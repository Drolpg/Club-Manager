"""Regras puras de estados, transições e contagem de prazos de cobrança e entrada."""

from datetime import date, timedelta
from enum import StrEnum


class SituacaoCobranca(StrEnum):
    ABERTA = "ABERTA"
    EM_VALIDACAO = "EM_VALIDACAO"
    ATRASADA = "ATRASADA"
    PAGA = "PAGA"
    ISENTA = "ISENTA"
    CANCELADA = "CANCELADA"
    PERDOADA = "PERDOADA"
    RENEGOCIADA = "RENEGOCIADA"
    ESTORNADA = "ESTORNADA"


SITUACOES_FINAIS_COBRANCA = frozenset(
    {
        SituacaoCobranca.PAGA,
        SituacaoCobranca.ISENTA,
        SituacaoCobranca.CANCELADA,
        SituacaoCobranca.PERDOADA,
        SituacaoCobranca.RENEGOCIADA,
        SituacaoCobranca.ESTORNADA,
    }
)


class ComandoCobranca(StrEnum):
    REGISTRAR_PAGAMENTO = "registrar_pagamento"
    VALIDAR_PAGAMENTO = "validar_pagamento"
    REJEITAR_PAGAMENTO = "rejeitar_pagamento"
    MARCAR_ATRASO = "marcar_atraso"
    QUESTIONAR = "questionar"
    DECIDIR_QUESTIONAMENTO = "decidir_questionamento"
    ISENTAR = "isentar"
    CANCELAR = "cancelar"
    CONVOCAR = "convocar"
    JUSTIFICAR_DIVIDA = "justificar_divida"
    PERDOAR = "perdoar"
    RENEGOCIAR = "renegociar"
    MANTER_DIVIDA = "manter_divida"
    ESTORNAR = "estornar"


_TRANSICOES_COBRANCA: dict[SituacaoCobranca, frozenset[ComandoCobranca]] = {
    SituacaoCobranca.ABERTA: frozenset(
        {
            ComandoCobranca.REGISTRAR_PAGAMENTO,
            ComandoCobranca.MARCAR_ATRASO,
            ComandoCobranca.QUESTIONAR,
            ComandoCobranca.DECIDIR_QUESTIONAMENTO,
            ComandoCobranca.ISENTAR,
            ComandoCobranca.CANCELAR,
        }
    ),
    SituacaoCobranca.ATRASADA: frozenset(
        {
            ComandoCobranca.REGISTRAR_PAGAMENTO,
            ComandoCobranca.QUESTIONAR,
            ComandoCobranca.DECIDIR_QUESTIONAMENTO,
            ComandoCobranca.ISENTAR,
            ComandoCobranca.CANCELAR,
            ComandoCobranca.CONVOCAR,
            ComandoCobranca.JUSTIFICAR_DIVIDA,
            ComandoCobranca.PERDOAR,
            ComandoCobranca.RENEGOCIAR,
            ComandoCobranca.MANTER_DIVIDA,
        }
    ),
    SituacaoCobranca.EM_VALIDACAO: frozenset(
        {
            ComandoCobranca.VALIDAR_PAGAMENTO,
            ComandoCobranca.REJEITAR_PAGAMENTO,
        }
    ),
    SituacaoCobranca.PAGA: frozenset({ComandoCobranca.ESTORNAR}),
}


def transicao_cobranca_permitida(situacao: SituacaoCobranca, comando: ComandoCobranca) -> bool:
    """Informa se a situação atual da cobrança aceita o comando (INV-COB-02)."""
    return comando in _TRANSICOES_COBRANCA.get(situacao, frozenset())


def estado_sem_pagamento(vencimento: date, hoje: date) -> SituacaoCobranca:
    """Situação para onde a cobrança volta após rejeição de pagamento (INV-COB-07)."""
    return SituacaoCobranca.ATRASADA if vencimento < hoje else SituacaoCobranca.ABERTA


def dias_pausados_em_decisao(pausada_em: date | None, vencimento: date, hoje: date) -> int:
    """Dias a somar na pausa de inadimplência ao manter um questionamento (Regra 11)."""
    if pausada_em is None:
        return 0
    inicio_pausa = max(pausada_em, vencimento)
    return max(0, (hoje - inicio_pausa).days)


def data_limite_convocacao(vencimento: date, limite_dias: int, dias_pausados: int) -> date:
    """Última data antes da qual o devedor ainda está dentro do limite de inadimplência."""
    return vencimento + timedelta(days=limite_dias + dias_pausados)


class SituacaoEntrada(StrEnum):
    EM_VALIDACAO = "EM_VALIDACAO"
    VALIDADA = "VALIDADA"
    REJEITADA = "REJEITADA"
    ESTORNADA = "ESTORNADA"


class ComandoEntrada(StrEnum):
    VALIDAR = "validar"
    REJEITAR = "rejeitar"
    ESTORNAR = "estornar"


_TRANSICOES_ENTRADA: dict[SituacaoEntrada, frozenset[ComandoEntrada]] = {
    SituacaoEntrada.EM_VALIDACAO: frozenset({ComandoEntrada.VALIDAR, ComandoEntrada.REJEITAR}),
    SituacaoEntrada.VALIDADA: frozenset({ComandoEntrada.ESTORNAR}),
}


def transicao_entrada_permitida(situacao: SituacaoEntrada, comando: ComandoEntrada) -> bool:
    """Entrada recebe decisão em validação e só pode ser estornada depois de validada."""
    return comando in _TRANSICOES_ENTRADA.get(situacao, frozenset())


class SituacaoSaida(StrEnum):
    AGUARDANDO_ENVIO = "AGUARDANDO_ENVIO"
    RECURSO_ENVIADO = "RECURSO_ENVIADO"
    EM_CONFERENCIA = "EM_CONFERENCIA"
    LIQUIDADA = "LIQUIDADA"
    CANCELADA = "CANCELADA"
    ESTORNADA = "ESTORNADA"


SITUACOES_FINAIS_SAIDA = frozenset(
    {
        SituacaoSaida.LIQUIDADA,
        SituacaoSaida.CANCELADA,
        SituacaoSaida.ESTORNADA,
    }
)
SITUACOES_ATIVAS_SAIDA = frozenset(
    {
        SituacaoSaida.AGUARDANDO_ENVIO,
        SituacaoSaida.RECURSO_ENVIADO,
        SituacaoSaida.EM_CONFERENCIA,
    }
)


class ComandoSaida(StrEnum):
    ENVIAR_RECURSO = "enviar_recurso"
    PRESTAR_CONTAS = "prestar_contas"
    DEVOLVER_PRESTACAO = "devolver_prestacao"
    DEVOLVER_SOBRA = "devolver_sobra"
    PEDIR_COMPLEMENTO = "pedir_complemento"
    LIQUIDAR = "liquidar"
    CANCELAR = "cancelar"
    ESTORNAR = "estornar"


_TRANSICOES_SAIDA: dict[SituacaoSaida, frozenset[ComandoSaida]] = {
    SituacaoSaida.AGUARDANDO_ENVIO: frozenset({ComandoSaida.ENVIAR_RECURSO, ComandoSaida.CANCELAR}),
    SituacaoSaida.RECURSO_ENVIADO: frozenset(
        {
            ComandoSaida.ENVIAR_RECURSO,
            ComandoSaida.PRESTAR_CONTAS,
            ComandoSaida.DEVOLVER_SOBRA,
        }
    ),
    SituacaoSaida.EM_CONFERENCIA: frozenset(
        {
            ComandoSaida.ENVIAR_RECURSO,
            ComandoSaida.DEVOLVER_PRESTACAO,
            ComandoSaida.DEVOLVER_SOBRA,
            ComandoSaida.PEDIR_COMPLEMENTO,
            ComandoSaida.LIQUIDAR,
        }
    ),
    SituacaoSaida.LIQUIDADA: frozenset({ComandoSaida.ESTORNAR}),
}


def transicao_saida_permitida(situacao: SituacaoSaida, comando: ComandoSaida) -> bool:
    """Informa se a situação atual da saída aceita o comando (INV-SAI-07, INV-SAI-08)."""
    return comando in _TRANSICOES_SAIDA.get(situacao, frozenset())
