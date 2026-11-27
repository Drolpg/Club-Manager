"""Regras puras dos relatórios: o CSV seguro e a formatação pt-BR (CA-23), o pedido e os parâmetros
(CA-03)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest

from relatorios.domain.csv_seguro import escapar_celula, formatar_para_csv, formatar_para_leitura
from relatorios.domain.documento import TipoDeColuna, Valor
from relatorios.domain.parametros import ParametroInvalido, nenhum, periodo
from relatorios.domain.pedido import (
    ComandoDoPedido,
    SituacaoDoPedido,
    TransicaoInvalida,
    expira_em,
    parado,
    pode_pedir_mais,
    proxima_situacao,
)


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


# O pedido: transições e prazos.

S = SituacaoDoPedido
C = ComandoDoPedido


@pytest.mark.parametrize(
    ("atual", "comando", "nova"),
    [
        (S.NA_FILA, C.INICIAR_GERACAO, S.GERANDO),
        (S.GERANDO, C.CONCLUIR, S.PRONTO),
        (S.GERANDO, C.FALHAR, S.FALHOU),
        (S.PRONTO, C.EXPIRAR, S.EXPIRADO),
    ],
)
def test_transicoes_validas_do_pedido(atual: S, comando: C, nova: S) -> None:
    assert proxima_situacao(atual, comando) == nova


_VALIDAS = {
    (S.NA_FILA, C.INICIAR_GERACAO),
    (S.GERANDO, C.CONCLUIR),
    (S.GERANDO, C.FALHAR),
    (S.PRONTO, C.EXPIRAR),
}


@pytest.mark.parametrize(("atual", "comando"), [(s, c) for s in S for c in C if (s, c) not in _VALIDAS])
def test_transicoes_invalidas_do_pedido(atual: S, comando: C) -> None:
    with pytest.raises(TransicaoInvalida):
        proxima_situacao(atual, comando)


def test_falhou_e_expirado_sao_finais() -> None:
    for comando in C:
        for final in (S.FALHOU, S.EXPIRADO):
            with pytest.raises(TransicaoInvalida):
                proxima_situacao(final, comando)


def test_arquivo_fica_disponivel_por_sete_dias() -> None:
    pronto = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
    assert expira_em(pronto) == datetime(2026, 11, 17, 14, 30, tzinfo=UTC)


def test_gerando_ha_mais_de_uma_hora_esta_parado() -> None:
    inicio = datetime(2026, 11, 10, 14, 0, tzinfo=UTC)
    assert not parado(inicio, inicio + timedelta(hours=1))
    assert parado(inicio, inicio + timedelta(hours=1, seconds=1))


@pytest.mark.parametrize(("em_andamento", "pode"), [(0, True), (2, True), (3, False), (4, False)])
def test_ate_tres_pedidos_em_andamento(em_andamento: int, pode: bool) -> None:
    assert pode_pedir_mais(em_andamento) is pode


# Os parâmetros (CA-03).

HOJE = date(2026, 11, 20)


def test_mes_vira_o_periodo_do_mes() -> None:
    assert periodo({"mes": "2026-02"}, HOJE) == {"de": "2026-02-01", "ate": "2026-02-28"}


def test_mes_corrente_e_aceito() -> None:
    assert periodo({"mes": "2026-11"}, HOJE) == {"de": "2026-11-01", "ate": "2026-11-30"}


def test_intervalo_e_normalizado() -> None:
    assert periodo({"de": "2026-10-05", "ate": "2026-12-31"}, HOJE) == {
        "de": "2026-10-05",
        "ate": "2026-12-31",
    }


@pytest.mark.parametrize(
    ("parametros", "campo"),
    [
        ({"mes": "2026-13"}, "mes"),
        ({"mes": "11/2026"}, "mes"),
        ({"mes": "2026-12"}, "mes"),
        ({"de": "2026-11-10", "ate": "2026-11-01"}, "ate"),
        ({"de": "2026-11-21", "ate": "2026-11-30"}, "de"),
        ({"de": "2026-02-30", "ate": "2026-03-01"}, "de"),
        ({"de": "2026-11-01"}, "de"),
        ({}, "de"),
        ({"mes": "2026-10", "setor": "x"}, "setor"),
    ],
)
def test_periodo_invalido_aponta_o_campo(parametros: dict[str, str], campo: str) -> None:
    with pytest.raises(ParametroInvalido) as erro:
        periodo(parametros, HOJE)
    assert erro.value.campo == campo


def test_tipo_sem_parametros_recusa_qualquer_chave() -> None:
    assert nenhum({}, HOJE) == {}
    with pytest.raises(ParametroInvalido) as erro:
        nenhum({"usuario_id": "outro"}, HOJE)
    assert erro.value.campo == "usuario_id"
