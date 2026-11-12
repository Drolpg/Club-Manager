from typing import Any

import pytest
from django.urls import path
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient

from kernel.errors import BusinessError, handler404, handler500  # noqa: F401


class _Entrada(serializers.Serializer[Any]):
    valor = serializers.DecimalField(max_digits=12, decimal_places=2)


@api_view(["GET"])
@permission_classes([AllowAny])
def _regra_violada(request: Request) -> Response:
    raise BusinessError(code="NAO_ESTA_EM_ANALISE", message="A solicitação não está em análise.")


@api_view(["GET"])
@permission_classes([AllowAny])
def _erro_inesperado(request: Request) -> Response:
    raise RuntimeError("SELECT * FROM segredo")


@api_view(["POST"])
@permission_classes([AllowAny])
def _entrada_invalida(request: Request) -> Response:
    _Entrada(data=request.data).is_valid(raise_exception=True)
    return Response({})


@api_view(["GET"])
def _protegida(request: Request) -> Response:
    return Response({})


urlpatterns = [
    path("regra/", _regra_violada),
    path("inesperado/", _erro_inesperado),
    path("invalida/", _entrada_invalida),
    path("protegida/", _protegida),
]


@pytest.fixture
def client() -> APIClient:
    return APIClient(raise_request_exception=False)


pytestmark = pytest.mark.urls(__name__)


def test_erro_de_negocio_vira_envelope_com_codigo_estavel(client: APIClient) -> None:
    response = client.get("/regra/")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "NAO_ESTA_EM_ANALISE",
            "message": "A solicitação não está em análise.",
            "details": None,
        }
    }


def test_erro_de_negocio_aceita_outro_status() -> None:
    erro = BusinessError(code="X", message="x", status=409)

    assert erro.status == 409


def test_erro_inesperado_nao_expoe_mensagem_interna(client: APIClient) -> None:
    response = client.get("/inesperado/")

    assert response.status_code == 500
    corpo = response.json()
    assert corpo["error"]["code"] == "INTERNAL_ERROR"
    assert "SELECT" not in response.content.decode()


def test_entrada_invalida_vira_envelope_com_os_campos(client: APIClient) -> None:
    response = client.post("/invalida/", {"valor": "abc"}, format="json")

    assert response.status_code == 400
    corpo = response.json()
    assert corpo["error"]["code"] == "VALIDATION_ERROR"
    assert "valor" in corpo["error"]["details"]


def test_rota_inexistente_vira_envelope(client: APIClient) -> None:
    response = client.get("/nao-existe/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_rota_sem_permissao_explicita_e_negada_por_padrao(client: APIClient) -> None:
    response = client.get("/protegida/")

    assert response.status_code in (401, 403)
    assert response.json()["error"]["code"] in ("NOT_AUTHENTICATED", "PERMISSION_DENIED")
