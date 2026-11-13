from collections.abc import Iterator
from typing import Any, ClassVar
from unittest import mock

import pytest
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from acesso.google import CredencialGoogleInvalida, VerificadorGoogleReal
from acesso.models import Convite, Situacao, Usuario
from acesso.tests.conftest import SENHA, criar_diretor, entrar
from acesso.tests.fakes import VerificadorGoogleFalso
from auditoria import public as auditoria

pytestmark = pytest.mark.django_db

CONVITES = "/api/v1/acesso/convites/"
CADASTRO_GOOGLE = "/api/v1/acesso/cadastros/google/"
SESSAO = "/api/v1/acesso/sessao/"
SESSAO_GOOGLE = "/api/v1/acesso/sessao/google/"
CONFIGURACAO = "/api/v1/acesso/configuracao/"


@pytest.fixture(autouse=True)
def _google_falso() -> Iterator[None]:
    VerificadorGoogleFalso.identidades.clear()
    with (
        override_settings(GOOGLE_VERIFIER="acesso.tests.fakes.VerificadorGoogleFalso"),
        mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()),
    ):
        yield
    VerificadorGoogleFalso.identidades.clear()


@pytest.fixture
def token(client_admin: APIClient) -> str:
    link: str = client_admin.post(CONVITES).json()["link"]
    return link.rsplit("/", 1)[1]


def _dados(token: str, credencial: str = "cred-caio", **extra: str) -> dict[str, str]:
    dados = {
        "token": token,
        "credencial": credencial,
        "nome": "Caio Convidado",
        "nome_de_usuario": "caio",
        "telefone": "11977776666",
        "senha": SENHA,
    }
    dados.update(extra)
    return dados


def _convite_ativo(token: str) -> bool:
    return bool(APIClient().post(f"{CONVITES}consultar/", {"token": token}).status_code == 204)


def _entrar_com_google(credencial: str) -> Any:
    return APIClient().post(SESSAO_GOOGLE, {"credencial": credencial})


def test_ca15_cadastro_pelo_google_ativa_a_conta_sem_link_de_verificacao(token: str, admin: Usuario) -> None:
    VerificadorGoogleFalso.aceitar("cred-caio", email="Caio@Gmail.com")
    mail.outbox.clear()
    client = APIClient()

    resposta = client.post(CADASTRO_GOOGLE, _dados(token))

    assert resposta.status_code == 201
    usuario = Usuario.objects.get(nome_de_usuario="caio")
    assert usuario.situacao == Situacao.ATIVO
    assert usuario.email == "caio@gmail.com"
    assert usuario.email_verificado_em is not None
    assert usuario.google_sub == "sub-Caio@Gmail.com"
    assert usuario.admin is False
    assert not _convite_ativo(token)
    assert Convite.objects.get().usado_por == usuario
    # Nenhum link de verificação; só o aviso aos admins.
    assert [m.to for m in mail.outbox] == [[admin.email]]
    assert "verificar" not in mail.outbox[0].body
    # Já sai logado.
    assert resposta.json()["usuario"]["id"] == str(usuario.id)
    assert client.get(SESSAO).json()["usuario"]["id"] == str(usuario.id)
    acoes = [r.acao for r in auditoria.historico_do_item("usuario", usuario.id)]
    assert acoes == ["CADASTRO_CONCLUIDO"]


def test_ca16_email_do_google_que_ja_tem_conta_nao_cria_outra_e_nao_gasta_o_convite(
    token: str, admin: Usuario
) -> None:
    VerificadorGoogleFalso.aceitar("cred-ana", email="ANA@exemplo.com")

    resposta = APIClient().post(CADASTRO_GOOGLE, _dados(token, "cred-ana"))

    assert resposta.status_code == 409
    assert resposta.json()["error"]["code"] == "CONTA_JA_EXISTE"
    assert Usuario.objects.count() == 1
    assert _convite_ativo(token)


def test_ca17_conta_criada_com_senha_entra_pelo_google_com_o_mesmo_email(diretor: Usuario) -> None:
    VerificadorGoogleFalso.aceitar("cred-bia", email="BIA@exemplo.com", sub="google-bia")
    client = APIClient()

    resposta = client.post(SESSAO_GOOGLE, {"credencial": "cred-bia"})

    assert resposta.status_code == 200
    assert resposta.json()["usuario"]["id"] == str(diretor.id)
    assert client.get(SESSAO).json()["usuario"]["id"] == str(diretor.id)
    assert Usuario.objects.count() == 1
    assert Usuario.objects.get(pk=diretor.pk).google_sub == "google-bia"


def test_ca18_conta_criada_pelo_google_entra_com_usuario_e_senha(token: str) -> None:
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@gmail.com")
    APIClient().post(CADASTRO_GOOGLE, _dados(token))

    client = APIClient()
    entrar(client, "caio")

    assert client.get(SESSAO).json()["usuario"]["email"] == "caio@gmail.com"


def test_ca19_quem_nao_tem_conta_nao_entra_pelo_google(db: None) -> None:
    VerificadorGoogleFalso.aceitar("cred-estranho", email="estranho@gmail.com")

    resposta = _entrar_com_google("cred-estranho")

    assert resposta.status_code == 403
    assert resposta.json()["error"]["code"] == "ACESSO_SO_POR_CONVITE"
    assert Usuario.objects.count() == 0


def test_ca28_usuario_desativado_nao_entra_pelo_google(db: None) -> None:
    criar_diretor("dani", Situacao.INATIVO)
    VerificadorGoogleFalso.aceitar("cred-dani", email="dani@exemplo.com")

    resposta = _entrar_com_google("cred-dani")

    assert resposta.status_code == 401
    assert resposta.json()["error"]["code"] == "CREDENCIAIS_INVALIDAS"


def test_entrar_pelo_google_verifica_a_conta_que_aguardava_verificacao(admin: Usuario) -> None:
    pendente = criar_diretor("caio", Situacao.AGUARDANDO_VERIFICACAO)
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@exemplo.com")
    mail.outbox.clear()

    resposta = _entrar_com_google("cred-caio")

    assert resposta.status_code == 200
    atual = Usuario.objects.get(pk=pendente.pk)
    assert atual.situacao == Situacao.ATIVO
    assert atual.email_verificado_em is not None
    assert [m.to for m in mail.outbox] == [[admin.email]]
    assert [r.acao for r in auditoria.historico_do_item("usuario", pendente.id)] == ["CADASTRO_CONCLUIDO"]


@pytest.mark.parametrize("rota", [SESSAO_GOOGLE, CADASTRO_GOOGLE])
def test_credencial_invalida_e_recusada(token: str, rota: str) -> None:
    corpo = {"credencial": "forjada"} if rota == SESSAO_GOOGLE else _dados(token, "forjada")

    resposta = APIClient().post(rota, corpo)

    assert resposta.status_code == 401
    assert resposta.json()["error"]["code"] == "GOOGLE_INVALIDO"
    assert Usuario.objects.filter(admin=False).count() == 0
    assert _convite_ativo(token)


def test_outra_conta_google_com_o_mesmo_email_nao_toma_a_conta_ja_vinculada(diretor: Usuario) -> None:
    VerificadorGoogleFalso.aceitar("cred-bia", email="bia@exemplo.com", sub="google-bia")
    _entrar_com_google("cred-bia")
    VerificadorGoogleFalso.aceitar("cred-impostor", email="bia@exemplo.com", sub="google-outro")

    resposta = _entrar_com_google("cred-impostor")

    assert resposta.status_code == 401
    assert resposta.json()["error"]["code"] == "GOOGLE_INVALIDO"


def test_cadastro_pelo_google_com_convite_invalido_nao_cria_conta(db: None) -> None:
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@gmail.com")

    resposta = APIClient().post(CADASTRO_GOOGLE, _dados("token-que-nao-existe"))

    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "CONVITE_INVALIDO"
    assert Usuario.objects.count() == 0


def test_cadastro_pelo_google_valida_os_demais_dados_e_nao_gasta_o_convite(token: str) -> None:
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@gmail.com")

    resposta = APIClient().post(CADASTRO_GOOGLE, _dados(token, senha="12345678"))

    assert resposta.status_code == 400
    assert "senha" in resposta.json()["error"]["details"]
    assert _convite_ativo(token)


def test_o_email_da_conta_e_sempre_o_do_google_e_nao_um_enviado_pelo_cliente(token: str) -> None:
    VerificadorGoogleFalso.aceitar("cred-caio", email="caio@gmail.com")

    APIClient().post(CADASTRO_GOOGLE, {**_dados(token), "email": "outro@exemplo.com"})

    assert Usuario.objects.get(nome_de_usuario="caio").email == "caio@gmail.com"


def test_configuracao_informa_o_id_de_cliente_do_google(db: None) -> None:
    with override_settings(GOOGLE_CLIENT_ID="123-abc.apps.googleusercontent.com"):
        com_id = APIClient().get(CONFIGURACAO)
    with override_settings(GOOGLE_CLIENT_ID=""):
        sem_id = APIClient().get(CONFIGURACAO)

    assert com_id.json() == {"google_client_id": "123-abc.apps.googleusercontent.com"}
    assert sem_id.json() == {"google_client_id": None}


class _RespostaDeCertificados:
    status = 200
    data = b"{}"
    headers: ClassVar[dict[str, str]] = {}


def _transporte_sem_rede(*args: Any, **kwargs: Any) -> _RespostaDeCertificados:
    return _RespostaDeCertificados()


def test_adapter_real_recusa_token_forjado_sem_usar_a_rede() -> None:
    verificador = VerificadorGoogleReal(
        client_id="123.apps.googleusercontent.com", transporte=_transporte_sem_rede
    )

    with pytest.raises(CredencialGoogleInvalida):
        verificador.verificar("eyJhbGciOiJub25lIn0.eyJlbWFpbCI6ImFAYi5jIn0.")


def test_adapter_real_sem_id_de_cliente_recusa_tudo() -> None:
    with pytest.raises(CredencialGoogleInvalida):
        VerificadorGoogleReal(client_id="", transporte=_transporte_sem_rede).verificar("qualquer")


@pytest.mark.parametrize(
    "conteudo",
    [
        {"sub": "1", "email": "a@gmail.com", "email_verified": False, "name": "A"},
        {"sub": "1", "email_verified": True, "name": "A"},
        {"email": "a@gmail.com", "email_verified": True},
    ],
)
def test_adapter_real_exige_email_verificado_e_identificador(conteudo: dict[str, Any]) -> None:
    verificador = VerificadorGoogleReal(
        client_id="123.apps.googleusercontent.com", transporte=_transporte_sem_rede
    )

    with (
        mock.patch("google.oauth2.id_token.verify_oauth2_token", return_value=conteudo),
        pytest.raises(CredencialGoogleInvalida),
    ):
        verificador.verificar("token")


def test_adapter_real_confere_o_publico_alvo_e_devolve_a_identidade() -> None:
    verificador = VerificadorGoogleReal(
        client_id="123.apps.googleusercontent.com", transporte=_transporte_sem_rede
    )
    conteudo = {"sub": "42", "email": "Caio@Gmail.com", "email_verified": True, "name": "Caio"}

    with mock.patch("google.oauth2.id_token.verify_oauth2_token", return_value=conteudo) as verificar:
        identidade = verificador.verificar("token")

    assert (identidade.sub, identidade.email, identidade.nome) == ("42", "Caio@Gmail.com", "Caio")
    assert verificar.call_args.kwargs["audience"] == "123.apps.googleusercontent.com"
