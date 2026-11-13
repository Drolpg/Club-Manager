"""Escrita de usuário logado sem o token CSRF (achado do M2 visto no M3)."""

import pytest
from rest_framework.test import APIClient

from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

CONVITES = "/api/v1/acesso/convites/"
MENSAGEM = "A página ficou desatualizada. Recarregue e tente de novo."


def _cliente_logado(admin: Usuario) -> APIClient:
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(admin)
    return client


def test_escrita_de_usuario_logado_sem_token_csrf_responde_csrf_failed(admin: Usuario) -> None:
    resposta = _cliente_logado(admin).post(CONVITES)

    assert resposta.status_code == 403
    assert resposta.json() == {"error": {"code": "CSRF_FAILED", "message": MENSAGEM, "details": None}}


def test_escrita_de_usuario_logado_com_token_csrf_invalido_responde_csrf_failed(admin: Usuario) -> None:
    client = _cliente_logado(admin)
    client.cookies["csrftoken"] = "a" * 64

    resposta = client.post(CONVITES, HTTP_X_CSRFTOKEN="a" * 32 + "b" * 32)

    assert (resposta.status_code, resposta.json()["error"]["code"]) == (403, "CSRF_FAILED")


def test_escrita_de_usuario_logado_com_token_valido_passa(admin: Usuario) -> None:
    client = _cliente_logado(admin)
    token = client.get("/api/v1/acesso/sessao/").cookies["csrftoken"].value

    resposta = client.post(CONVITES, HTTP_X_CSRFTOKEN=token)

    assert resposta.status_code == 201


def test_permissao_negada_continua_sendo_permission_denied(diretor: Usuario) -> None:
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(diretor)
    token = client.get("/api/v1/acesso/sessao/").cookies["csrftoken"].value

    resposta = client.post(CONVITES, HTTP_X_CSRFTOKEN=token)

    assert (resposta.status_code, resposta.json()["error"]["code"]) == (403, "PERMISSION_DENIED")
