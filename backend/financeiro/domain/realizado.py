"""Regras puras do realizado, para o dashboard e os relatórios (`relatorios/dashboard-e-lancamentos`).

Realizado é o que foi validado (entrada) ou liquidado (saída), na data em que isso aconteceu (RN-015, RN-026).
O estorno é um lançamento à parte, na data dele (RN-027). Sem framework: só datas, `Decimal` e as situações.
"""

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from financeiro.domain.saidas import calcular_valor_realizado_saida
from financeiro.domain.transicoes import SituacaoCobranca, SituacaoEntrada, SituacaoSaida


class TipoDeLancamento(StrEnum):
    COBRANCA = "COBRANCA"
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    ESTORNO = "ESTORNO"


class EstadoDoLancamento(StrEnum):
    EM_ABERTO = "EM_ABERTO"
    EM_VALIDACAO = "EM_VALIDACAO"
    REALIZADO = "REALIZADO"
    ENCERRADO_SEM_VALOR = "ENCERRADO_SEM_VALOR"
    ESTORNADO = "ESTORNADO"


_E = EstadoDoLancamento
_ESTADOS: dict[TipoDeLancamento, dict[str, EstadoDoLancamento]] = {
    TipoDeLancamento.COBRANCA: {
        SituacaoCobranca.ABERTA: _E.EM_ABERTO,
        SituacaoCobranca.ATRASADA: _E.EM_ABERTO,
        SituacaoCobranca.EM_VALIDACAO: _E.EM_VALIDACAO,
        SituacaoCobranca.PAGA: _E.REALIZADO,
        SituacaoCobranca.ISENTA: _E.ENCERRADO_SEM_VALOR,
        SituacaoCobranca.CANCELADA: _E.ENCERRADO_SEM_VALOR,
        SituacaoCobranca.PERDOADA: _E.ENCERRADO_SEM_VALOR,
        SituacaoCobranca.RENEGOCIADA: _E.ENCERRADO_SEM_VALOR,
        SituacaoCobranca.ESTORNADA: _E.ESTORNADO,
    },
    TipoDeLancamento.ENTRADA: {
        SituacaoEntrada.EM_VALIDACAO: _E.EM_VALIDACAO,
        SituacaoEntrada.VALIDADA: _E.REALIZADO,
        SituacaoEntrada.REJEITADA: _E.ENCERRADO_SEM_VALOR,
        SituacaoEntrada.ESTORNADA: _E.ESTORNADO,
    },
    TipoDeLancamento.SAIDA: {
        SituacaoSaida.AGUARDANDO_ENVIO: _E.EM_ABERTO,
        SituacaoSaida.RECURSO_ENVIADO: _E.EM_ABERTO,
        SituacaoSaida.EM_CONFERENCIA: _E.EM_ABERTO,
        SituacaoSaida.LIQUIDADA: _E.REALIZADO,
        SituacaoSaida.CANCELADA: _E.ENCERRADO_SEM_VALOR,
        SituacaoSaida.ESTORNADA: _E.ESTORNADO,
    },
}


def estado_comum(tipo: TipoDeLancamento, situacao: str) -> EstadoDoLancamento:
    """O estado comum aos quatro tipos (P10). O estorno é sempre realizado."""
    if tipo == TipoDeLancamento.ESTORNO:
        return EstadoDoLancamento.REALIZADO
    try:
        return _ESTADOS[tipo][situacao]
    except KeyError:
        raise ValueError(f"Situação desconhecida para {tipo}: {situacao!r}.") from None


def situacoes_do_estado(tipo: TipoDeLancamento, estado: EstadoDoLancamento) -> frozenset[str]:
    """As situações de origem de um tipo que dão o estado pedido, para filtrar no banco."""
    if tipo == TipoDeLancamento.ESTORNO:
        return frozenset({""}) if estado == EstadoDoLancamento.REALIZADO else frozenset()
    return frozenset(str(s) for s, e in _ESTADOS[tipo].items() if e == estado)


@dataclass(frozen=True)
class DevolucaoDaSaida:
    valor: Decimal
    situacao: str
    estornada_em: datetime | None = None


def realizado_da_saida(
    *, enviado: Decimal, devolucoes: Iterable[DevolucaoDaSaida], liquidada_em: datetime
) -> Decimal:
    """O valor que saiu do clube, como estava na liquidação (N2).

    Desconta a devolução validada e também a estornada depois da liquidação: estornar uma devolução só é
    possível com a saída fora de `LIQUIDADA`, e o mês da liquidação não pode mudar por isso (RN-027). Mínimo
    zero, como `calcular_valor_realizado_saida`.
    """
    devolvido = sum(
        (
            d.valor
            for d in devolucoes
            if d.situacao == SituacaoEntrada.VALIDADA
            or (d.situacao == SituacaoEntrada.ESTORNADA and d.estornada_em and d.estornada_em > liquidada_em)
        ),
        Decimal("0.00"),
    )
    return calcular_valor_realizado_saida(enviado, devolvido)


def limites_do_mes(ano: int, mes: int) -> tuple[date, date]:
    """O primeiro e o último dia do mês. Mês fora de 1 a 12: `ValueError`."""
    if not 1 <= mes <= 12:
        raise ValueError(f"Mês inválido: {mes}.")
    return date(ano, mes, 1), date(ano, mes, calendar.monthrange(ano, mes)[1])


def limites_do_periodo(de: date, ate: date) -> tuple[date, date]:
    """O período de e até, inclusive. Início depois do fim: `ValueError`."""
    if de > ate:
        raise ValueError("O início do período é depois do fim.")
    return de, ate
