"""Regras puras do realizado (spec técnica `relatorios/dashboard-e-lancamentos`, N2, N3 e o estado comum)."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from financeiro.domain.realizado import (
    DevolucaoDaSaida,
    EstadoDoLancamento,
    TipoDeLancamento,
    estado_comum,
    limites_do_mes,
    limites_do_periodo,
    realizado_da_saida,
    situacoes_do_estado,
)

_FUSO = ZoneInfo("America/Sao_Paulo")
_LIQUIDADA_EM = datetime(2026, 10, 20, 15, 0, tzinfo=_FUSO)


def _dev(valor: str, situacao: str, estornada_em: datetime | None = None) -> DevolucaoDaSaida:
    return DevolucaoDaSaida(valor=Decimal(valor), situacao=situacao, estornada_em=estornada_em)


def test_realizado_e_o_enviado_menos_a_devolucao_validada() -> None:
    devolucoes = [_dev("50.00", "VALIDADA"), _dev("30.00", "REJEITADA")]

    valor = realizado_da_saida(enviado=Decimal("200.00"), devolucoes=devolucoes, liquidada_em=_LIQUIDADA_EM)

    assert valor == Decimal("150.00")


def test_devolucao_estornada_depois_da_liquidacao_continua_descontada() -> None:
    depois = datetime(2026, 11, 5, 10, 0, tzinfo=_FUSO)

    valor = realizado_da_saida(
        enviado=Decimal("200.00"), devolucoes=[_dev("50.00", "ESTORNADA", depois)], liquidada_em=_LIQUIDADA_EM
    )

    assert valor == Decimal("150.00")


def test_devolucao_estornada_antes_da_liquidacao_nao_desconta() -> None:
    antes = datetime(2026, 10, 10, 10, 0, tzinfo=_FUSO)

    valor = realizado_da_saida(
        enviado=Decimal("200.00"), devolucoes=[_dev("50.00", "ESTORNADA", antes)], liquidada_em=_LIQUIDADA_EM
    )

    assert valor == Decimal("200.00")


def test_realizado_nunca_fica_negativo_e_gasto_maior_nao_conta() -> None:
    valor = realizado_da_saida(
        enviado=Decimal("50.00"), devolucoes=[_dev("80.00", "VALIDADA")], liquidada_em=_LIQUIDADA_EM
    )

    assert valor == Decimal("0.00")


@pytest.mark.parametrize(
    ("tipo", "situacao", "estado"),
    [
        (TipoDeLancamento.COBRANCA, "ABERTA", EstadoDoLancamento.EM_ABERTO),
        (TipoDeLancamento.COBRANCA, "ATRASADA", EstadoDoLancamento.EM_ABERTO),
        (TipoDeLancamento.COBRANCA, "EM_VALIDACAO", EstadoDoLancamento.EM_VALIDACAO),
        (TipoDeLancamento.COBRANCA, "PAGA", EstadoDoLancamento.REALIZADO),
        (TipoDeLancamento.COBRANCA, "ISENTA", EstadoDoLancamento.ENCERRADO_SEM_VALOR),
        (TipoDeLancamento.COBRANCA, "CANCELADA", EstadoDoLancamento.ENCERRADO_SEM_VALOR),
        (TipoDeLancamento.COBRANCA, "PERDOADA", EstadoDoLancamento.ENCERRADO_SEM_VALOR),
        (TipoDeLancamento.COBRANCA, "RENEGOCIADA", EstadoDoLancamento.ENCERRADO_SEM_VALOR),
        (TipoDeLancamento.COBRANCA, "ESTORNADA", EstadoDoLancamento.ESTORNADO),
        (TipoDeLancamento.ENTRADA, "EM_VALIDACAO", EstadoDoLancamento.EM_VALIDACAO),
        (TipoDeLancamento.ENTRADA, "VALIDADA", EstadoDoLancamento.REALIZADO),
        (TipoDeLancamento.ENTRADA, "REJEITADA", EstadoDoLancamento.ENCERRADO_SEM_VALOR),
        (TipoDeLancamento.ENTRADA, "ESTORNADA", EstadoDoLancamento.ESTORNADO),
        (TipoDeLancamento.SAIDA, "AGUARDANDO_ENVIO", EstadoDoLancamento.EM_ABERTO),
        (TipoDeLancamento.SAIDA, "RECURSO_ENVIADO", EstadoDoLancamento.EM_ABERTO),
        (TipoDeLancamento.SAIDA, "EM_CONFERENCIA", EstadoDoLancamento.EM_ABERTO),
        (TipoDeLancamento.SAIDA, "LIQUIDADA", EstadoDoLancamento.REALIZADO),
        (TipoDeLancamento.SAIDA, "CANCELADA", EstadoDoLancamento.ENCERRADO_SEM_VALOR),
        (TipoDeLancamento.SAIDA, "ESTORNADA", EstadoDoLancamento.ESTORNADO),
    ],
)
def test_estado_comum_de_cada_situacao(
    tipo: TipoDeLancamento, situacao: str, estado: EstadoDoLancamento
) -> None:
    assert estado_comum(tipo, situacao) == estado
    assert situacao in situacoes_do_estado(tipo, estado)


def test_estorno_e_sempre_realizado() -> None:
    assert estado_comum(TipoDeLancamento.ESTORNO, "") == EstadoDoLancamento.REALIZADO
    assert situacoes_do_estado(TipoDeLancamento.ESTORNO, EstadoDoLancamento.EM_ABERTO) == frozenset()


def test_situacao_desconhecida_e_recusada() -> None:
    with pytest.raises(ValueError, match="Situação desconhecida"):
        estado_comum(TipoDeLancamento.COBRANCA, "INVENTADA")


@pytest.mark.parametrize(
    ("ano", "mes", "esperado"),
    [
        (2026, 11, (date(2026, 11, 1), date(2026, 11, 30))),
        (2028, 2, (date(2028, 2, 1), date(2028, 2, 29))),
        (2026, 12, (date(2026, 12, 1), date(2026, 12, 31))),
    ],
)
def test_limites_do_mes(ano: int, mes: int, esperado: tuple[date, date]) -> None:
    assert limites_do_mes(ano, mes) == esperado


def test_limites_do_mes_invalido() -> None:
    with pytest.raises(ValueError, match="Mês inválido"):
        limites_do_mes(2026, 13)


def test_limites_do_periodo_confere_a_ordem() -> None:
    assert limites_do_periodo(date(2026, 12, 30), date(2027, 1, 2)) == (date(2026, 12, 30), date(2027, 1, 2))
    with pytest.raises(ValueError, match="depois do fim"):
        limites_do_periodo(date(2027, 1, 2), date(2026, 12, 30))
