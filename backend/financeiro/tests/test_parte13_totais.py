"""Parte 13: totais do período, N1 a N8 (spec `relatorios/dashboard-e-lancamentos`, CA-01 a CA-05, CA-20).

Os lançamentos passam pelos serviços do `financeiro`; só o instante da validação, da liquidação ou do estorno
é fixado, para pôr cada valor no mês certo.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from financeiro import public
from financeiro.domain.realizado import DevolucaoDaSaida, realizado_da_saida
from financeiro.models import Saida
from financeiro.tests.apoio_lancamentos import Livro, local

pytestmark = pytest.mark.django_db

OUT = (date(2026, 10, 1), date(2026, 10, 31))
NOV = (date(2026, 11, 1), date(2026, 11, 30))


def test_ca01_entradas_do_mes_somam_cobranca_paga_e_entrada_validada() -> None:
    livro = Livro()
    livro.cobranca_paga("100.00", validada_em=local(2026, 10, 5))
    livro.entrada_validada("1000.00", validada_em=local(2026, 10, 6))
    livro.cobranca("10.00")
    livro.registrar_pagamento(livro.cobranca("20.00"))
    livro.isentar(livro.cobranca("30.00"))
    livro.cancelar(livro.cobranca("40.00"))
    livro.entrada_rejeitada("50.00")
    livro.entrada("60.00")

    totais = public.totais_do_periodo(*OUT)

    assert totais.entradas_realizadas == Decimal("1100.00")
    assert totais.entradas == Decimal("1100.00")
    assert totais.saidas == Decimal("0.00")


def test_ca02_saida_liquidada_conta_enviado_menos_devolvido_e_a_devolucao_nao_e_entrada() -> None:
    livro = Livro()
    livro.saida_liquidada(
        "300.00", enviado="200.00", gasto="150.00", devolvido="50.00", liquidada_em=local(2026, 10, 9)
    )
    livro.saida("80.00")
    enviada = livro.saida("90.00")
    livro.enviar(enviada, "90.00")
    conferencia = livro.saida("70.00")
    livro.enviar(conferencia, "70.00")
    livro.prestar(conferencia, "70.00")

    totais = public.totais_do_periodo(*OUT)

    assert totais.saidas_realizadas == Decimal("150.00")
    assert totais.entradas == Decimal("0.00")


def test_ca02_gasto_acima_do_enviado_nao_reembolsado_nao_conta() -> None:
    livro = Livro()
    livro.saida_liquidada("200.00", enviado="200.00", gasto="240.00", liquidada_em=local(2026, 10, 9))

    assert public.totais_do_periodo(*OUT).saidas_realizadas == Decimal("200.00")


def test_ca03_conta_no_mes_da_validacao_e_no_mes_da_liquidacao() -> None:
    livro = Livro()
    livro.cobranca_paga("100.00", validada_em=local(2026, 11, 2))
    livro.saida_liquidada("300.00", liquidada_em=local(2026, 11, 3))

    assert public.totais_do_periodo(*OUT).resultado == Decimal("0.00")
    novembro = public.totais_do_periodo(*NOV)
    assert novembro.entradas == Decimal("100.00")
    assert novembro.saidas == Decimal("300.00")


def test_r8_validacao_as_23h30_do_ultimo_dia_fica_no_mes() -> None:
    livro = Livro()
    livro.cobranca_paga("100.00", validada_em=local(2026, 10, 31, 23, 30))
    livro.cobranca_paga("7.00", validada_em=local(2026, 11, 1, 0, 0))

    assert public.totais_do_periodo(*OUT).entradas == Decimal("100.00")
    assert public.totais_do_periodo(*NOV).entradas == Decimal("7.00")


def test_ca04_estorno_entra_no_mes_dele_e_o_original_fica_no_seu() -> None:
    livro = Livro()
    entrada = livro.entrada_validada("1000.00", validada_em=local(2026, 10, 5))
    cobranca = livro.cobranca_paga("100.00", validada_em=local(2026, 10, 6))
    saida = livro.saida_liquidada("300.00", liquidada_em=local(2026, 10, 7))
    livro.estornar_entrada(entrada, em=local(2026, 11, 4))
    livro.estornar_cobranca(cobranca, em=local(2026, 11, 5))
    livro.estornar_saida(saida, em=local(2026, 11, 6))

    outubro = public.totais_do_periodo(*OUT)
    assert (outubro.entradas, outubro.saidas) == (Decimal("1100.00"), Decimal("300.00"))
    novembro = public.totais_do_periodo(*NOV)
    assert novembro.entradas_realizadas == Decimal("0.00")
    assert novembro.estornos_de_entrada == Decimal("1100.00")
    assert novembro.entradas == Decimal("-1100.00")
    assert novembro.estornos_de_saida == Decimal("300.00")
    assert novembro.saidas == Decimal("-300.00")
    assert public.saldo_acumulado(date(2026, 11, 30)) == Decimal("0.00")


def test_estorno_de_devolucao_nao_entra_e_nao_muda_o_mes_da_liquidacao() -> None:
    livro = Livro()
    saida = livro.saida("300.00")
    livro.enviar(saida, "200.00")
    livro.prestar(saida, "150.00")
    devolucao = livro.devolver(saida, "50.00")
    saida = livro.liquidar(saida, em=local(2026, 10, 9))
    livro.estornar_saida(saida, em=local(2026, 11, 2))
    livro.estornar_entrada(devolucao, em=local(2026, 11, 3))

    assert public.totais_do_periodo(*OUT).saidas == Decimal("150.00")
    novembro = public.totais_do_periodo(*NOV)
    assert novembro.estornos_de_entrada == Decimal("0.00")
    assert novembro.saidas == Decimal("-150.00")


def test_ca05_saldo_acumulado_e_a_soma_dos_resultados_ate_a_data() -> None:
    livro = Livro()
    livro.entrada_validada("1000.00", validada_em=local(2026, 9, 10))
    livro.saida_liquidada("300.00", liquidada_em=local(2026, 10, 10))
    livro.cobranca_paga("150.00", validada_em=local(2026, 11, 10))

    assert public.saldo_acumulado(date(2026, 9, 30)) == Decimal("1000.00")
    assert public.saldo_acumulado(date(2026, 10, 31)) == Decimal("700.00")
    assert public.saldo_acumulado(date(2026, 11, 30)) == Decimal("850.00")
    assert public.totais_do_periodo(*OUT).resultado == Decimal("-300.00")
    assert public.primeira_data_de_realizacao() == date(2026, 9, 10)


def test_sem_lancamento_tudo_zero_e_sem_primeira_data() -> None:
    totais = public.totais_do_periodo(*NOV)

    assert (totais.entradas, totais.saidas, totais.resultado) == (Decimal("0.00"),) * 3
    assert public.primeira_data_de_realizacao() is None


def test_agregacao_das_saidas_igual_a_funcao_pura() -> None:
    livro = Livro()
    livro.saida_liquidada(
        "300.00", enviado="200.00", gasto="150.00", devolvido="50.00", liquidada_em=local(2026, 10, 3)
    )
    livro.saida_liquidada("200.00", enviado="200.00", gasto="240.00", liquidada_em=local(2026, 10, 4))
    livro.saida_liquidada("120.00", liquidada_em=local(2026, 10, 5))

    esperado = Decimal("0.00")
    for saida in Saida.objects.filter(liquidada_em__isnull=False).prefetch_related("envios", "devolucoes"):
        assert saida.liquidada_em is not None
        devolucoes = [DevolucaoDaSaida(valor=d.valor, situacao=d.situacao) for d in saida.devolucoes.all()]
        enviado = sum((e.valor for e in saida.envios.all()), Decimal("0.00"))
        esperado += realizado_da_saida(
            enviado=enviado, devolucoes=devolucoes, liquidada_em=saida.liquidada_em
        )

    assert public.totais_do_periodo(*OUT).saidas_realizadas == esperado == Decimal("470.00")


def _consultas_dos_totais() -> int:
    with CaptureQueriesContext(connection) as capturadas:
        public.totais_do_periodo(*OUT)
        public.saldo_acumulado(date(2026, 10, 31))
    return len(capturadas)


def test_ca20_numero_de_consultas_nao_cresce_com_os_lancamentos() -> None:
    livro = Livro()
    livro.cobranca_paga("10.00", validada_em=local(2026, 10, 2))
    livro.saida_liquidada("10.00", liquidada_em=local(2026, 10, 2))
    poucas = _consultas_dos_totais()

    for dia in range(3, 6):
        livro.cobranca_paga("10.00", validada_em=local(2026, 10, dia))
        livro.entrada_validada("10.00", validada_em=local(2026, 10, dia))
        livro.saida_liquidada("10.00", liquidada_em=local(2026, 10, dia))

    assert _consultas_dos_totais() == poucas
