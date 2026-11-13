"""`acesso` publica eventos de integração (ADR-003): cadastro concluído e mudança do papel de admin.

`acesso` não conhece quem trata os eventos: aqui um tratador de teste guarda o que recebeu.
"""

import dataclasses
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from acesso import public
from acesso.models import Situacao, Usuario
from acesso.services import cadastro, usuarios
from acesso.tests.conftest import SENHA, criar_diretor
from acesso.tests.fakes import VerificadorGoogleFalso
from kernel import events
from kernel.errors import BusinessError

pytestmark = pytest.mark.django_db

CONVITES = "/api/v1/acesso/convites/"
CADASTROS = "/api/v1/acesso/cadastros/"
CADASTRO_GOOGLE = "/api/v1/acesso/cadastros/google/"
VERIFICACOES = "/api/v1/acesso/verificacoes/"
SESSAO_GOOGLE = "/api/v1/acesso/sessao/google/"

_GOOGLE_FALSO = "acesso.tests.fakes.VerificadorGoogleFalso"


@pytest.fixture(autouse=True)
def _executar_na_hora_o_que_roda_depois_do_commit() -> Iterator[None]:
    with mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()):
        yield


@pytest.fixture(autouse=True)
def _google_falso() -> Iterator[None]:
    VerificadorGoogleFalso.identidades.clear()
    with override_settings(GOOGLE_VERIFIER=_GOOGLE_FALSO):
        yield
    VerificadorGoogleFalso.identidades.clear()


@pytest.fixture
def recebidos(tratadores_de_eventos: None) -> list[Any]:
    """Um tratador de teste para cada evento de `acesso`; o que ele recebe fica na lista."""
    events.unsubscribe_all_for_tests()
    lista: list[Any] = []
    events.subscribe(public.CadastroConcluido, lista.append)
    events.subscribe(public.PapelDeAdminAlterado, lista.append)
    return lista


def _token_de_convite(client_admin: APIClient) -> str:
    return str(client_admin.post(CONVITES).json()["link"]).rsplit("/", 1)[1]


def _dados_do_cadastro(token: str, **extra: str) -> dict[str, str]:
    return {
        "token": token,
        "nome": "Caio Convidado",
        "nome_de_usuario": "caio",
        "telefone": "11977776666",
        "senha": SENHA,
        **extra,
    }


def test_os_eventos_sao_dados_imutaveis_da_api_publica(diretor: Usuario) -> None:
    evento = public.CadastroConcluido(usuario_id=diretor.id)

    assert dataclasses.is_dataclass(evento)
    with pytest.raises(dataclasses.FrozenInstanceError):
        evento.usuario_id = diretor.id  # type: ignore[misc]


def test_concluir_o_cadastro_publica_cadastro_concluido(recebidos: list[Any], diretor: Usuario) -> None:
    cadastro.concluir_cadastro(diretor)

    assert recebidos == [public.CadastroConcluido(usuario_id=diretor.id)]


def test_concluir_o_cadastro_nao_manda_mais_o_email_simples_aos_admins(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    mail.outbox.clear()

    cadastro.concluir_cadastro(diretor)

    assert mail.outbox == []


def test_verificar_o_link_publica_cadastro_concluido(recebidos: list[Any], client_admin: APIClient) -> None:
    token = _token_de_convite(client_admin)
    APIClient().post(CADASTROS, _dados_do_cadastro(token, email="caio@exemplo.com"))
    token_de_verificacao = mail.outbox[-1].body.split("/verificar/")[1].split()[0]
    assert recebidos == []

    resposta = APIClient().post(VERIFICACOES, {"token": token_de_verificacao})

    assert resposta.status_code == 204
    caio = Usuario.objects.get(nome_de_usuario="caio")
    assert recebidos == [public.CadastroConcluido(usuario_id=caio.id)]


def test_o_cadastro_pelo_google_publica_cadastro_concluido(
    recebidos: list[Any], client_admin: APIClient
) -> None:
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@gmail.com")
    token = _token_de_convite(client_admin)

    resposta = APIClient().post(CADASTRO_GOOGLE, _dados_do_cadastro(token, credencial="cred-caio"))

    assert resposta.status_code == 201
    caio = Usuario.objects.get(nome_de_usuario="caio")
    assert recebidos == [public.CadastroConcluido(usuario_id=caio.id)]


def test_entrar_pelo_google_de_quem_aguardava_verificacao_publica_cadastro_concluido(
    recebidos: list[Any], admin: Usuario
) -> None:
    pendente = criar_diretor("caio", Situacao.AGUARDANDO_VERIFICACAO)
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@exemplo.com")

    resposta = APIClient().post(SESSAO_GOOGLE, {"credencial": "cred-caio"})

    assert resposta.status_code == 200
    assert recebidos == [public.CadastroConcluido(usuario_id=pendente.id)]


def test_entrar_pelo_google_de_conta_ja_ativa_nao_publica(recebidos: list[Any], admin: Usuario) -> None:
    VerificadorGoogleFalso.aceitar("cred-ana", email=admin.email)

    resposta = APIClient().post(SESSAO_GOOGLE, {"credencial": "cred-ana"})

    assert resposta.status_code == 200
    assert recebidos == []


def test_tornar_admin_publica_papel_de_admin_alterado(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    usuarios.tornar_admin(ator=admin, usuario_id=diretor.id)

    assert recebidos == [public.PapelDeAdminAlterado(usuario_id=diretor.id, admin=True)]


def test_remover_admin_publica_papel_de_admin_alterado(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    usuarios.tornar_admin(ator=admin, usuario_id=diretor.id)
    recebidos.clear()

    usuarios.remover_admin(ator=admin, usuario_id=diretor.id)

    assert recebidos == [public.PapelDeAdminAlterado(usuario_id=diretor.id, admin=False)]


def test_tornar_admin_de_quem_ja_e_admin_nao_publica(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    usuarios.tornar_admin(ator=admin, usuario_id=diretor.id)
    recebidos.clear()

    with pytest.raises(BusinessError):
        usuarios.tornar_admin(ator=admin, usuario_id=diretor.id)

    assert recebidos == []


def test_o_erro_do_tratador_desfaz_a_mudanca_de_papel(
    admin: Usuario, diretor: Usuario, tratadores_de_eventos: None
) -> None:
    def quebra(evento: Any) -> None:
        raise RuntimeError("falhou")

    events.subscribe(public.PapelDeAdminAlterado, quebra)

    with pytest.raises(RuntimeError):
        usuarios.tornar_admin(ator=admin, usuario_id=diretor.id)

    assert Usuario.objects.get(pk=diretor.id).admin is False
