"""Erros para o cliente: sempre o mesmo envelope, com código estável.

    {"error": {"code": "NAO_ESTA_EM_ANALISE", "message": "...", "details": null}}

Nunca sai stack trace, SQL nem mensagem interna (AGENTS.md).
"""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, JsonResponse
from rest_framework import exceptions, status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

_INTERNAL_MESSAGE = "Erro interno. Tente de novo; se continuar, avise o administrador."


class BusinessError(Exception):
    """Regra de negócio violada. O `code` é contrato com os clientes e não muda."""

    def __init__(self, code: str, message: str, *, status: int = 422, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """Handler do DRF. Converte toda exceção no envelope."""
    if isinstance(exc, BusinessError):
        return Response(envelope(exc.code, exc.message, exc.details), status=exc.status)

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, exceptions.ValidationError):
        return Response(
            envelope("VALIDATION_ERROR", "Os dados enviados são inválidos.", exc.get_full_details()),
            status=exc.status_code,
        )

    if isinstance(exc, exceptions.APIException):
        code = str(exc.default_code).upper()
        return Response(envelope(code, str(exc.detail)), status=exc.status_code)

    logger.exception("Erro não tratado em %s", context.get("view"))
    return Response(
        envelope("INTERNAL_ERROR", _INTERNAL_MESSAGE), status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def handler404(request: HttpRequest, exception: Exception) -> JsonResponse:
    """Rota que não existe, fora das views do DRF."""
    return JsonResponse(envelope("NOT_FOUND", "Recurso não encontrado."), status=404)


def handler500(request: HttpRequest) -> JsonResponse:
    return JsonResponse(envelope("INTERNAL_ERROR", _INTERNAL_MESSAGE), status=500)
