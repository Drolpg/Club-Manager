"""Parte 15: consultas para os relatórios (spec `relatorios/relatorios-pdf-e-csv`, "Fontes de cada relatório";
CA-16 a CA-21).

Só leitura, só dataclasses, sem conferir quem pergunta (é do catálogo de `relatorios`). As regras são as dos
totais do dashboard (N1 a N15): o mesmo período dá os mesmos números.
"""

import dataclasses
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from financeiro import public
from financeiro.models import Cobranca, Saida
from financeiro.services import inadimplencia, pagamentos, questionamentos, rotina_diaria, saidas
from financeiro.tests.apoio_lancamentos import Livro, _pdf, local, no_instante
from financeiro.tests.conftest import conceder_permissoes, novo_diretor
from kernel.dinheiro import Dinheiro

pytestmark = pytest.mark.django_db

OUT = (date(2026, 10, 1), date(2026, 10, 31))
ZERO = Decimal("0.00")


def _cobranca_em(livro: Livro, valor: str, vencimento: date, **extra: object) -> Cobranca:
    """Cobrança criada 15 dias antes do vencimento fixo: o teste não depende de hoje."""
    criada = vencimento - timedelta(days=15)
    with no_instante(local(criada.year, criada.month, criada.day, 8)):
        return livro.cobranca(valor, vencimento=vencimento, **extra)  # type: ignore[arg-type]


def _atrasada(
    livro: Livro, valor: str, *, devedor: object = None, vencimento: date = date(2026, 10, 10)
) -> Cobranca:
    cobranca = _cobranca_em(livro, valor, vencimento, devedor=devedor)
    rotina_diaria.executar(vencimento + timedelta(days=1))
    cobranca.refresh_from_db()
    assert cobranca.situacao == "ATRASADA"
    return cobranca


# Extrato: lançamentos realizados (CA-16) -----------------------------------------------------------------


def test_ca16_linhas_sao_os_realizados_do_periodo_pela_data_de_realizacao() -> None:
    livro = Livro()
    with no_instante(local(2026, 9, 28)):
        cobranca = livro.cobranca("100.00", vencimento=date(2026, 10, 5), descricao="Mensalidade de outubro")
        livro.registrar_pagamento(cobranca)
    with no_instante(local(2026, 10, 3, 9)):
        pagamentos.validar(livro.validador.id, cobranca.id, motivo_id=livro.m_val_p)
    entrada = livro.entrada_validada("1000.00", validada_em=local(2026, 10, 2, 15))
    saida = livro.saida_liquidada("300.00", liquidada_em=local(2026, 10, 20))
    livro.cobranca_paga("7.00", validada_em=local(2026, 11, 1, 0, 1))
    livro.entrada("55.00")

    linhas = public.lancamentos_realizados(*OUT)

    assert [(linha.tipo, linha.realizado_em) for linha in linhas] == [
        ("ENTRADA", date(2026, 10, 2)),
        ("COBRANCA", date(2026, 10, 3)),
        ("SAIDA", date(2026, 10, 20)),
    ]
    entrada_l, cobranca_l, saida_l = linhas
    assert (entrada_l.lado, entrada_l.valor, entrada_l.contraparte) == (
        "ENTRADA",
        Decimal("1000.00"),
        "Patrocinador",
    )
    assert entrada_l.data_do_fato == entrada.data
    assert entrada_l.categoria == "Patrocínio"
    assert (cobranca_l.descricao, cobranca_l.contraparte) == ("Mensalidade de outubro", livro.devedor.nome)
    assert cobranca_l.data_do_fato == date(2026, 9, 28)
    assert (saida_l.lado, saida_l.valor, saida_l.setor) == ("SAIDA", Decimal("300.00"), saida.setor_nome)
    assert saida_l.contraparte == f"{livro.solicitante.nome} — {saida.setor_nome}"
    assert saida.primeiro_envio_em is not None
    assert saida_l.data_do_fato == timezone.localdate(saida.primeiro_envio_em)


def test_ca16_estorno_entra_na_data_dele_com_sinal_negativo_no_lado_do_original() -> None:
    livro = Livro()
    entrada = livro.entrada_validada("1000.00", validada_em=local(2026, 9, 5))
    saida = livro.saida_liquidada("300.00", liquidada_em=local(2026, 9, 7))
    livro.estornar_entrada(entrada, em=local(2026, 10, 4))
    livro.estornar_saida(saida, em=local(2026, 10, 6))

    linhas = public.lancamentos_realizados(*OUT)

    assert [(linha.tipo, linha.lado, linha.valor, linha.realizado_em) for linha in linhas] == [
        ("ESTORNO", "ENTRADA", Decimal("-1000.00"), date(2026, 10, 4)),
        ("ESTORNO", "SAIDA", Decimal("-300.00"), date(2026, 10, 6)),
    ]
    assert linhas[0].descricao == "Estorno de: Patrocinador"


def test_ca16_as_linhas_somam_as_entradas_e_as_saidas_do_periodo() -> None:
    livro = Livro()
    livro.cobranca_paga("100.00", validada_em=local(2026, 10, 5))
    entrada = livro.entrada_validada("1000.00", validada_em=local(2026, 10, 6))
    livro.saida_liquidada(
        "300.00", enviado="200.00", gasto="150.00", devolvido="50.00", liquidada_em=local(2026, 10, 9)
    )
    livro.estornar_entrada(entrada, em=local(2026, 10, 25))

    linhas = public.lancamentos_realizados(*OUT)
    totais = public.totais_do_periodo(*OUT)

    assert sum((linha.valor for linha in linhas if linha.lado == "ENTRADA"), ZERO) == totais.entradas
    assert sum((linha.valor for linha in linhas if linha.lado == "SAIDA"), ZERO) == totais.saidas
    assert len(linhas) == 4


def test_ca16_estorno_de_devolucao_nao_aparece() -> None:
    livro = Livro()
    saida = livro.saida("300.00")
    livro.enviar(saida, "200.00")
    livro.prestar(saida, "150.00")
    devolucao = livro.devolver(saida, "50.00")
    saida = livro.liquidar(saida, em=local(2026, 9, 9))
    livro.estornar_saida(saida, em=local(2026, 10, 2))
    livro.estornar_entrada(devolucao, em=local(2026, 10, 3))

    linhas = public.lancamentos_realizados(*OUT)

    assert [(linha.lado, linha.valor) for linha in linhas] == [("SAIDA", Decimal("-150.00"))]


# Balancete (CA-17) -------------------------------------------------------------------------------------


def test_ca17_balancete_por_categoria_e_setor_fecha_com_os_totais() -> None:
    livro = Livro()
    livro.cobranca_paga("100.00", validada_em=local(2026, 10, 5))
    entrada = livro.entrada_validada("1000.00", validada_em=local(2026, 9, 6))
    livro.saida_liquidada("300.00", liquidada_em=local(2026, 10, 9))
    livro.estornar_entrada(entrada, em=local(2026, 10, 25))

    balancete = public.balancete(*OUT)

    por_nome = {linha.nome: linha for linha in balancete.entradas}
    assert (por_nome["Mensalidade"].realizado, por_nome["Mensalidade"].estornos) == (Decimal("100.00"), ZERO)
    assert (por_nome["Patrocínio"].realizado, por_nome["Patrocínio"].estornos) == (ZERO, Decimal("1000.00"))
    assert por_nome["Patrocínio"].liquido == Decimal("-1000.00")
    [arbitragem] = balancete.saidas
    assert (arbitragem.nome, arbitragem.liquido) == ("Arbitragem", Decimal("300.00"))
    [setor] = balancete.saidas_por_setor
    assert setor.nome == livro.setor.nome
    totais = public.totais_do_periodo(*OUT)
    assert balancete.totais == totais
    assert sum((linha.liquido for linha in balancete.entradas), ZERO) == totais.entradas
    assert sum((linha.liquido for linha in balancete.saidas), ZERO) == totais.saidas
    assert sum((linha.liquido for linha in balancete.saidas_por_setor), ZERO) == totais.saidas


# Inadimplência (CA-18) ---------------------------------------------------------------------------------


def test_ca18_inadimplencia_detalhada_e_a_de_n12_com_convocado_e_justificou() -> None:
    livro = Livro()
    outro = novo_diretor("dev3_m10")
    conceder_permissoes(outro)
    simples = _atrasada(livro, "100.00")
    convocada = _atrasada(livro, "50.00", devedor=outro, vencimento=date(2026, 9, 1))
    rotina_diaria.executar(date(2026, 10, 5))
    inadimplencia.justificar_divida(ator_id=outro.id, cobranca_id=convocada.id, texto="Perdi o emprego")
    questionada = _atrasada(livro, "999.00", devedor=outro)
    questionamentos.questionar(ator_id=outro.id, cobranca_id=questionada.id, texto="Já paguei")

    linhas = public.inadimplencia_detalhada(date(2026, 10, 20))

    assert sorted((linha.valor, linha.convocado, linha.justificou) for linha in linhas) == [
        (Decimal("50.00"), True, True),
        (Decimal("100.00"), False, False),
    ]
    resumo = public.resumo_da_inadimplencia()
    assert len(linhas) == resumo.cobrancas
    assert sum((linha.valor for linha in linhas), ZERO) == resumo.total
    da_simples = next(linha for linha in linhas if linha.valor == simples.valor)
    assert (da_simples.devedor, da_simples.vencimento, da_simples.dias_de_atraso) == (
        livro.devedor.nome,
        date(2026, 10, 10),
        10,
    )


def test_ca18_inadimplencia_nao_tem_texto_livre_nem_contato() -> None:
    campos = {campo.name for campo in dataclasses.fields(public.CobrancaInadimplente)}

    assert campos == {
        "devedor",
        "descricao",
        "categoria",
        "valor",
        "vencimento",
        "dias_de_atraso",
        "convocado",
        "justificou",
    }


# Prestação de contas (CA-20) ---------------------------------------------------------------------------


def _enviada(livro: Livro, aprovado: str, enviado_em: datetime, valor: str | None = None) -> Saida:
    saida = livro.saida(aprovado)
    saidas.enviar_recurso(
        livro.fin.id, saida.id, valor=Dinheiro(valor or aprovado), arquivo=_pdf(), enviado_em=enviado_em
    )
    saida.refresh_from_db()
    return saida


def test_ca20_prestacoes_do_periodo_pelo_primeiro_envio_com_valores() -> None:
    livro = Livro()
    atrasada = _enviada(livro, "100.00", local(2026, 10, 2, 9))
    conferida = _enviada(livro, "300.00", local(2026, 10, 15, 9), valor="200.00")
    livro.prestar(conferida, "150.00")
    livro.devolver(conferida, "50.00")
    _enviada(livro, "70.00", local(2026, 9, 30, 9))
    livro.saida("80.00")

    linhas = public.prestacoes_de_contas(*OUT, so_pendentes=False, hoje=date(2026, 10, 20))

    assert [linha.aprovado for linha in linhas] == [Decimal("100.00"), Decimal("300.00")]
    primeira, segunda = linhas
    assert (primeira.situacao, primeira.dias_desde_o_envio, primeira.em_atraso) == (
        "RECURSO_ENVIADO",
        18,
        True,
    )
    assert primeira.tem_comprovante is False
    assert (segunda.enviado, segunda.gasto_informado, segunda.devolvido_validado) == (
        Decimal("200.00"),
        Decimal("150.00"),
        Decimal("50.00"),
    )
    assert (segunda.situacao, segunda.em_atraso) == ("EM_CONFERENCIA", False)
    assert primeira.solicitante == livro.solicitante.nome
    assert primeira.setor == atrasada.setor_nome


def test_ca20_so_pendentes_tira_as_liquidadas() -> None:
    livro = Livro()
    pendente = _enviada(livro, "100.00", local(2026, 10, 2, 9))
    liquidada = _enviada(livro, "60.00", local(2026, 10, 3, 9))
    livro.prestar(liquidada, "60.00")
    livro.liquidar(liquidada, em=local(2026, 10, 10))

    todas = public.prestacoes_de_contas(*OUT, so_pendentes=False, hoje=date(2026, 10, 20))
    pendentes = public.prestacoes_de_contas(*OUT, so_pendentes=True, hoje=date(2026, 10, 20))

    assert len(todas) == 2
    assert [linha.aprovado for linha in pendentes] == [pendente.valor_aprovado]


# Fluxo de caixa: o previsto (CA-21) --------------------------------------------------------------------


def test_ca21_previsto_por_mes_de_vencimento_sem_as_encerradas_sem_valor() -> None:
    livro = Livro()
    paga = _cobranca_em(livro, "100.00", date(2026, 10, 5))
    livro.registrar_pagamento(paga)
    with no_instante(local(2026, 10, 6)):
        pagamentos.validar(livro.validador.id, paga.id, motivo_id=livro.m_val_p)
    _cobranca_em(livro, "40.00", date(2026, 10, 25))
    livro.isentar(_cobranca_em(livro, "30.00", date(2026, 10, 26)))
    livro.cancelar(_cobranca_em(livro, "20.00", date(2026, 10, 27)))
    _atrasada(livro, "15.00", vencimento=date(2026, 10, 12))
    questionada = _atrasada(livro, "8.00", vencimento=date(2026, 10, 13))
    questionamentos.questionar(ator_id=livro.devedor.id, cobranca_id=questionada.id, texto="Errado")
    _cobranca_em(livro, "500.00", date(2026, 11, 5))

    meses = public.fluxo_previsto(date(2026, 10, 1), date(2026, 11, 30), hoje=date(2026, 10, 20))

    assert [mes.mes for mes in meses] == [date(2026, 10, 1), date(2026, 11, 1)]
    outubro, novembro = meses
    assert outubro.previsto == Decimal("163.00")
    assert outubro.recebido == Decimal("100.00")
    assert outubro.em_aberto == Decimal("63.00")
    assert outubro.questionadas == Decimal("8.00")
    assert outubro.inadimplentes == Decimal("15.00")
    assert (novembro.previsto, novembro.recebido, novembro.em_aberto) == (
        Decimal("500.00"),
        ZERO,
        Decimal("500.00"),
    )


# Orçamentos de eventos (CA-19) -------------------------------------------------------------------------


def test_ca19_orcamento_aprovado_e_realizado_por_evento() -> None:
    livro = Livro()
    com_saida, sem_saida, outro_evento = uuid.uuid7(), uuid.uuid7(), uuid.uuid7()
    liquidada = livro.saida_liquidada(
        "300.00", enviado="300.00", gasto="250.00", devolvido="50.00", liquidada_em=local(2026, 10, 9)
    )
    aguardando = livro.saida("120.00")
    Saida.objects.filter(pk=liquidada.pk).update(evento_id=com_saida)
    Saida.objects.filter(pk=aguardando.pk).update(evento_id=outro_evento)

    orcamentos = public.orcamentos_de_eventos([com_saida, sem_saida, outro_evento])

    assert (orcamentos[com_saida].aprovado, orcamentos[com_saida].realizado) == (
        Decimal("300.00"),
        Decimal("250.00"),
    )
    assert (orcamentos[outro_evento].aprovado, orcamentos[outro_evento].realizado) == (
        Decimal("120.00"),
        None,
    )
    assert sem_saida not in orcamentos
