"""Logs estruturados com ID de correlação (RNF-13).

Cada requisição ganha um `request_id`, devolvido no cabeçalho `X-Request-ID` e incluído em toda linha de log.
Não registre dados pessoais, tokens nem segredos.
"""

import json
import logging
import re
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from django.http import HttpRequest, HttpResponse

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_HEADER = "X-Request-ID"
_VALID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        received = request.headers.get(_HEADER, "")
        # Só reaproveita o ID recebido se tiver formato seguro; senão gera outro.
        request_id = received if _VALID.fullmatch(received) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[_HEADER] = request_id
        return response


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)
