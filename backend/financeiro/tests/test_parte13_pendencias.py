"""Parte 13: pendências e resumos do dashboard (N11 a N13, N15 e "minhas cobranças"; CA-07, CA-08).

Só leitura: as consultas não conferem quem pergunta (é do serviço de `relatorios`).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from financeiro import public
from financeiro.models import Cobranca
from financeiro.services import consulta, questionamentos, rotina_diaria, saidas
from financeiro.tests.apoio_lancamentos import Livro, local, no_instante
from financeiro.tests.conftest import conceder_permissoes, novo_diretor
from kernel.dinheiro import Dinheiro

pytestmark = pytest.mark.django_db


def _atrasada(livro: Livro, valor: str, *, devedor: object = None, dias: int = 20) -> Cobranca:
    """Uma cobrança criada `dias` atrás, vencida há uma semana e marcada pela rotina diária."""
    hoje = timezone.localdate()
    criada_em = local(*(hoje - timedelta(days=dias)).timetuple()[:3])
    with no_instante(criada_em):
        cobranca = livro.cobranca(valor, vencimento=hoje - timedelta(days=7), devedor=devedor)
    rotina_diaria.executar(hoje)
    cobranca.refresh_from_db()
    assert cobranca.situacao == "ATRASADA"
    return cobranca


def test_n11_a_receber_no_mes_conta_aberta_atrasada_e_em_validacao() -> None:
    livro = Livro()
    hoje = timezone.localdate()
    aberta = livro.cobranca("10.00", vencimento=hoje + timedelta(days=3))
    em_validacao = livro.cobranca("20.00", vencimento=hoje + timedelta(days=4))
    livro.registrar_pagamento(em_validacao)
    atrasada = _atrasada(livro, "30.00")
    livro.isentar(livro.cobranca("40.00", vencimento=hoje + timedelta(days=5)))
    livro.cobranca("50.00", vencimento=hoje + timedelta(days=60))
    livro.cobranca_paga("60.00")

    vencimentos = [aberta.vencimento, em_validacao.vencimento, atrasada.vencimento]
    resumo = public.a_receber(min(vencimentos), max(vencimentos))

    assert (resumo.quantidade, resumo.total) == (3, Decimal("60.00"))


def test_ca07_inadimplencia_igual_a_consulta_de_inadimplentes_e_sem_questionada() -> None:
    livro = Livro()
    outro = novo_diretor("dev2_m10")
    conceder_permissoes(outro)
    _atrasada(livro, "100.00")
    _atrasada(livro, "50.00")
    _atrasada(livro, "25.00", devedor=outro)
    questionada = _atrasada(livro, "999.00", devedor=outro)
    questionamentos.questionar(ator_id=outro.id, cobranca_id=questionada.id, texto="Já paguei")

    resumo = public.resumo_da_inadimplencia()

    assert (resumo.cobrancas, resumo.devedores, resumo.total) == (3, 2, Decimal("175.00"))
    lista = consulta.listar(livro.fin.id, inadimplentes=True, limite=50)
    assert len(lista.itens) == resumo.cobrancas
    assert sum((i["valor"] for i in lista.itens), Decimal("0.00")) == resumo.total


def test_ca08_pendencias_de_validacao_contam_pagamentos_e_entradas_inclusive_devolucao() -> None:
    livro = Livro()
    em_validacao = livro.cobranca("80.00")
    livro.registrar_pagamento(em_validacao)
    livro.entrada("300.00")
    saida = livro.saida("200.00")
    livro.enviar(saida, "200.00")
    livro.prestar(saida, "150.00")
    livro.devolver(saida, "50.00", validar=False)
    livro.cobranca_paga("10.00")
    livro.entrada_validada("20.00")

    pendencias = public.pendencias_de_validacao()

    assert (pendencias.pagamentos.quantidade, pendencias.pagamentos.total) == (1, Decimal("80.00"))
    assert (pendencias.entradas.quantidade, pendencias.entradas.total) == (2, Decimal("350.00"))


def test_ca08_prestacoes_pendentes_aguardando_em_atraso_no_setimo_dia_e_em_conferencia() -> None:
    livro = Livro()
    hoje = timezone.localdate()

    def enviada_ha(dias: int) -> None:
        saida = livro.saida("100.00")
        enviado_em = local(*(hoje - timedelta(days=dias)).timetuple()[:3], hora=9)
        saidas.enviar_recurso(
            livro.fin.id, saida.id, valor=Dinheiro("100.00"), arquivo=_pdf(), enviado_em=enviado_em
        )

    enviada_ha(7)
    enviada_ha(6)
    conferencia = livro.saida("90.00")
    livro.enviar(conferencia, "90.00")
    livro.prestar(conferencia, "90.00")
    livro.saida("70.00")

    pendentes = public.prestacoes_pendentes(hoje)

    assert (pendentes.aguardando, pendentes.em_atraso, pendentes.em_conferencia) == (2, 1, 1)


def _pdf() -> SimpleUploadedFile:
    return SimpleUploadedFile("c.pdf", b"%PDF-1.4\n%%EOF\n", content_type="application/pdf")


def test_resumo_do_devedor_em_aberto_atrasadas_em_validacao_e_a_proxima() -> None:
    livro = Livro()
    hoje = timezone.localdate()
    livro.cobranca("10.00", vencimento=hoje + timedelta(days=9), descricao="Depois")
    proxima = livro.cobranca("15.00", vencimento=hoje + timedelta(days=2), descricao="Logo")
    em_validacao = livro.cobranca("20.00")
    livro.registrar_pagamento(em_validacao)
    _atrasada(livro, "30.00")
    livro.cobranca_paga("40.00")

    resumo = public.resumo_do_devedor(livro.devedor.id, hoje)

    assert (resumo.em_aberto.quantidade, resumo.em_aberto.total) == (2, Decimal("25.00"))
    assert (resumo.atrasadas.quantidade, resumo.atrasadas.total) == (1, Decimal("30.00"))
    assert (resumo.em_validacao.quantidade, resumo.em_validacao.total) == (1, Decimal("20.00"))
    assert resumo.proxima is not None
    assert (resumo.proxima.id, resumo.proxima.descricao) == (proxima.id, "Logo")
    assert resumo.proxima.valor == Decimal("15.00")


def test_resumo_do_devedor_sem_cobrancas() -> None:
    sem_nada = novo_diretor("vazio_m10")

    resumo = public.resumo_do_devedor(sem_nada.id, date(2026, 11, 22))

    assert (resumo.em_aberto.quantidade, resumo.atrasadas.quantidade, resumo.em_validacao.quantidade) == (
        0,
        0,
        0,
    )
    assert resumo.proxima is None
