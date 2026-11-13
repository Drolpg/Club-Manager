"""O contrato e a documentação da API só para o admin, sem depender de CDN (encerra a TD-001)."""

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

SCHEMA = "/api/v1/schema/"
DOCS = "/api/v1/docs/"


@pytest.mark.parametrize("rota", [SCHEMA, DOCS])
def test_sem_sessao_o_contrato_e_a_documentacao_sao_negados(rota: str) -> None:
    resposta = APIClient().get(rota)

    assert resposta.status_code == 401


@pytest.mark.parametrize("rota", [SCHEMA, DOCS])
def test_diretor_nao_ve_o_contrato_nem_a_documentacao(client_diretor: APIClient, rota: str) -> None:
    resposta = client_diretor.get(rota)

    assert resposta.status_code == 403


def test_admin_ve_o_contrato_com_as_rotas_do_acesso(client_admin: APIClient) -> None:
    resposta = client_admin.get(SCHEMA, headers={"Accept": "application/json"})

    assert resposta.status_code == 200
    schema = resposta.json()
    assert schema["info"]["title"] == "Club Manager API"
    for caminho in ("/api/v1/health/", "/api/v1/acesso/sessao/", "/api/v1/acesso/convites/"):
        assert caminho in schema["paths"]


def test_pagina_de_documentacao_nao_carrega_nada_de_cdn(client_admin: APIClient) -> None:
    resposta = client_admin.get(DOCS, headers={"Accept": "text/html"})

    assert resposta.status_code == 200
    pagina = resposta.content.decode()
    assert "/static/drf_spectacular_sidecar/" in pagina
    for cdn in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"):
        assert cdn not in pagina
