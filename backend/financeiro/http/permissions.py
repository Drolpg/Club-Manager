"""Permissões HTTP das rotas do módulo financeiro (camada de entrada; o serviço também confere)."""

import uuid

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from permissoes import public as permissoes


def _usuario_ativo(request: Request) -> bool:
    autenticado = getattr(request.user, "is_authenticated", False)
    ativo = getattr(request.user, "is_active", False)
    return bool(autenticado and ativo)


def _usuario_id(request: Request) -> uuid.UUID | None:
    if not _usuario_ativo(request):
        return None
    raw_id = getattr(request.user, "id", None)
    if raw_id is None:
        return None
    return uuid.UUID(str(raw_id))


class EhAdmin(BasePermission):
    """Cadastros de categorias e chaves Pix são mantidos apenas pelo admin."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _usuario_ativo(request) and bool(getattr(request.user, "admin", False))


class LeGestao(BasePermission):
    """Admin ou diretor ativo com cargo."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        usuario_id = _usuario_id(request)
        return usuario_id is not None and permissoes.le_gestao(usuario_id)


class DiretorAtivo(BasePermission):
    """Qualquer diretor autenticado e ativo (inclusive sem cargo)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _usuario_ativo(request)


def exige_permissao(codigo: str) -> type[BasePermission]:
    """Permissão DRF que exige admin ou diretor ativo com cargo e a permissão `codigo`."""

    class _Permissao(BasePermission):
        def has_permission(self, request: Request, view: APIView) -> bool:
            usuario_id = _usuario_id(request)
            if usuario_id is None:
                return False
            if getattr(request.user, "admin", False):
                return True
            return permissoes.le_gestao(usuario_id) and permissoes.pode(usuario_id, codigo)

    _Permissao.__name__ = f"Permissao_{codigo.replace('.', '_')}"
    return _Permissao
