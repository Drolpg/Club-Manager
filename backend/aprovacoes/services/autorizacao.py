"""Conferências de quem age, escritas sobre as APIs públicas de `acesso` e `permissoes` (adendo 1).

As rotas conferem primeiro; os serviços conferem de novo, porque também são chamados em processo.
"""

import uuid

from acesso import public as acesso
from aprovacoes.domain import decisores
from aprovacoes.domain.decisores import Avaliacao
from kernel.errors import BusinessError
from permissoes import public as permissoes

# Mensagens dos códigos que as funções de decisão devolvem. Os de "quem pode" são 403; os de regra, 422.
_MENSAGENS = {
    decisores.PERMISSION_DENIED: (403, "Você não tem permissão para fazer isso."),
    decisores.SO_O_SOLICITANTE: (403, "Só quem enviou a solicitação pode fazer isso."),
    decisores.SOLICITANTE_NAO_DECIDE: (403, "Quem enviou a solicitação não pode decidi-la."),
    decisores.APROVADOR_NAO_INDICADO: (
        422,
        "Você pode aprovar este tipo de solicitação: indique outro diretor para decidir este pedido.",
    ),
    decisores.APROVADOR_INVALIDO: (
        422,
        "O aprovador indicado precisa ser outro diretor ativo com cargo, e só quem aprovaria o próprio "
        "pedido indica um aprovador.",
    ),
    "NAO_ESTA_EM_ANALISE": (422, "A solicitação não está em análise."),
    "NAO_ESTA_CONTESTADA_NEM_RETIRADA": (422, "Só se reenvia uma solicitação contestada ou retirada."),
    "NAO_ESTA_RECUSADA": (422, "Só se reabre uma solicitação recusada."),
    "NAO_PODE_EDITAR": (422, "Só se edita uma solicitação aprovada, antes de a execução começar."),
    "NAO_PODE_CANCELAR": (422, "Esta solicitação não pode mais ser cancelada."),
    "NAO_ESTA_APROVADA": (422, "A solicitação não está aprovada."),
    "NAO_PODE_ENCERRAR": (422, "Esta solicitação não pode ser encerrada."),
}


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


def erro(codigo: str) -> BusinessError:
    status, mensagem = _MENSAGENS[codigo]
    return BusinessError(codigo, mensagem, status=status)


def exigir(avaliacao: Avaliacao) -> None:
    """Levanta o erro que a função de decisão devolveu, se ela disse que não pode."""
    if not avaliacao.pode:
        raise erro(avaliacao.erro or "PERMISSION_DENIED")
