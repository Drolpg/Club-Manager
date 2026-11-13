from acesso.models import Usuario
from kernel.errors import BusinessError


def exigir_admin(ator: Usuario) -> None:
    """Na etapa 1, só o admin administra convites e usuários (ACE-R05).

    As rotas já exigem admin; os serviços conferem de novo, para a regra valer por qualquer caminho.
    """
    if not (ator.is_active and ator.admin):
        raise BusinessError("PERMISSION_DENIED", "Só o admin pode fazer isso.", status=403)
