"""Peças de transporte usadas por todos os módulos."""

from django.http import HttpRequest
from rest_framework.authentication import SessionAuthentication as _SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from kernel.errors import CSRF_MESSAGE, BusinessError


class SessionAuthentication(_SessionAuthentication):
    """Autenticação por sessão (ADR-008) que responde 401, e não 403, a quem não está logado."""

    def authenticate_header(self, request: Request) -> str:
        return "Session"

    def enforce_csrf(self, request: Request) -> None:
        """Escrita de usuário logado sem token válido responde `CSRF_FAILED`, e não `PERMISSION_DENIED`.

        Sem isto, o DRF levanta `PermissionDenied` e o código sai igual ao de falta de permissão.
        """
        try:
            super().enforce_csrf(request)
        except PermissionDenied as erro:
            raise BusinessError("CSRF_FAILED", CSRF_MESSAGE, status=403) from erro


def client_ip(request: HttpRequest) -> str:
    """IP de quem fez a requisição.

    Em produção há exatamente um proxy na frente da API (o Caddy), que acrescenta o IP real no fim do
    cabeçalho `X-Forwarded-For`. O que vier antes foi escrito pelo cliente e não é confiável.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return str(request.META.get("REMOTE_ADDR", ""))
