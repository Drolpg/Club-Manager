from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from acesso.models import Usuario
from kernel import rate_limit
from kernel.errors import BusinessError
from kernel.http import client_ip

# Rotas abertas de escrita: 20 requisições por minuto por IP (technical-spec, "Limites").
_LIMITE_POR_IP = 20
_JANELA_POR_IP = 60


class EhAdmin(BasePermission):
    """Na etapa 1, convites e usuários são administrados só pelo admin. O serviço confere de novo."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.user, Usuario) and request.user.is_active and request.user.admin


def limitar_por_ip(request: Request) -> None:
    """Conta a requisição e recusa quando o IP passa do limite das rotas abertas."""
    ip = client_ip(request._request)
    if rate_limit.exceeded("rotas-abertas", ip, limit=_LIMITE_POR_IP):
        raise BusinessError(
            "MUITAS_TENTATIVAS", "Muitas tentativas. Espere um minuto e tente de novo.", status=429
        )
    rate_limit.hit("rotas-abertas", ip, window=_JANELA_POR_IP)
