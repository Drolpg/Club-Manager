"""O serviço do dashboard (CA-06, CA-08 a CA-13, CA-20): completo e básico, só leitura.

Banco real. Os lançamentos são criados pela API HTTP do `financeiro` (`apoio_dashboard.py`), e os números
vêm das consultas públicas dos módulos donos.
"""

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from comunicacao import public as comunicacao
from eventos import public as eventos
from financeiro import public as financeiro
from kernel.errors import BusinessError
from relatorios.services import dashboard
from relatorios.tests.apoio_dashboard import Clube, diretor, local
from tests import apoio
from tests.apoio import Situacao

pytestmark = pytest.mark.django_db


def _mes_passado(hoje: date) -> date:
    return (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)


def _no_dia(dia: date, hora: int = 12) -> Any:
    return local(dia.year, dia.month, dia.day, hora)


@pytest.fixture
def clube(db: None) -> Clube:
    return Clube()


@pytest.fixture
def hoje() -> date:
    return timezone.localdate()


def _completo(resultado: Any) -> dashboard.DashboardCompleto:
    assert isinstance(resultado, dashboard.DashboardCompleto)
    return resultado


def test_ca09_e_ca13_completo_com_os_numeros_do_mes_e_de_hoje(clube: Clube, hoje: date) -> None:
    passado = _mes_passado(hoje)
    clube.entrada_validada("1000.00", validada_em=_no_dia(passado.replace(day=5)))
    clube.cobranca_paga("100.00", validada_em=_no_dia(hoje, hora=0))
    clube.saida_liquidada("300.00", liquidada_em=_no_dia(hoje, hora=0))
    aberta = clube.saida("500.00")
    clube.enviar(aberta, "200.00")
    clube.registrar_pagamento(clube.cobranca("80.00"))

    painel = _completo(dashboard.dashboard(clube.fin.id))

    assert painel.mes == hoje.replace(day=1)
    assert (painel.do_mes.entradas, painel.do_mes.saidas) == (Decimal("100.00"), Decimal("300.00"))
    assert painel.do_mes.resultado == Decimal("-200.00")
    assert painel.do_mes.saldo_acumulado == Decimal("800.00")
    assert painel.hoje.comprometido == Decimal("500.00")
    assert painel.hoje.saldo_livre == Decimal("300.00")
    assert painel.hoje.pendencias_de_validacao.pagamentos.total == Decimal("80.00")
    assert painel.hoje.prestacoes_pendentes.aguardando == 1
    assert (painel.primeiro_mes, painel.ultimo_mes) == (passado, hoje.replace(day=1))
    assert painel.minhas_cobrancas.em_aberto.quantidade == 0


def test_ca06_comprometido_e_o_da_visao_do_caixa(clube: Clube) -> None:
    clube.saida("400.00")
    clube.cobranca_paga("50.00")

    painel = _completo(dashboard.dashboard(clube.fin.id))

    caixa = financeiro.visao_do_caixa()
    assert painel.hoje.comprometido == caixa.total_comprometido == Decimal("400.00")
    assert (
        painel.hoje.saldo_livre
        == caixa.total_entradas_validadas - caixa.total_saidas_liquidadas - Decimal("400.00")
    )


def test_ca09_o_mes_escolhido_muda_so_os_numeros_do_mes(clube: Clube, hoje: date) -> None:
    passado = _mes_passado(hoje)
    clube.entrada_validada("1000.00", validada_em=_no_dia(passado.replace(day=10)))
    clube.cobranca_paga("100.00", validada_em=_no_dia(hoje, hora=0))

    corrente = _completo(dashboard.dashboard(clube.fin.id))
    anterior = _completo(dashboard.dashboard(clube.fin.id, passado.strftime("%Y-%m")))

    assert anterior.mes == passado
    assert anterior.do_mes.entradas == Decimal("1000.00")
    assert anterior.do_mes.saldo_acumulado == Decimal("1000.00")
    assert corrente.do_mes.saldo_acumulado == Decimal("1100.00")
    assert anterior.hoje == corrente.hoje
    assert anterior.proximos_eventos == corrente.proximos_eventos
    assert anterior.ultimos_comunicados == corrente.ultimos_comunicados


def test_ca10_mes_sem_lancamento_e_anterior_ao_primeiro_mostram_zeros(clube: Clube, hoje: date) -> None:
    painel = _completo(dashboard.dashboard(clube.fin.id, "2020-01"))

    assert painel.mes == date(2020, 1, 1)
    assert (painel.do_mes.entradas, painel.do_mes.saidas, painel.do_mes.resultado) == (Decimal("0.00"),) * 3
    assert painel.do_mes.saldo_acumulado == Decimal("0.00")
    assert painel.primeiro_mes == hoje.replace(day=1)


@pytest.mark.parametrize("mes", ["2026-13", "2026-00", "novembro", "2026-1", "2026-11-01"])
def test_ca10_mes_invalido_e_recusado(clube: Clube, mes: str) -> None:
    with pytest.raises(BusinessError) as excecao:
        dashboard.dashboard(clube.fin.id, mes)

    assert excecao.value.code == "VALIDATION_ERROR"
    assert "mes" in excecao.value.details


def test_ca10_mes_futuro_e_recusado(clube: Clube, hoje: date) -> None:
    seguinte = (hoje.replace(day=28) + timedelta(days=5)).strftime("%Y-%m")

    with pytest.raises(BusinessError) as excecao:
        dashboard.dashboard(clube.fin.id, seguinte)

    assert excecao.value.code == "VALIDATION_ERROR"


def test_ca09_admin_ve_o_completo(clube: Clube) -> None:
    assert isinstance(dashboard.dashboard(clube.admin.id), dashboard.DashboardCompleto)


@pytest.fixture
def espioes() -> Iterator[dict[str, mock.MagicMock]]:
    alvos = {
        "totais": (financeiro, "totais_do_periodo"),
        "saldo": (financeiro, "saldo_acumulado"),
        "caixa": (financeiro, "visao_do_caixa"),
        "inadimplencia": (financeiro, "resumo_da_inadimplencia"),
        "eventos": (eventos, "proximos_eventos"),
        "comunicados": (comunicacao, "ultimos_comunicados"),
    }
    patches = {nome: mock.patch.object(m, f, wraps=getattr(m, f)) for nome, (m, f) in alvos.items()}
    espias = {nome: p.start() for nome, p in patches.items()}
    yield espias
    for p in patches.values():
        p.stop()


def test_ca11_basico_so_com_o_que_e_do_usuario_e_sem_consultar_o_clube(
    clube: Clube, espioes: dict[str, mock.MagicMock]
) -> None:
    sem_cargo = apoio.criar_diretor("sem.cargo.dash")
    clube.cobranca_paga("100.00")
    clube.registrar_pagamento(clube.cobranca("30.00", devedor=sem_cargo), devedor=sem_cargo)
    clube.cobranca("20.00", devedor=sem_cargo)

    painel = dashboard.dashboard(sem_cargo.id, "2020-01")

    assert isinstance(painel, dashboard.DashboardBasico)
    assert painel.minhas_cobrancas.em_aberto.total == Decimal("20.00")
    assert painel.minhas_cobrancas.em_validacao.total == Decimal("30.00")
    assert painel.notificacoes_nao_lidas >= 1
    for espiao in espioes.values():
        espiao.assert_not_called()


def test_usuario_desativado_e_negado(clube: Clube) -> None:
    desativado = apoio.criar_diretor("desativado.dash", Situacao.INATIVO)

    with pytest.raises(BusinessError) as excecao:
        dashboard.dashboard(desativado.id)

    assert excecao.value.code == "PERMISSION_DENIED"


def _consultas(usuario_id: Any) -> int:
    with CaptureQueriesContext(connection) as capturadas:
        dashboard.dashboard(usuario_id)
    return len(capturadas)


def test_ca20_consultas_do_dashboard_nao_crescem_com_os_lancamentos(clube: Clube) -> None:
    leitor = diretor("leitor.dash")
    # Um lançamento de cada tipo já na primeira massa: com zero linhas o `prefetch_related` não consulta, e a
    # diferença seria de zero para um, e não de poucos para muitos.
    clube.cobranca_paga("10.00")
    clube.entrada_validada("10.00")
    clube.saida_liquidada("10.00")
    clube.saida("5.00")
    poucas = _consultas(leitor.id)

    for _ in range(3):
        clube.cobranca_paga("10.00")
        clube.entrada_validada("10.00")
        clube.saida_liquidada("10.00")
        clube.saida("5.00")

    assert _consultas(leitor.id) == poucas
