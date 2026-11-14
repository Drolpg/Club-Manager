"""Os códigos de erro do motor e as mensagens deles. Os de "quem pode" são 403; os de regra, 422.

Os códigos são contrato com os clientes (technical-spec, tabela de erros, e o adendo 1 dela) e não mudam.
"""

from aprovacoes.domain import decisores
from kernel.errors import BusinessError

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
    "TETO_SEM_VALOR": (422, "Só se sugere teto numa solicitação que tem valor."),
}


def erro(codigo: str) -> BusinessError:
    status, mensagem = _MENSAGENS[codigo]
    return BusinessError(codigo, mensagem, status=status)
