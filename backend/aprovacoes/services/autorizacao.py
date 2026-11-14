"""Conferências de quem age, escritas sobre as APIs públicas de `acesso` e `permissoes` (adendo 1).

As rotas conferem primeiro; os serviços conferem de novo, porque também são chamados em processo.
"""

import uuid

from acesso import public as acesso
from kernel.errors import BusinessError
from permissoes import public as permissoes


def negado(mensagem: str = "Você não tem permissão para fazer isso.") -> BusinessError:
    return BusinessError("PERMISSION_DENIED", mensagem, status=403)


def e_admin(usuario_id: uuid.UUID) -> bool:
    usuario = acesso.usuario_por_id(usuario_id)
    return usuario is not None and usuario.ativo and usuario.admin


def exigir_admin(ator_id: uuid.UUID) -> None:
    if not e_admin(ator_id):
        raise negado("Só o admin pode fazer isso.")


def exigir_leitura_de_gestao(ator_id: uuid.UUID) -> None:
    """Admin ativo, ou ativo com cargo ativo (PER-R10; regra 18 da spec funcional)."""
    if not permissoes.le_gestao(ator_id):
        raise negado()
