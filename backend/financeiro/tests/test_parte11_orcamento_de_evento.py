"""Parte 11: vínculo do orçamento de evento e cancelamento com o evento (adendo 1 da spec técnica do M7).

O `evento_id` sai do conteúdo da solicitação de gasto: o vínculo é o registro `OrcamentoDeEvento`, criado só
por `abrir_solicitacao_orcamentaria`. `cancelar_orcamento_de_evento` trata os três casos do orçamento quando o
evento é cancelado.
"""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro import public as fin_public
from financeiro import tipos
from financeiro.models import NaoPodeApagar, OrcamentoDeEvento, Saida
from financeiro.services import saidas
from financeiro.tests.conftest import garantir_motivo
from financeiro.tests.test_parte8_saidas_servicos import (
    _aprovar_solicitacao,
    _notifs_tipo,
    _pdf,
    _png,
    _setup_gastos,
)
from kernel import events
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("tratadores_de_eventos")]

SOLICITACOES = "/api/v1/aprovacoes/solicitacoes/"


def _cliente(usuario: Any) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


def _itens(valor: str = "400.00") -> list[dict[str, Any]]:
    return [{"descricao": "Arbitragem", "valor": valor}]


def _orcamento(ctx: dict[str, Any], evento_id: uuid.UUID, valor: str = "400.00") -> uuid.UUID:
    return fin_public.abrir_solicitacao_orcamentaria(
        solicitante_id=ctx["solicitante"].id,
        descricao="Orçamento do amistoso",
        categoria_id=ctx["cat_saida"].id,
        setor_id=ctx["setor"].id,
        itens=_itens(valor),
        evento_id=evento_id,
    )


def _conteudo_da_tela(ctx: dict[str, Any], valor: str) -> dict[str, Any]:
    """O mesmo corpo de `conteudoEstruturado()` em `AcoesDaSolicitacao.tsx`."""
    return {
        "descricao": "Orçamento ajustado",
        "categoria_id": str(ctx["cat_saida"].id),
        "setor_id": str(ctx["setor"].id),
        "itens": _itens(valor),
        "cotacao_id": None,
    }


# --- vínculo ---


def test_orcamento_nasce_com_o_vinculo_e_sem_evento_no_conteudo() -> None:
    ctx = _setup_gastos()
    recebidos: list[fin_public.OrcamentoDeEventoMudou] = []
    events.subscribe(fin_public.OrcamentoDeEventoMudou, recebidos.append)
    evento_id = uuid.uuid7()

    sol_id = _orcamento(ctx, evento_id)

    vinculo = OrcamentoDeEvento.objects.get(solicitacao_id=sol_id)
    assert vinculo.evento_id == evento_id
    assert "evento_id" not in aprovacoes.obter_solicitacao(sol_id).conteudo
    _aprovar_solicitacao(ctx, sol_id)
    assert [(e.evento_id, e.acontecimento) for e in recebidos] == [(evento_id, "APROVADA")]
    assert Saida.objects.get(solicitacao_id=sol_id).evento_id == evento_id


def test_vinculo_e_imutavel_e_nao_e_apagado() -> None:
    ctx = _setup_gastos()
    vinculo = OrcamentoDeEvento.objects.get(solicitacao_id=_orcamento(ctx, uuid.uuid7()))

    vinculo.evento_id = uuid.uuid7()
    with pytest.raises(NaoPodeApagar):
        vinculo.save()
    with pytest.raises(NaoPodeApagar):
        vinculo.delete()


def test_conteudo_com_evento_e_recusado_pelo_motor_e_pela_rota_generica() -> None:
    ctx = _setup_gastos()
    conteudo = {**_conteudo_da_tela(ctx, "50.00"), "evento_id": str(uuid.uuid7())}

    with pytest.raises(BusinessError) as recusa:
        aprovacoes.enviar(tipo="financeiro.gasto", conteudo=conteudo, solicitante_id=ctx["comum"].id)
    assert recusa.value.code == "VALIDATION_ERROR"
    assert "evento_id" in recusa.value.details

    resposta = _cliente(ctx["comum"]).post(
        SOLICITACOES, {"tipo": "financeiro.gasto", "conteudo": conteudo}, format="json"
    )
    assert resposta.status_code == 400, resposta.content
    assert "evento_id" in resposta.json()["error"]["details"]
    assert not OrcamentoDeEvento.objects.exists()


def test_rota_de_gasto_nao_liga_gasto_a_evento() -> None:
    ctx = _setup_gastos()

    resposta = _cliente(ctx["comum"]).post(
        "/api/v1/financeiro/gastos/",
        {
            "descricao": "Uniformes",
            "categoria_id": str(ctx["cat_saida"].id),
            "setor_id": str(ctx["setor"].id),
            "itens": _itens("120.00"),
            "evento_id": str(uuid.uuid7()),
        },
        format="json",
    )

    assert resposta.status_code == 201, resposta.content
    assert "evento_id" not in resposta.json()["conteudo"]
    assert not OrcamentoDeEvento.objects.exists()


def test_ca08_orcamento_contestado_e_reenviado_pela_tela_continua_ligado_ao_evento() -> None:
    ctx = _setup_gastos()
    recebidos: list[fin_public.OrcamentoDeEventoMudou] = []
    events.subscribe(fin_public.OrcamentoDeEventoMudou, recebidos.append)
    evento_id = uuid.uuid7()
    sol_id = _orcamento(ctx, evento_id, "500.00")
    c_admin = _cliente(ctx["admin"])

    contestar = ctx["c_aprov"].post(
        f"{SOLICITACOES}{sol_id}/contestar/",
        {
            "motivo_id": garantir_motivo(c_admin, "solicitacao.contestar"),
            "mensagem": "Reduza a arbitragem.",
            "texto": "",
            "teto_sugerido": "350.00",
        },
        format="json",
    )
    assert contestar.status_code == 200, contestar.content
    reenviar = ctx["c_sol"].post(
        f"{SOLICITACOES}{sol_id}/reenviar/", {"conteudo": _conteudo_da_tela(ctx, "350.00")}, format="json"
    )
    assert reenviar.status_code == 200, reenviar.content
    _aprovar_solicitacao(ctx, sol_id)

    assert [e.acontecimento for e in recebidos] == ["CONTESTADA", "APROVADA"]
    assert all(e.evento_id == evento_id for e in recebidos)
    assert recebidos[-1].valor == Decimal("350.00")
    assert Saida.objects.get(solicitacao_id=sol_id).evento_id == evento_id


def test_complemento_de_orcamento_de_evento_nasce_sem_evento_no_conteudo() -> None:
    ctx = _setup_gastos()
    sol_id = _orcamento(ctx, uuid.uuid7(), "300.00")
    _aprovar_solicitacao(ctx, sol_id)
    saida = Saida.objects.get(solicitacao_id=sol_id)
    saidas.enviar_recurso(ctx["enviador"].id, saida.id, valor=Dinheiro("300.00"), arquivo=_pdf())
    saidas.prestar_contas(
        ctx["solicitante"].id, saida.id, valor=Dinheiro("360.00"), descricao="Subiu", arquivo=_png()
    )

    pedido = saidas.pedir_complemento(
        ctx["solicitante"].id, saida.id, itens=[{"descricao": "Diferença", "valor": "60.00"}]
    )

    from financeiro.models import Complemento

    complemento = Complemento.objects.get(pk=pedido["id"])
    assert "evento_id" not in aprovacoes.obter_solicitacao(complemento.solicitacao_id).conteudo
    assert not OrcamentoDeEvento.objects.filter(solicitacao_id=complemento.solicitacao_id).exists()


# --- cancelamento junto com o evento (CA-24 do M8) ---


def _cancelar(sol_id: uuid.UUID, evento_id: uuid.UUID, ator_id: uuid.UUID | None = None) -> None:
    fin_public.cancelar_orcamento_de_evento(
        sol_id, evento_id=evento_id, titulo_do_evento="Amistoso", ator_id=ator_id, motivo="Evento cancelado"
    )


@pytest.mark.parametrize("situacao", ["EM_ANALISE", "CONTESTADA"])
def test_orcamento_ainda_em_decisao_e_cancelado(situacao: str) -> None:
    ctx = _setup_gastos()
    evento_id = uuid.uuid7()
    sol_id = _orcamento(ctx, evento_id)
    if situacao == "CONTESTADA":
        resposta = ctx["c_aprov"].post(
            f"{SOLICITACOES}{sol_id}/contestar/",
            {
                "motivo_id": garantir_motivo(_cliente(ctx["admin"]), "solicitacao.contestar"),
                "mensagem": "Ajuste.",
                "texto": "",
            },
            format="json",
        )
        assert resposta.status_code == 200, resposta.content

    _cancelar(sol_id, evento_id, ator_id=None)

    assert aprovacoes.situacao_de(sol_id) == aprovacoes.Situacao.CANCELADA
    assert not Saida.objects.filter(solicitacao_id=sol_id).exists()


def test_orcamento_aprovado_sem_envio_cancela_a_solicitacao_e_a_saida() -> None:
    ctx = _setup_gastos()
    evento_id = uuid.uuid7()
    sol_id = _orcamento(ctx, evento_id)
    _aprovar_solicitacao(ctx, sol_id)

    _cancelar(sol_id, evento_id, ator_id=ctx["aprovador"].id)

    assert aprovacoes.situacao_de(sol_id) == aprovacoes.Situacao.CANCELADA
    assert Saida.objects.get(solicitacao_id=sol_id).situacao == "CANCELADA"
    assert _notifs_tipo(ctx["liquidador"], tipos.NOTIF_ORCAMENTO_DE_EVENTO_CANCELADO) == []


@pytest.mark.parametrize("liquidar", [False, True])
def test_recurso_ja_enviado_nada_e_cancelado_e_quem_liquida_e_avisado_uma_vez(liquidar: bool) -> None:
    ctx = _setup_gastos()
    evento_id = uuid.uuid7()
    sol_id = _orcamento(ctx, evento_id, "300.00")
    _aprovar_solicitacao(ctx, sol_id)
    saida = Saida.objects.get(solicitacao_id=sol_id)
    saidas.enviar_recurso(ctx["enviador"].id, saida.id, valor=Dinheiro("300.00"), arquivo=_pdf())
    if liquidar:
        saidas.prestar_contas(
            ctx["solicitante"].id, saida.id, valor=Dinheiro("300.00"), descricao="NF", arquivo=_png()
        )
        saidas.liquidar(ctx["liquidador"].id, saida.id)
    antes = Saida.objects.get(pk=saida.id).situacao

    _cancelar(sol_id, evento_id)
    _cancelar(sol_id, evento_id)

    assert Saida.objects.get(pk=saida.id).situacao == antes
    esperada = aprovacoes.Situacao.ENCERRADA if liquidar else aprovacoes.Situacao.EM_EXECUCAO
    assert aprovacoes.situacao_de(sol_id) == esperada
    assert len(_notifs_tipo(ctx["liquidador"], tipos.NOTIF_ORCAMENTO_DE_EVENTO_CANCELADO)) == 1
    acoes = [r.acao for r in auditoria.historico_do_item("saida", saida.id)]
    assert "ORCAMENTO_DE_EVENTO_CANCELADO" in acoes


def test_orcamento_ja_cancelado_nao_muda_nada() -> None:
    ctx = _setup_gastos()
    evento_id = uuid.uuid7()
    sol_id = _orcamento(ctx, evento_id)
    aprovacoes.cancelar(sol_id, ator_id=ctx["solicitante"].id, motivo="Desisti")

    _cancelar(sol_id, evento_id)

    assert aprovacoes.situacao_de(sol_id) == aprovacoes.Situacao.CANCELADA


def test_vinculo_de_outro_evento_e_erro_de_programacao() -> None:
    ctx = _setup_gastos()
    sol_id = _orcamento(ctx, uuid.uuid7())

    with pytest.raises(ValueError, match="não é do evento"):
        _cancelar(sol_id, uuid.uuid7())
    assert aprovacoes.situacao_de(sol_id) == aprovacoes.Situacao.EM_ANALISE


@pytest.mark.django_db(transaction=True)
def test_migracao_do_vinculo_e_reversivel() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("financeiro", "0003_saidas_cotacoes_estornos_e_permissoes")])
    assert "financeiro_orcamentodeevento" not in connection.introspection.table_names()
    try:
        call_command("migrate", "financeiro", verbosity=0)
    finally:
        call_command("migrate", verbosity=0)
    assert "financeiro_orcamentodeevento" in connection.introspection.table_names()
