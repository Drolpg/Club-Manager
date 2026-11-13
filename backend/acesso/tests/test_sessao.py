from typing import Any

import pytest
from rest_framework.test import APIClient

from acesso.models import Situacao, Usuario
from acesso.tests.conftest import SENHA, criar_diretor, entrar

pytestmark = pytest.mark.django_db

URL = "/api/v1/acesso/sessao/"
SENHA_ERRADA = "senha-errada-123"


def _login(client: APIClient, identificador: str, senha: str = SENHA) -> Any:
    return client.post(URL, {"identificador": identificador, "senha": senha})


@pytest.mark.parametrize("identificador", ["bia", "BIA", " Bia ", "bia@exemplo.com", "BIA@Exemplo.COM"])
def test_ca20_entra_por_nome_de_usuario_ou_email_em_qualquer_caixa(
    client: APIClient, diretor: Usuario, identificador: str
) -> None:
    resposta = _login(client, identificador)

    assert resposta.status_code == 200
    assert resposta.json()["usuario"] == {
        "id": str(diretor.id),
        "nome": "Diretor bia",
        "nome_de_usuario": "bia",
        "email": "bia@exemplo.com",
        "admin": False,
        "situacao": "ATIVO",
        "tem_cargo": False,
    }
    assert client.get(URL).json()["usuario"]["id"] == str(diretor.id)


def test_resposta_do_login_nao_traz_a_senha_nem_o_hash(client: APIClient, diretor: Usuario) -> None:
    corpo = _login(client, "bia").content.decode()

    assert "password" not in corpo
    assert "argon2" not in corpo


def test_ca21_conta_inexistente_e_senha_errada_tem_a_mesma_resposta(
    client: APIClient, diretor: Usuario
) -> None:
    inexistente = _login(client, "ninguem")
    senha_errada = _login(client, "bia", SENHA_ERRADA)

    assert inexistente.status_code == senha_errada.status_code == 401
    assert inexistente.json() == senha_errada.json()
    assert inexistente.json()["error"]["code"] == "CREDENCIAIS_INVALIDAS"


def test_ca10_conta_aguardando_verificacao_e_recusada_com_aviso_proprio(client: APIClient) -> None:
    criar_diretor("caio", Situacao.AGUARDANDO_VERIFICACAO)

    resposta = _login(client, "caio")

    assert resposta.status_code == 403
    assert resposta.json()["error"]["code"] == "EMAIL_NAO_VERIFICADO"
    assert client.get(URL).json() == {"usuario": None}


def test_conta_aguardando_verificacao_com_senha_errada_nao_revela_a_situacao(client: APIClient) -> None:
    criar_diretor("caio", Situacao.AGUARDANDO_VERIFICACAO)

    resposta = _login(client, "caio", SENHA_ERRADA)

    assert resposta.json()["error"]["code"] == "CREDENCIAIS_INVALIDAS"


def test_conta_inativa_e_recusada_como_dados_invalidos(client: APIClient) -> None:
    criar_diretor("dani", Situacao.INATIVO)

    resposta = _login(client, "dani")

    assert resposta.status_code == 401
    assert resposta.json()["error"]["code"] == "CREDENCIAIS_INVALIDAS"


def test_ca22_sexta_tentativa_e_recusada_mesmo_com_a_senha_certa(client: APIClient, diretor: Usuario) -> None:
    for _ in range(5):
        assert _login(client, "bia", SENHA_ERRADA).status_code == 401

    resposta = _login(client, "BIA")

    assert resposta.status_code == 429
    assert resposta.json()["error"]["code"] == "MUITAS_TENTATIVAS"
    assert client.get(URL).json() == {"usuario": None}


def test_bloqueio_vale_tambem_para_o_email_da_mesma_conta(client: APIClient, diretor: Usuario) -> None:
    for _ in range(5):
        _login(client, "bia", SENHA_ERRADA)

    assert _login(client, "bia@exemplo.com").status_code == 429


def test_bloqueio_de_uma_conta_nao_atinge_outra(client: APIClient, diretor: Usuario) -> None:
    criar_diretor("edu")
    for _ in range(5):
        _login(client, "bia", SENHA_ERRADA)

    assert _login(client, "edu").status_code == 200


def test_login_certo_zera_a_contagem_de_erros(client: APIClient, diretor: Usuario) -> None:
    for _ in range(4):
        _login(client, "bia", SENHA_ERRADA)
    assert _login(client, "bia").status_code == 200
    for _ in range(4):
        _login(client, "bia", SENHA_ERRADA)

    assert _login(client, "bia").status_code == 200


def test_tentativas_em_conta_inexistente_tambem_sao_limitadas(client: APIClient, db: None) -> None:
    for _ in range(5):
        _login(client, "ninguem", SENHA_ERRADA)

    assert _login(client, "ninguem", SENHA_ERRADA).status_code == 429


def test_ca23_sair_encerra_a_sessao(client: APIClient, diretor: Usuario) -> None:
    entrar(client, "bia")

    resposta = client.delete(URL)

    assert resposta.status_code == 204
    assert client.get(URL).json() == {"usuario": None}


def test_ca36_rota_protegida_sem_sessao_e_negada(client: APIClient, db: None) -> None:
    resposta = client.delete(URL)

    assert resposta.status_code == 401
    assert resposta.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_consultar_a_sessao_sem_login_devolve_usuario_nulo_e_o_cookie_csrf(
    client: APIClient, db: None
) -> None:
    resposta = client.get(URL)

    assert resposta.status_code == 200
    assert resposta.json() == {"usuario": None}
    assert "csrftoken" in resposta.cookies


def test_login_sem_token_csrf_e_recusado(diretor: Usuario) -> None:
    client = APIClient(enforce_csrf_checks=True)

    resposta = _login(client, "bia")

    assert resposta.status_code == 403


def test_login_com_token_csrf_e_aceito(diretor: Usuario) -> None:
    client = APIClient(enforce_csrf_checks=True)
    token = client.get(URL).cookies["csrftoken"].value

    resposta = client.post(URL, {"identificador": "bia", "senha": SENHA}, headers={"X-CSRFToken": token})

    assert resposta.status_code == 200


def test_escrita_logada_sem_token_csrf_e_recusada(diretor: Usuario) -> None:
    client = APIClient(enforce_csrf_checks=True)
    token = client.get(URL).cookies["csrftoken"].value
    client.post(URL, {"identificador": "bia", "senha": SENHA}, headers={"X-CSRFToken": token})

    resposta = client.delete(URL)

    assert resposta.status_code == 403
    assert client.get(URL).json()["usuario"] is not None


def test_login_troca_a_chave_da_sessao(client: APIClient, diretor: Usuario) -> None:
    sessao = client.session
    sessao["marcador"] = "antes do login"
    sessao.save()
    antes = sessao.session_key

    entrar(client, "bia")

    assert client.session.session_key != antes


def test_cookie_de_sessao_nao_e_legivel_por_script(client: APIClient, diretor: Usuario) -> None:
    resposta = _login(client, "bia")

    assert resposta.cookies["sessionid"]["httponly"]
    assert resposta.cookies["sessionid"]["samesite"] == "Lax"


def test_usuario_desativado_perde_a_sessao_na_requisicao_seguinte(
    client: APIClient, diretor: Usuario
) -> None:
    entrar(client, "bia")
    Usuario.objects.filter(pk=diretor.pk).update(situacao=Situacao.INATIVO)

    assert client.get(URL).json() == {"usuario": None}
    assert client.delete(URL).status_code == 401


def test_login_valida_os_campos(client: APIClient, db: None) -> None:
    resposta = client.post(URL, {"identificador": ""})

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "VALIDATION_ERROR"


def test_falha_de_csrf_responde_no_envelope_de_erro(diretor: Usuario) -> None:
    client = APIClient(enforce_csrf_checks=True)

    resposta = _login(client, "bia")

    assert resposta.status_code == 403
    assert resposta.json()["error"]["code"] == "CSRF_FAILED"
