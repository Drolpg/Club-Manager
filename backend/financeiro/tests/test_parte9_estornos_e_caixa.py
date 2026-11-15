"""Parte 9: Estornos ligados (ADR-013), visão do caixa (RF-127) e filtros de consulta de saídas."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from financeiro import public as fin_public
from financeiro import tipos
from financeiro.domain.autorizacao import (
    PERM_COBRANCAS_CRIAR,
    PERM_ENTRADAS_REGISTRAR,
    PERM_ENTRADAS_VALIDAR,
    PERM_FINANCEIRO_ESTORNAR,
    PERM_GASTOS_APROVAR,
    PERM_PAGAMENTOS_VALIDAR,
    PERM_SAIDAS_ENVIAR,
    PERM_SAIDAS_LIQUIDAR,
)
from financeiro.models import CategoriaFinanceira, Cobranca, Entrada, Estorno, Saida
from financeiro.services import consulta, entradas, estornos, gastos, pagamentos, saidas
from financeiro.tests.conftest import (
    conceder_permissoes,
    criar_cobranca,
    garantir_chave_pix,
    garantir_motivo,
    hoje_local,
    notificacoes_do,
    novo_diretor,
)
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError
from permissoes import public as permissoes

pytestmark = pytest.mark.django_db

_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _pdf(nome: str = "comp.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, _PDF_BYTES, content_type="application/pdf")


def _notifs_tipo(usuario: Any, tipo: str) -> list[dict[str, Any]]:
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return [n for n in notificacoes_do(cliente) if n["tipo"] == tipo]


def _cenario_caixa_e_estorno() -> dict[str, Any]:
    admin = novo_diretor("admin_s9", admin=True)
    financeiro_sem_estorno = novo_diretor("fin_s9")
    solicitante = novo_diretor("sol_s9")
    conceder_permissoes(solicitante)
    conceder_permissoes(
        financeiro_sem_estorno,
        PERM_COBRANCAS_CRIAR,
        PERM_PAGAMENTOS_VALIDAR,
        PERM_ENTRADAS_REGISTRAR,
        PERM_ENTRADAS_VALIDAR,
        PERM_GASTOS_APROVAR,
        PERM_SAIDAS_ENVIAR,
        PERM_SAIDAS_LIQUIDAR,
    )
    estornador = novo_diretor("est_s9")
    conceder_permissoes(estornador, PERM_FINANCEIRO_ESTORNAR)

    c_admin = APIClient()
    c_admin.force_authenticate(user=admin)
    c_fin = APIClient()
    c_fin.force_authenticate(user=financeiro_sem_estorno)

    cat_entrada = CategoriaFinanceira.objects.get(nome="Patrocínio", natureza="ENTRADA")
    cat_div = CategoriaFinanceira.objects.get(nome="Diversos", natureza="ENTRADA")
    cat_saida = CategoriaFinanceira.objects.get(nome="Arbitragem", natureza="SAIDA")
    setor = permissoes.listar_setores_ativos()[0]
    pix_id = uuid.UUID(garantir_chave_pix(c_admin, padrao=True))

    return {
        "admin": admin,
        "fin": financeiro_sem_estorno,
        "estornador": estornador,
        "solicitante": solicitante,
        "c_admin": c_admin,
        "c_fin": c_fin,
        "cat_entrada": cat_entrada,
        "cat_div": cat_div,
        "cat_saida": cat_saida,
        "setor": setor,
        "pix_id": pix_id,
        "m_apr": garantir_motivo(c_admin, "solicitacao.aprovar"),
        "m_val_e": uuid.UUID(garantir_motivo(c_admin, tipos.DECISAO_ENTRADA_VALIDAR)),
        "m_val_p": uuid.UUID(garantir_motivo(c_admin, tipos.DECISAO_PAGAMENTO_VALIDAR)),
        "m_est": uuid.UUID(garantir_motivo(c_admin, tipos.DECISAO_ESTORNAR)),
    }


def _nova_saida(ctx: dict[str, Any], descricao: str, valor: str) -> Saida:
    sol = gastos.abrir_solicitacao(
        ctx["solicitante"].id,
        descricao=descricao,
        categoria_id=ctx["cat_saida"].id,
        setor_id=ctx["setor"].id,
        itens=[{"descricao": descricao, "valor": valor}],
    )
    resp = ctx["c_fin"].post(
        f"/api/v1/aprovacoes/solicitacoes/{sol.id}/aprovar/",
        {"motivo_id": ctx["m_apr"], "texto": "Ok"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    return Saida.objects.get(solicitacao_id=sol.id, situacao="AGUARDANDO_ENVIO")


def test_ca03_e_ca32_visao_do_caixa_comprometido_realizado_e_estornos() -> None:
    ctx = _cenario_caixa_e_estorno()
    caixa0 = fin_public.visao_do_caixa()
    assert (caixa0.total_entradas_validadas, caixa0.total_saidas_liquidadas, caixa0.total_comprometido) == (
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    )

    # Entrada avulsa validada soma em entradas_validadas.
    ent_avulsa = entradas.registrar(
        ctx["fin"].id,
        categoria_id=ctx["cat_entrada"].id,
        valor=Dinheiro("1000.00"),
        data=hoje_local(),
        origem="Patrocinador",
        evidencia_texto="TED 1",
    )
    entradas.validar(ctx["admin"].id, uuid.UUID(str(ent_avulsa["id"])), motivo_id=ctx["m_val_e"])

    # Saída 1: aprovada 300, enviada 200 -> comprometida = 300, liquidada = 0.
    s1 = _nova_saida(ctx, "Arbitragem jogo 1", "300.00")
    assert fin_public.visao_do_caixa().total_comprometido == Decimal("300.00")
    saidas.enviar_recurso(ctx["fin"].id, s1.id, valor=Dinheiro("200.00"), arquivo=_pdf("s1.pdf"))

    # Prestação 150 + devolução de 50 validada -> comprometido = 250; entrada avulsa continua 1000.
    saidas.prestar_contas(ctx["solicitante"].id, s1.id, valor=Dinheiro("150.00"), descricao="Recibo 150")
    dev = saidas.devolver_sobra(
        ctx["solicitante"].id, s1.id, valor=Dinheiro("50.00"), evidencia_texto="Pix 50"
    )
    entradas.validar(ctx["fin"].id, uuid.UUID(str(dev["id"])), motivo_id=ctx["m_val_e"])

    caixa_meio = fin_public.visao_do_caixa()
    assert caixa_meio.total_entradas_validadas == Decimal("1000.00")
    assert caixa_meio.total_comprometido == Decimal("250.00")
    assert caixa_meio.total_saidas_liquidadas == Decimal("0.00")

    # Ao liquidar s1: comprometido vai a 0; saidas_liquidadas passa a ser 200 - 50 = 150 (realizado).
    saidas.liquidar(ctx["fin"].id, s1.id)
    caixa_liq = fin_public.visao_do_caixa()
    assert caixa_liq.total_comprometido == Decimal("0.00")
    assert caixa_liq.total_saidas_liquidadas == Decimal("150.00")

    # Saída 2: aprovada 200, enviada 200, gasto 240 (40 não reembolsados): liquidada computa apenas 200.
    s2 = _nova_saida(ctx, "Arbitragem jogo 2", "200.00")
    saidas.enviar_recurso(ctx["fin"].id, s2.id, valor=Dinheiro("200.00"), arquivo=_pdf("s2.pdf"))
    saidas.prestar_contas(ctx["solicitante"].id, s2.id, valor=Dinheiro("240.00"), descricao="Extra")
    saidas.liquidar(ctx["fin"].id, s2.id, justificativa="Sem reembolso")
    assert fin_public.visao_do_caixa().total_saidas_liquidadas == Decimal("350.00")

    # Estorno da saída s2 retira 200 das saídas liquidadas; devolução de s1 não estorna isolada!
    with pytest.raises(BusinessError) as exc_bloq:
        estornos.estornar_entrada(
            ctx["admin"].id,
            uuid.UUID(str(dev["id"])),
            motivo_id=ctx["m_est"],
            justificativa="Tentativa isolada",
        )
    assert exc_bloq.value.code == "NAO_PODE_ESTORNAR"

    estornos.estornar_saida(
        ctx["estornador"].id,
        s2.id,
        motivo_id=ctx["m_est"],
        justificativa="Lançamento duplicado",
    )
    caixa_est = fin_public.visao_do_caixa()
    assert caixa_est.total_saidas_liquidadas == Decimal("150.00")
    assert Estorno.objects.filter(saida=s2).count() == 1
    assert len(_notifs_tipo(ctx["solicitante"], tipos.NOTIF_REGISTRO_ESTORNADO)) == 1
    assert len(_notifs_tipo(ctx["admin"], tipos.NOTIF_REGISTRO_ESTORNADO)) == 1


def test_ca27_a_29_estorno_permissao_entrada_e_cobranca_com_bloqueio_de_recibo() -> None:
    ctx = _cenario_caixa_e_estorno()

    # Setor Financeiro padrão não possui `financeiro.estornar`.
    ent = entradas.registrar(
        ctx["fin"].id,
        categoria_id=ctx["cat_entrada"].id,
        valor=Dinheiro("500.00"),
        data=hoje_local(),
        origem="Rifa extra",
        evidencia_texto="Comprovante",
    )
    entradas.validar(ctx["admin"].id, uuid.UUID(str(ent["id"])), motivo_id=ctx["m_val_e"])

    with pytest.raises(BusinessError) as exc_perm:
        estornos.estornar_entrada(
            ctx["fin"].id,
            uuid.UUID(str(ent["id"])),
            motivo_id=ctx["m_est"],
            justificativa="Sem permissão",
        )
    assert exc_perm.value.code == "PERMISSION_DENIED"

    res_est_ent = estornos.estornar_entrada(
        ctx["admin"].id,
        uuid.UUID(str(ent["id"])),
        motivo_id=ctx["m_est"],
        justificativa="Entrada duplicada confirmada",
    )
    assert res_est_ent["alvo_tipo"] == "ENTRADA"
    assert Entrada.objects.get(pk=ent["id"]).situacao == "ESTORNADA"

    # Cobrança paga pode ser estornada e deixa de emitir recibo PDF (CA-29).
    cob_id = uuid.UUID(
        str(
            criar_cobranca(
                ctx["c_fin"],
                devedor_id=ctx["solicitante"].id,
                categoria_id=str(ctx["cat_div"].id),
                descricao="Mensalidade maio",
                valor="120.00",
                vencimento=hoje_local() + timedelta(days=5),
                chave_pix_id=str(ctx["pix_id"]),
            )["id"]
        )
    )
    pagamentos.registrar(
        ctx["solicitante"].id,
        cob_id,
        forma="COMPROVANTE",
        data_pagamento=hoje_local(),
        arquivo=_pdf("pag.pdf"),
    )
    pagamentos.validar(ctx["fin"].id, cob_id, motivo_id=ctx["m_val_p"])
    assert pagamentos.emitir_recibo(ctx["solicitante"].id, cob_id).status_code == 200

    res_est_cob = estornos.estornar_cobranca(
        ctx["estornador"].id,
        cob_id,
        motivo_id=ctx["m_est"],
        justificativa="Cheque/comprovante inválido após fechamento",
    )
    assert res_est_cob["alvo_tipo"] == "COBRANCA"
    assert Cobranca.objects.get(pk=cob_id).situacao == "ESTORNADA"

    with pytest.raises(BusinessError) as exc_rec:
        pagamentos.emitir_recibo(ctx["solicitante"].id, cob_id)
    assert exc_rec.value.code == "NAO_ESTA_PAGA"


def test_ca30_e_31_filtros_e_paginacao_saidas_e_estornos() -> None:
    ctx = _cenario_caixa_e_estorno()
    s1 = _nova_saida(ctx, "Saída aguardando", "100.00")
    s2 = _nova_saida(ctx, "Saída enviada atrasada", "200.00")
    saidas.enviar_recurso(
        ctx["fin"].id,
        s2.id,
        valor=Dinheiro("200.00"),
        arquivo=_pdf("atraso.pdf"),
        enviado_em=timezone.now() - timedelta(days=8),
    )

    pag_pend_env = consulta.listar_saidas(ctx["fin"].id, pendentes_envio=True)
    assert [item["id"] for item in pag_pend_env["itens"]] == [s1.id]

    pag_atr = consulta.listar_saidas(ctx["fin"].id, atrasadas=True)
    assert [item["id"] for item in pag_atr["itens"]] == [s2.id]

    detalhe = consulta.detalhe_saida(ctx["solicitante"].id, s2.id)
    assert detalhe["em_atraso"] is True
    assert len(detalhe["envios"]) == 1
    assert "prestar_contas" in detalhe["acoes"]

    hist = consulta.historico_saida(ctx["fin"].id, s2.id)
    assert {h["acao"] for h in hist} >= {"SAIDA_ABERTA", "RECURSO_ENVIADO"}
