import pytest
from rest_framework.test import APIClient

from config.celery import app as celery_app


@pytest.mark.django_db
def test_contrato_openapi_e_gerado_e_lista_o_health() -> None:
    response = APIClient().get("/api/v1/schema/", headers={"Accept": "application/json"})

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Club Manager API"
    assert "/api/v1/health/" in schema["paths"]


def test_celery_le_a_configuracao_do_django() -> None:
    assert celery_app.main == "club_manager"
    assert celery_app.conf.task_always_eager is True
    assert celery_app.conf.timezone == "America/Sao_Paulo"
