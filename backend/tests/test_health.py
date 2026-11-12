from unittest import mock

import pytest
from django.db import OperationalError
from rest_framework.test import APIClient


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_health_responde_ok_com_o_banco_no_ar(client: APIClient) -> None:
    response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_health_responde_503_sem_expor_o_erro_quando_o_banco_cai(client: APIClient) -> None:
    with mock.patch(
        "kernel.health.connection.cursor",
        side_effect=OperationalError("senha=segredo host=interno"),
    ):
        response = client.get("/api/v1/health/")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert "segredo" not in response.content.decode()


@pytest.mark.django_db
def test_health_nao_exige_autenticacao(client: APIClient) -> None:
    response = client.get("/api/v1/health/")

    assert response.status_code != 401
    assert response.status_code != 403
