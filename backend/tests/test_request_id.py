import json
import logging

import pytest
from rest_framework.test import APIClient

from kernel.logging import JsonFormatter, request_id_var


@pytest.mark.django_db
def test_resposta_devolve_um_request_id_gerado() -> None:
    response = APIClient().get("/api/v1/health/")

    assert len(response["X-Request-ID"]) >= 16


@pytest.mark.django_db
def test_resposta_reaproveita_o_request_id_recebido() -> None:
    response = APIClient().get("/api/v1/health/", headers={"X-Request-ID": "abc-123_DEF"})

    assert response["X-Request-ID"] == "abc-123_DEF"


@pytest.mark.django_db
def test_request_id_recebido_malformado_e_substituido() -> None:
    response = APIClient().get("/api/v1/health/", headers={"X-Request-ID": "x\ninjetado: 1" * 20})

    assert "injetado" not in response["X-Request-ID"]


def test_log_sai_em_json_com_o_request_id() -> None:
    token = request_id_var.set("req-1")
    try:
        record = logging.LogRecord("app", logging.INFO, __file__, 1, "pagamento %s", ("validado",), None)
        linha = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert linha["message"] == "pagamento validado"
    assert linha["level"] == "INFO"
    assert linha["logger"] == "app"
    assert linha["request_id"] == "req-1"
    assert "time" in linha
