"""Permissão HTTP das rotas do perfil: só a sessão ativa. "Dono ou admin" é do serviço (D4)."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class UsuarioAtivo(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        usuario = request.user
        return bool(getattr(usuario, "is_authenticated", False) and getattr(usuario, "is_active", False))
