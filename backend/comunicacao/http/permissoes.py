"""Permissões HTTP das rotas de `comunicacao`: a entrada, antes de qualquer outra conferência.

O serviço confere de novo, com o item (autoria, situação), porque também é chamado em processo.
"""

import uuid

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from permissoes import public as permissoes


def _usuario_id(request: Request) -> uuid.UUID | None:
    usuario = request.user
    if not (getattr(usuario, "is_authenticated", False) and getattr(usuario, "is_active", False)):
        return None
    raw_id = getattr(usuario, "id", None)
    return uuid.UUID(str(raw_id)) if raw_id is not None else None


class LeGestao(BasePermission):
    """Admin ativo, ou diretor ativo com cargo ativo."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        usuario_id = _usuario_id(request)
        return usuario_id is not None and permissoes.le_gestao(usuario_id)


class EhAdmin(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return _usuario_id(request) is not None and bool(getattr(request.user, "admin", False))


def exige_permissao(codigo: str) -> type[BasePermission]:
    """Leitura de gestão e a permissão do catálogo (o admin a tem pelo acesso total)."""

    class _Permissao(BasePermission):
        def has_permission(self, request: Request, view: APIView) -> bool:
            usuario_id = _usuario_id(request)
            return (
                usuario_id is not None
                and permissoes.le_gestao(usuario_id)
                and permissoes.pode(usuario_id, codigo)
            )

    _Permissao.__name__ = f"Permissao_{codigo.replace('.', '_')}"
    return _Permissao
