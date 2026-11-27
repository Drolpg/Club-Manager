"""Regras puras dos relatórios: o CSV seguro e a formatação em pt-BR (CA-23)."""

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest

from relatorios.domain.csv_seguro import escapar_celula, formatar_para_csv, formatar_para_leitura
from relatorios.domain.documento import TipoDeColuna, Valor


@pytest.mark.parametrize("texto", ["=1+1", "+55 11", "-2", "@SOMA(A1)", "\tcomeça com tab", "\rretorno"])
def test_texto_que_vira_formula_ganha_apostrofo(texto: str) -> None:
    assert escapar_celula(texto) == "'" + texto


@pytest.mark.parametrize("texto", ["Mensalidade", "", " =depois de espaço", "Pix 50"])
def test_texto_comum_nao_muda(texto: str) -> None:
    assert escapar_celula(texto) == texto


@pytest.mark.parametrize(
    ("valor", "tipo", "esperado"),
    [
        (Decimal("1234.50"), TipoDeColuna.DINHEIRO, "1234,50"),
        (Decimal("-150.00"), TipoDeColuna.DINHEIRO, "-150,00"),
        (Decimal("0"), TipoDeColuna.DINHEIRO, "0,00"),
        (date(2026, 11, 5), TipoDeColuna.DATA, "05/11/2026"),
        (7, TipoDeColuna.INTEIRO, "7"),
        (True, TipoDeColuna.SIM_NAO, "sim"),
        (False, TipoDeColuna.SIM_NAO, "não"),
        ("=HIPERLINK()", TipoDeColuna.TEXTO, "'=HIPERLINK()"),
        (None, TipoDeColuna.DINHEIRO, ""),
    ],
)
def test_formatacao_para_csv(valor: Valor, tipo: TipoDeColuna, esperado: str) -> None:
    assert formatar_para_csv(valor, tipo) == esperado


@pytest.mark.parametrize(
    ("valor", "tipo", "esperado"),
    [
        (Decimal("1234567.5"), TipoDeColuna.DINHEIRO, "R$ 1.234.567,50"),
        (Decimal("-100.00"), TipoDeColuna.DINHEIRO, "-R$ 100,00"),
        (date(2026, 1, 9), TipoDeColuna.DATA, "09/01/2026"),
        ("=1+1", TipoDeColuna.TEXTO, "=1+1"),
        (None, TipoDeColuna.TEXTO, "—"),
    ],
)
def test_formatacao_para_leitura(valor: Valor, tipo: TipoDeColuna, esperado: str) -> None:
    assert formatar_para_leitura(valor, tipo) == esperado


def test_dinheiro_nunca_passa_por_ponto_flutuante() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        formatar_para_csv(cast(Any, 1234.5), TipoDeColuna.DINHEIRO)
