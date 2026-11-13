from acesso import portas
from acesso.models import Usuario
from kernel.errors import BusinessError


def exigir_admin(ator: Usuario) -> None:
    """Na etapa 1, só o admin administra convites e usuários (ACE-R05).

    As rotas já exigem admin; os serviços conferem de novo, para a regra valer por qualquer caminho.
    """
    if not (ator.is_active and ator.admin):
        raise BusinessError("PERMISSION_DENIED", "Só o admin pode fazer isso.", status=403)


def exigir_gerenciar_convites(ator: Usuario) -> None:
    """Convites são do admin, ou de quem a porta de `permissoes` liberar (adendo 1 da ADR-003).

    Usuários, ao contrário, continuam só do admin (`exigir_admin`).
    """
    if not (ator.is_active and portas.pode_gerenciar_convites(ator.id)):
        raise BusinessError(
            "PERMISSION_DENIED", "Você não tem permissão para gerenciar convites.", status=403
        )
