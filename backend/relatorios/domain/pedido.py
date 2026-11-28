"""A máquina de estados do pedido de relatório e os prazos (spec técnica `relatorios/relatorios-pdf-e-csv`).

Pura: sem framework. Os serviços aplicam as transições pelas funções que revelam a intenção
(`iniciar_geracao`, `concluir`, `falhar`, `expirar`); repetir um pedido expirado ou que falhou é um
pedido novo.
"""

from datetime import datetime, timedelta
from enum import StrEnum


class SituacaoDoPedido(StrEnum):
    NA_FILA = "NA_FILA"
    GERANDO = "GERANDO"
    PRONTO = "PRONTO"
    FALHOU = "FALHOU"
    EXPIRADO = "EXPIRADO"


class Formato(StrEnum):
    PDF = "PDF"
    CSV = "CSV"


class ComandoDoPedido(StrEnum):
    INICIAR_GERACAO = "iniciar_geracao"
    CONCLUIR = "concluir"
    FALHAR = "falhar"
    EXPIRAR = "expirar"


S = SituacaoDoPedido
C = ComandoDoPedido
_TRANSICOES: dict[SituacaoDoPedido, dict[ComandoDoPedido, SituacaoDoPedido]] = {
    S.NA_FILA: {C.INICIAR_GERACAO: S.GERANDO},
    S.GERANDO: {C.CONCLUIR: S.PRONTO, C.FALHAR: S.FALHOU},
    S.PRONTO: {C.EXPIRAR: S.EXPIRADO},
}

EM_ANDAMENTO = frozenset({S.NA_FILA, S.GERANDO})
COM_ARQUIVO = frozenset({S.PRONTO, S.EXPIRADO})
DIAS_DISPONIVEL = 7
MAXIMO_EM_ANDAMENTO = 3
LIMITE_GERANDO = timedelta(hours=1)


class TransicaoInvalida(ValueError):
    pass


def proxima_situacao(atual: SituacaoDoPedido, comando: ComandoDoPedido) -> SituacaoDoPedido:
    try:
        return _TRANSICOES[atual][comando]
    except KeyError:
        raise TransicaoInvalida(f"O pedido em {atual} não aceita {comando}.") from None


def expira_em(concluido_em: datetime) -> datetime:
    """O arquivo fica disponível por 7 dias a partir de quando ficou pronto (Q8, ADR-020)."""
    return concluido_em + timedelta(days=DIAS_DISPONIVEL)


def parado(iniciado_em: datetime, agora: datetime) -> bool:
    """Gerando há mais de uma hora: o worker reiniciou no meio (P29)."""
    return agora - iniciado_em > LIMITE_GERANDO


def pode_pedir_mais(em_andamento: int) -> bool:
    """Até três pedidos na fila ou gerando por usuário (P21)."""
    return em_andamento < MAXIMO_EM_ANDAMENTO
