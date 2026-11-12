"""Situação de um convite (regra 2 da especificação funcional).

A situação não é gravada: é sempre calculada dos fatos do convite e da hora atual. Por isso a expiração é
exata e não depende de tarefa agendada.
"""

from datetime import datetime, timedelta
from enum import StrEnum

VALIDADE = timedelta(hours=24)


class SituacaoDoConvite(StrEnum):
    ATIVO = "ATIVO"
    USADO = "USADO"
    EXPIRADO = "EXPIRADO"
    REVOGADO = "REVOGADO"


def situacao_do_convite(
    *, agora: datetime, expira_em: datetime, usado_em: datetime | None, revogado_em: datetime | None
) -> SituacaoDoConvite:
    """O primeiro caso que casar vence: usado, revogado, expirado, ativo."""
    if usado_em is not None:
        return SituacaoDoConvite.USADO
    if revogado_em is not None:
        return SituacaoDoConvite.REVOGADO
    if agora >= expira_em:
        return SituacaoDoConvite.EXPIRADO
    return SituacaoDoConvite.ATIVO
