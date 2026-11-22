"""Parte 13: a visão do caixa conta as cobranças pagas (D-23; adendo 1 da funcional do M7; CA-22, CA-23).

O teste do CA-32 do M7 (`test_parte9_estornos_e_caixa.py`) só usava entrada sem devedor e por isso não pegou
que a cobrança paga ficava fora do total de entradas.
"""

from decimal import Decimal

import pytest

from financeiro import public
from financeiro.tests.apoio_lancamentos import Livro

pytestmark = pytest.mark.django_db


def test_ca22_cobranca_paga_entra_no_total_de_entradas_da_visao_do_caixa() -> None:
    livro = Livro()
    livro.entrada_validada("1000.00")
    livro.cobranca_paga("100.00")

    assert public.visao_do_caixa().total_entradas_validadas == Decimal("1100.00")


def test_ca22_cobranca_paga_e_estornada_sai_do_total() -> None:
    livro = Livro()
    livro.entrada_validada("1000.00")
    paga = livro.cobranca_paga("100.00")

    livro.estornar_cobranca(paga)

    assert public.visao_do_caixa().total_entradas_validadas == Decimal("1000.00")


def test_ca22_cobranca_que_nao_foi_paga_nao_entra() -> None:
    livro = Livro()
    livro.cobranca("10.00")
    em_validacao = livro.cobranca("20.00")
    livro.registrar_pagamento(em_validacao)
    livro.isentar(livro.cobranca("30.00"))
    livro.cancelar(livro.cobranca("40.00"))
    livro.entrada_rejeitada("50.00")
    livro.entrada("60.00")

    assert public.visao_do_caixa().total_entradas_validadas == Decimal("0.00")


def test_ca23_totais_da_visao_iguais_aos_totais_acumulados_e_comprometido_como_antes() -> None:
    livro = Livro()
    livro.entrada_validada("1000.00")
    livro.cobranca_paga("150.00")
    estornada = livro.entrada_validada("70.00")
    livro.estornar_entrada(estornada)
    livro.saida_liquidada("300.00", enviado="200.00", gasto="150.00", devolvido="50.00")
    dobrada = livro.saida_liquidada("200.00")
    livro.estornar_saida(dobrada)
    aberta = livro.saida("500.00")
    livro.enviar(aberta, "100.00")

    visao = public.visao_do_caixa()

    assert visao.total_entradas_validadas == Decimal("1150.00")
    assert visao.total_saidas_liquidadas == Decimal("150.00")
    assert visao.total_comprometido == Decimal("500.00")
