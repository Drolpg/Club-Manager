from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from permissoes.services import consulta


def _usuario_ativo(request: Request) -> bool:
    return bool(getattr(request.user, "is_active", False))


class EhAdmin(BasePermission):
    """Cargos, setores, classificação e concessões são administrados só pelo admin (PER-R09)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _usuario_ativo(request) and bool(getattr(request.user, "admin", False))


class LeGestao(BasePermission):
    """Admin, ou diretor ativo com cargo (PER-R10)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        usuario_id = getattr(request.user, "id", None)
        return _usuario_ativo(request) and usuario_id is not None and consulta.le_gestao(usuario_id)
