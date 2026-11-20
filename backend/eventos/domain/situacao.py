"""A situação do evento, pela regra de precedência de `domain-events.md` (INV-EVT-01).

As situações das solicitações chegam como texto (os valores de `aprovacoes.public.Situacao`), para o domínio
não importar outro módulo.
"""

from enum import StrEnum


class SituacaoDoEvento(StrEnum):
    EM_APROVACAO = "EM_APROVACAO"
    PUBLICADO = "PUBLICADO"
    RECUSADO = "RECUSADO"
    REALIZADO = "REALIZADO"
    CANCELADO = "CANCELADO"


ENCERRADAS = frozenset({SituacaoDoEvento.REALIZADO, SituacaoDoEvento.CANCELADO})

# A solicitação conta como aprovada também depois de aprovada: em execução ou encerrada.
_APROVADAS = frozenset({"APROVADA", "EM_EXECUCAO", "ENCERRADA"})


def situacao_do_evento(
    *,
    cancelado: bool,
    realizado: bool,
    situacao_da_solicitacao_do_evento: str,
    envolve_custo: bool,
    situacao_do_orcamento: str | None,
) -> SituacaoDoEvento:
    """O primeiro que casar vence: cancelado, realizado, recusado, publicado, em aprovação."""
    if cancelado:
        return SituacaoDoEvento.CANCELADO
    if realizado:
        return SituacaoDoEvento.REALIZADO
    if situacao_da_solicitacao_do_evento == "RECUSADA":
        return SituacaoDoEvento.RECUSADO
    evento_aprovado = situacao_da_solicitacao_do_evento in _APROVADAS
    orcamento_aprovado = situacao_do_orcamento in _APROVADAS
    if evento_aprovado and (not envolve_custo or orcamento_aprovado):
        return SituacaoDoEvento.PUBLICADO
    return SituacaoDoEvento.EM_APROVACAO
