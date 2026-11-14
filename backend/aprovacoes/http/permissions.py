"""Permissões das rotas, sobre as APIs públicas de `permissoes` (adendo 1 da technical-spec).

Toda rota é negada por padrão; as abertas declaram uma destas. O serviço confere de novo.
"""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from permissoes import public as permissoes


def _usuario_ativo(request: Request) -> bool:
    return bool(getattr(request.user, "is_active", False))


class EhAdmin(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return _usuario_ativo(request) and bool(getattr(request.user, "admin", False))


class LeGestao(BasePermission):
    """Admin ativo, ou diretor ativo com cargo ativo (PER-R10)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        usuario_id = getattr(request.user, "id", None)
        return _usuario_ativo(request) and usuario_id is not None and permissoes.le_gestao(usuario_id)
