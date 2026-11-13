import uuid

from acesso import public as acesso
from kernel.errors import BusinessError


def exigir_admin(ator_id: uuid.UUID) -> None:
    """Só o admin altera cargos, setores, classificação e concessões (PER-R09).

    O acesso total não dá isto. As rotas já exigem admin; os serviços conferem de novo.
    """
    ator = acesso.usuario_por_id(ator_id)
    if ator is None or not (ator.ativo and ator.admin):
        raise BusinessError("PERMISSION_DENIED", "Só o admin pode fazer isso.", status=403)
