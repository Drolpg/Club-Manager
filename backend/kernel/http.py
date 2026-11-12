"""Peças de transporte usadas por todos os módulos."""

from django.http import HttpRequest
from rest_framework.authentication import SessionAuthentication as _SessionAuthentication
from rest_framework.request import Request


class SessionAuthentication(_SessionAuthentication):
    """Autenticação por sessão (ADR-008) que responde 401, e não 403, a quem não está logado."""

    def authenticate_header(self, request: Request) -> str:
        return "Session"


def client_ip(request: HttpRequest) -> str:
    """IP de quem fez a requisição.

    Em produção há exatamente um proxy na frente da API (o Caddy), que acrescenta o IP real no fim do
    cabeçalho `X-Forwarded-For`. O que vier antes foi escrito pelo cliente e não é confiável.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return str(request.META.get("REMOTE_ADDR", ""))
