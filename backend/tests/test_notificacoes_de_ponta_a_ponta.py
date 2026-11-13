"""CA-20 de ponta a ponta: o cadastro concluído, por senha e pelo Google, notifica os admins.

Fica em `tests/` porque cruza `acesso`, `permissoes` e `notificacoes`; os testes de cada módulo só usam a API
pública dos outros.
"""

import re
from collections.abc import Iterator
from unittest import mock

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from acesso.tests.fakes import VerificadorGoogleFalso
from notificacoes.models import Notificacao, SituacaoDoEmail
from tests.apoio import SENHA, Usuario

pytestmark = pytest.mark.django_db

CONVITES = "/api/v1/acesso/convites/"
CADASTROS = "/api/v1/acesso/cadastros/"
CADASTRO_GOOGLE = "/api/v1/acesso/cadastros/google/"
VERIFICACOES = "/api/v1/acesso/verificacoes/"
SESSAO_GOOGLE = "/api/v1/acesso/sessao/google/"

_TIPO = "acesso.cadastro_concluido"
_ASSUNTO_ANTIGO = "Novo diretor aguardando classificação"


@pytest.fixture(autouse=True)
def _executar_na_hora_o_que_roda_depois_do_commit() -> Iterator[None]:
    with mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()):
        yield


@pytest.fixture(autouse=True)
def _google_falso() -> Iterator[None]:
    VerificadorGoogleFalso.identidades.clear()
    with override_settings(GOOGLE_VERIFIER="acesso.tests.fakes.VerificadorGoogleFalso"):
        yield
    VerificadorGoogleFalso.identidades.clear()


def _convite(client_admin: APIClient) -> str:
    return str(client_admin.post(CONVITES).json()["link"]).rsplit("/", 1)[1]


def _dados(token: str, **extra: str) -> dict[str, str]:
    return {
        "token": token,
        "nome": "Caio Convidado",
        "nome_de_usuario": "caio",
        "telefone": "11977776666",
        "senha": SENHA,
        **extra,
    }


def _conferir_o_aviso_aos_admins(admin: Usuario, caio: Usuario) -> None:
    (notificacao,) = Notificacao.objects.filter(tipo=_TIPO)
    assert notificacao.destinatario_id == admin.id
    assert notificacao.pede_acao is True
    assert (notificacao.item_tipo, notificacao.item_id) == ("usuario", caio.id)
    assert notificacao.caminho == f"/admin/usuarios/{caio.id}"
    assert "Caio Convidado" in notificacao.texto
    assert notificacao.email_situacao == SituacaoDoEmail.ENVIADO
    assert [m.subject for m in mail.outbox if m.to == [admin.email]] == ["Novo diretor para classificar"]
    assert _ASSUNTO_ANTIGO not in {m.subject for m in mail.outbox}


def test_ca20_cadastro_por_senha_verificado_notifica_o_admin_e_o_email_simples_do_m2_nao_existe_mais(
    admin: Usuario, client_admin: APIClient
) -> None:
    token = _convite(client_admin)
    APIClient().post(CADASTROS, _dados(token, email="caio@exemplo.com"))
    link = re.search(r"/verificar/(\S+)", str(mail.outbox[-1].body))
    assert link
    assert Notificacao.objects.filter(tipo=_TIPO).count() == 0
    mail.outbox.clear()

    resposta = APIClient().post(VERIFICACOES, {"token": link.group(1)})

    assert resposta.status_code == 204
    _conferir_o_aviso_aos_admins(admin, Usuario.objects.get(nome_de_usuario="caio"))


def test_ca20_cadastro_pelo_google_notifica_o_admin_e_o_email_simples_do_m2_nao_existe_mais(
    admin: Usuario, client_admin: APIClient
) -> None:
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@gmail.com")
    token = _convite(client_admin)
    mail.outbox.clear()

    resposta = APIClient().post(CADASTRO_GOOGLE, _dados(token, credencial="cred-caio"))

    assert resposta.status_code == 201
    _conferir_o_aviso_aos_admins(admin, Usuario.objects.get(nome_de_usuario="caio"))


def test_ca20_entrar_pelo_google_de_quem_aguardava_verificacao_notifica_o_admin(
    admin: Usuario, client_admin: APIClient
) -> None:
    token = _convite(client_admin)
    APIClient().post(CADASTROS, _dados(token, email="caio@exemplo.com"))
    caio = Usuario.objects.get(nome_de_usuario="caio")
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@exemplo.com")
    mail.outbox.clear()

    resposta = APIClient().post(SESSAO_GOOGLE, {"credencial": "cred-caio"})

    assert resposta.status_code == 200
    _conferir_o_aviso_aos_admins(admin, caio)
