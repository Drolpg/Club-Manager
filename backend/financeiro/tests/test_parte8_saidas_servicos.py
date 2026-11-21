"""Parte 8: Serviços de gastos, aprovações, envios, prestação, devolução, complemento e rotina."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from aprovacoes import public as aprovacoes
from financeiro import public as fin_public
from financeiro import tipos
from financeiro.domain.autorizacao import (
    PERM_ENTRADAS_VALIDAR,
    PERM_GASTOS_APROVAR,
    PERM_SAIDAS_ENVIAR,
    PERM_SAIDAS_LIQUIDAR,
)
from financeiro.models import (
    CategoriaFinanceira,
    Complemento,
    Cotacao,
    Saida,
    SituacaoComplemento,
    SituacaoPrestacao,
)
from financeiro.services import consulta, gastos, rotina_diaria, saidas
from financeiro.tests.conftest import (
    conceder_permissoes,
    garantir_motivo,
    hoje_local,
    notificacoes_do,
    novo_diretor,
)
from kernel import events
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError
from permissoes import public as permissoes

pytestmark = pytest.mark.django_db

_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _pdf(nome: str = "comp.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, _PDF_BYTES, content_type="application/pdf")


def _png(nome: str = "nota.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, _PNG_BYTES, content_type="image/png")


def _notifs_tipo(usuario: Any, tipo: str) -> list[dict[str, Any]]:
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return [n for n in notificacoes_do(cliente) if n["tipo"] == tipo]


def _setup_gastos() -> dict[str, Any]:
    admin = novo_diretor("admin_s8", admin=True)
    solicitante = novo_diretor("sol_s8")
    aprovador = novo_diretor("apr_s8")
    enviador = novo_diretor("env_s8")
    liquidador = novo_diretor("liq_s8")
    validador = novo_diretor("val_s8")
    comum = novo_diretor("comum_s8")

    conceder_permissoes(solicitante)
    conceder_permissoes(aprovador, PERM_GASTOS_APROVAR)
    conceder_permissoes(enviador, PERM_SAIDAS_ENVIAR)
    conceder_permissoes(liquidador, PERM_SAIDAS_LIQUIDAR, PERM_ENTRADAS_VALIDAR)
    conceder_permissoes(validador, PERM_ENTRADAS_VALIDAR)
    conceder_permissoes(comum)

    cat_saida = CategoriaFinanceira.objects.get(nome="Material esportivo", natureza="SAIDA")
    cat_entrada = CategoriaFinanceira.objects.get(nome="Diversos", natureza="ENTRADA")
    setor = permissoes.listar_setores_ativos()[0]

    from rest_framework.test import APIClient

    c_admin = APIClient()
    c_admin.force_authenticate(user=admin)
    c_aprov = APIClient()
    c_aprov.force_authenticate(user=aprovador)
    c_sol = APIClient()
    c_sol.force_authenticate(user=solicitante)

    m_apr = garantir_motivo(c_admin, "solicitacao.aprovar")
    m_rec = garantir_motivo(c_admin, "solicitacao.recusar")
    m_dev_p = garantir_motivo(c_admin, tipos.DECISAO_PRESTACAO_DEVOLVER)
    m_val_e = garantir_motivo(c_admin, tipos.DECISAO_ENTRADA_VALIDAR)

    return {
        "admin": admin,
        "solicitante": solicitante,
        "aprovador": aprovador,
        "enviador": enviador,
        "liquidador": liquidador,
        "validador": validador,
        "comum": comum,
        "c_aprov": c_aprov,
        "c_sol": c_sol,
        "cat_saida": cat_saida,
        "cat_entrada": cat_entrada,
        "setor": setor,
        "m_apr": m_apr,
        "m_rec": m_rec,
        "m_dev_p": m_dev_p,
        "m_val_e": m_val_e,
    }


def _aprovar_solicitacao(ctx: dict[str, Any], solicitacao_id: uuid.UUID) -> None:
    resp = ctx["c_aprov"].post(
        f"/api/v1/aprovacoes/solicitacoes/{solicitacao_id}/aprovar/",
        {"motivo_id": ctx["m_apr"], "texto": "Aprovado para compra."},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _abrir_e_aprovar(
    ctx: dict[str, Any],
    *,
    itens: list[dict[str, Any]] | None = None,
    descricao: str = "Compra de bolas oficiais",
    cotacao_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, Saida]:
    sol = gastos.abrir_solicitacao(
        ctx["solicitante"].id,
        descricao=descricao,
        categoria_id=ctx["cat_saida"].id,
        setor_id=ctx["setor"].id,
        itens=itens or [{"descricao": "Bolas", "valor": "200.00"}, {"descricao": "Redes", "valor": "100.00"}],
        cotacao_id=cotacao_id,
    )
    _aprovar_solicitacao(ctx, sol.id)
    saida = Saida.objects.get(solicitacao_id=sol.id, situacao="AGUARDANDO_ENVIO")
    return sol.id, saida


def test_ca01_a_07_solicitacao_de_gasto_aprovacao_cancelamento_pre_envio_e_pos_envio() -> None:
    ctx = _setup_gastos()

    cot = gastos.upload_cotacao(ctx["solicitante"].id, _pdf("orcamento.pdf"))
    assert Cotacao.objects.filter(pk=cot.id).exists()

    # Recusa categoria ENTRADA no gasto e setor inexistente
    with pytest.raises(BusinessError) as exc_cat:
        gastos.abrir_solicitacao(
            ctx["solicitante"].id,
            descricao="Erro categoria",
            categoria_id=ctx["cat_entrada"].id,
            setor_id=ctx["setor"].id,
            itens=[{"descricao": "Item", "valor": "50.00"}],
        )
    assert exc_cat.value.status == 400

    with pytest.raises(BusinessError) as exc_set:
        gastos.abrir_solicitacao(
            ctx["solicitante"].id,
            descricao="Erro setor",
            categoria_id=ctx["cat_saida"].id,
            setor_id=uuid.uuid4(),
            itens=[{"descricao": "Item", "valor": "50.00"}],
        )
    assert exc_set.value.status == 400

    sol_id, saida = _abrir_e_aprovar(ctx, cotacao_id=cot.id)
    assert saida.valor_aprovado == Decimal("300.00")
    assert saida.categoria_nome == "Material esportivo"
    assert saida.setor_nome == ctx["setor"].nome
    assert saida.cotacao_id == cot.id
    assert len(_notifs_tipo(ctx["enviador"], tipos.NOTIF_SAIDA_AGUARDANDO_ENVIO)) == 1

    # CA-07: cancelamento na solicitação antes do envio cancela a Saida vinculada.
    aprovacoes.cancelar(sol_id, ator_id=ctx["solicitante"].id, motivo="Fornecedor desistiu")
    saida.refresh_from_db()
    assert saida.situacao == "CANCELADA"
    assert saida.cancelada_em is not None

    # Nova solicitação e envio inicial (D-15): bloqueia cancelamento em aprovacoes.
    sol2_id, saida2 = _abrir_e_aprovar(ctx)
    saidas.enviar_recurso(
        ctx["enviador"].id,
        saida2.id,
        valor=Dinheiro("300.00"),
        arquivo=_pdf("ted.pdf"),
    )
    saida2.refresh_from_db()
    assert saida2.situacao == "RECURSO_ENVIADO"
    assert aprovacoes.situacao_de(sol2_id) == aprovacoes.Situacao.EM_EXECUCAO
    assert len(_notifs_tipo(ctx["solicitante"], tipos.NOTIF_RECURSO_ENVIADO)) == 1

    with pytest.raises(BusinessError) as exc_d15:
        saidas.enviar_recurso(
            ctx["enviador"].id,
            saida2.id,
            valor=Dinheiro("10.00"),
            arquivo=_pdf("ted2.pdf"),
        )
    assert exc_d15.value.code == "NAO_AGUARDA_ENVIO"

    with pytest.raises(BusinessError) as exc_canc:
        aprovacoes.cancelar(sol2_id, ator_id=ctx["solicitante"].id, motivo="Tarde demais")
    assert exc_canc.value.code == "NAO_PODE_CANCELAR"


def test_ca12_a_15_prestacao_lembretes_idempotentes_e_devolucao_de_prestacao() -> None:
    ctx = _setup_gastos()
    _, saida = _abrir_e_aprovar(ctx)
    agora = timezone.now()
    saidas.enviar_recurso(
        ctx["enviador"].id,
        saida.id,
        valor=Dinheiro("300.00"),
        arquivo=_pdf("ted.pdf"),
        enviado_em=agora - timedelta(days=8),
    )

    hoje = hoje_local()
    r1 = rotina_diaria.executar(hoje)
    assert r1["prestacoes_lembrete_5_dias"] == 1
    assert r1["prestacoes_aviso_7_dias"] == 1
    assert len(_notifs_tipo(ctx["solicitante"], tipos.NOTIF_PRESTACAO_LEMBRETE_5_DIAS)) == 1
    assert len(_notifs_tipo(ctx["solicitante"], tipos.NOTIF_PRESTACAO_VENCIDA)) == 1
    assert len(_notifs_tipo(ctx["liquidador"], tipos.NOTIF_PRESTACAO_VENCIDA_FIN)) == 1
    assert consulta.detalhe_saida(ctx["liquidador"].id, saida.id)["em_atraso"] is True

    # Segunda execução no mesmo dia é idempotente (RNF-10).
    r2 = rotina_diaria.executar(hoje)
    assert r2["prestacoes_lembrete_5_dias"] == 0
    assert r2["prestacoes_aviso_7_dias"] == 0

    # Prestação continua aceita após o vencimento (P11); outro ator é recusado.
    with pytest.raises(BusinessError) as exc_sol:
        saidas.prestar_contas(
            ctx["enviador"].id,
            saida.id,
            valor=Dinheiro("300.00"),
            descricao="Tentativa alheia",
            arquivo=_png("nf.png"),
        )
    assert exc_sol.value.code == "SO_O_SOLICITANTE"

    saidas.prestar_contas(
        ctx["solicitante"].id,
        saida.id,
        valor=Dinheiro("300.00"),
        descricao="Nota fiscal 123",
        arquivo=_png("nf.png"),
    )
    saida.refresh_from_db()
    assert saida.situacao == "EM_CONFERENCIA"
    assert len(_notifs_tipo(ctx["liquidador"], tipos.NOTIF_PRESTACAO_REGISTRADA)) == 1

    # Devolver prestação para correção volta para RECURSO_ENVIADO e guarda histórico.
    saidas.devolver_prestacao(
        ctx["liquidador"].id,
        saida.id,
        motivo_id=uuid.UUID(ctx["m_dev_p"]),
        texto="Faltou página 2 do cupom.",
    )
    saida.refresh_from_db()
    assert saida.situacao == "RECURSO_ENVIADO"
    assert saida.prestacoes.filter(situacao=SituacaoPrestacao.DEVOLVIDA).count() == 1
    assert len(_notifs_tipo(ctx["solicitante"], tipos.NOTIF_PRESTACAO_DEVOLVIDA)) == 1


def test_ca16_a_25_devolucao_complemento_e_liquidacoes_completas() -> None:
    ctx = _setup_gastos()

    # 1) Gasto menor que o enviado -> exige devolução validada (CA-21).
    sol1_id, s1 = _abrir_e_aprovar(ctx)
    saidas.enviar_recurso(ctx["enviador"].id, s1.id, valor=Dinheiro("300.00"), arquivo=_pdf("t1.pdf"))
    saidas.prestar_contas(
        ctx["solicitante"].id,
        s1.id,
        valor=Dinheiro("250.00"),
        descricao="Sobrou 50",
        arquivo=_png("nf1.png"),
    )
    with pytest.raises(BusinessError) as exc_dif:
        saidas.liquidar(ctx["liquidador"].id, s1.id)
    assert exc_dif.value.code == "DIFERENCA_NAO_ACERTADA"

    # Tentar devolver acima do enviado falha (INV-ENT-03).
    with pytest.raises(BusinessError) as exc_lim:
        saidas.devolver_sobra(ctx["solicitante"].id, s1.id, valor=Dinheiro("300.01"), evidencia_texto="Pix")
    assert exc_lim.value.code == "DEVOLUCAO_ACIMA_DO_ENVIADO"

    dev = saidas.devolver_sobra(
        ctx["solicitante"].id, s1.id, valor=Dinheiro("50.00"), evidencia_texto="Pix devolvido"
    )
    with pytest.raises(BusinessError) as exc_pend:
        saidas.liquidar(ctx["liquidador"].id, s1.id)
    assert exc_pend.value.code == "DEVOLUCAO_PENDENTE"

    from financeiro.services import entradas

    entradas.validar(ctx["liquidador"].id, uuid.UUID(str(dev["id"])), motivo_id=uuid.UUID(ctx["m_val_e"]))

    # Admin solicitante ou próprio solicitante não liquida (CA-24).
    sol_adm = gastos.abrir_solicitacao(
        ctx["admin"].id,
        descricao="Gasto admin",
        categoria_id=ctx["cat_saida"].id,
        setor_id=ctx["setor"].id,
        itens=[{"descricao": "Item", "valor": "100.00"}],
    )
    _aprovar_solicitacao(ctx, sol_adm.id)
    s_adm = Saida.objects.get(solicitacao_id=sol_adm.id)
    saidas.enviar_recurso(ctx["enviador"].id, s_adm.id, valor=Dinheiro("100.00"), arquivo=_pdf("tadm.pdf"))
    saidas.prestar_contas(
        ctx["admin"].id,
        s_adm.id,
        valor=Dinheiro("100.00"),
        descricao="NF adm",
        arquivo=_png("nfadm.png"),
    )
    with pytest.raises(BusinessError) as exc_self:
        saidas.liquidar(ctx["admin"].id, s_adm.id)
    assert exc_self.value.code == "SOLICITANTE_NAO_LIQUIDA"

    saidas.liquidar(ctx["liquidador"].id, s1.id)
    s1.refresh_from_db()
    assert s1.situacao == "LIQUIDADA"
    assert s1.valor_nao_reembolsado == Decimal("0.00")
    assert aprovacoes.situacao_de(sol1_id) == aprovacoes.Situacao.ENCERRADA
    assert len(_notifs_tipo(ctx["solicitante"], tipos.NOTIF_SAIDA_LIQUIDADA)) == 1

    # 2) Gasto maior com complemento aprovado + envio adicional (CA-18, CA-19, CA-22).
    _, s2 = _abrir_e_aprovar(ctx)
    saidas.enviar_recurso(ctx["enviador"].id, s2.id, valor=Dinheiro("300.00"), arquivo=_pdf("t2.pdf"))
    saidas.prestar_contas(
        ctx["solicitante"].id,
        s2.id,
        valor=Dinheiro("380.00"),
        descricao="Aumento de preço",
        arquivo=_png("nf2.png"),
    )
    comp_res = saidas.pedir_complemento(
        ctx["solicitante"].id,
        s2.id,
        itens=[{"descricao": "Diferença unitária", "valor": "80.00"}],
        descricao="Ajuste orçamento",
    )
    with pytest.raises(BusinessError) as exc_dup:
        saidas.pedir_complemento(
            ctx["solicitante"].id,
            s2.id,
            itens=[{"descricao": "Outro", "valor": "10.00"}],
        )
    assert exc_dup.value.code == "COMPLEMENTO_JA_EM_ANDAMENTO"

    comp = Complemento.objects.get(pk=comp_res["id"])
    _aprovar_solicitacao(ctx, comp.solicitacao_id)
    comp.refresh_from_db()
    assert comp.situacao == SituacaoComplemento.APROVADO
    assert len(_notifs_tipo(ctx["enviador"], tipos.NOTIF_COMPLEMENTO_APROVADO)) == 1

    saidas.enviar_recurso(
        ctx["enviador"].id,
        s2.id,
        valor=Dinheiro("80.00"),
        complemento_id=comp.id,
        arquivo=_pdf("ted_comp.pdf"),
    )
    saidas.liquidar(ctx["liquidador"].id, s2.id)
    s2.refresh_from_db()
    assert s2.situacao == "LIQUIDADA"
    assert s2.total_enviado() == Decimal("380.00")

    # 3) Gasto maior sem complemento -> diferença não reembolsada com justificativa obrigatória (CA-23).
    _, s3 = _abrir_e_aprovar(ctx)
    saidas.enviar_recurso(ctx["enviador"].id, s3.id, valor=Dinheiro("300.00"), arquivo=_pdf("t3.pdf"))
    saidas.prestar_contas(
        ctx["solicitante"].id, s3.id, valor=Dinheiro("340.00"), descricao="Diretor pagou diferença"
    )
    with pytest.raises(BusinessError) as exc_just:
        saidas.liquidar(ctx["liquidador"].id, s3.id, justificativa="   ")
    assert exc_just.value.status == 400
    assert "justificativa" in exc_just.value.details

    saidas.liquidar(ctx["liquidador"].id, s3.id, justificativa="Solicitante abriu mão do reembolso.")
    s3.refresh_from_db()
    assert s3.situacao == "LIQUIDADA"
    assert s3.valor_nao_reembolsado == Decimal("40.00")


def test_contrato_publico_eventos_m8_e_devolucao_compatibilidade_m6() -> None:
    ctx = _setup_gastos()
    recebidos: list[fin_public.OrcamentoDeEventoMudou] = []
    events.subscribe(fin_public.OrcamentoDeEventoMudou, recebidos.append)

    evento_id = uuid.uuid7()
    sol_id = fin_public.abrir_solicitacao_orcamentaria(
        solicitante_id=ctx["solicitante"].id,
        descricao="Orçamento amistoso",
        categoria_id=ctx["cat_saida"].id,
        setor_id=ctx["setor"].id,
        itens=[{"descricao": "Arbitragem", "valor": "400.00"}],
        evento_id=evento_id,
    )
    _aprovar_solicitacao(ctx, sol_id)
    assert any(
        ev.evento_id == evento_id
        and ev.solicitacao_id == sol_id
        and ev.acontecimento == "APROVADA"
        and ev.valor == Decimal("400.00")
        for ev in recebidos
    )
    saida = Saida.objects.get(solicitacao_id=sol_id)
    assert saida.evento_id == evento_id

    # Compatibilidade M6 sem saida_id continua funcionando.
    ent_id = fin_public.registrar_devolucao_de_saida(
        categoria_id=ctx["cat_entrada"].id,
        valor=Dinheiro("50.00"),
        data=hoje_local(),
        origem="Evento X",
        referencia="Sobra de evento",
        registrada_por_id=ctx["solicitante"].id,
    )
    assert ent_id is not None

    # Compatibilidade estendida M7 com saida_id funciona para saída após envio.
    saidas.enviar_recurso(ctx["enviador"].id, saida.id, valor=Dinheiro("400.00"), arquivo=_pdf("ev.pdf"))
    dev_id = fin_public.registrar_devolucao_de_saida(
        categoria_id=ctx["cat_entrada"].id,
        valor=Dinheiro("20.00"),
        data=hoje_local(),
        origem="Devolução saída evento",
        referencia="Comprovante pix",
        registrada_por_id=ctx["solicitante"].id,
        saida_id=saida.id,
    )
    assert saida.devolucoes.filter(pk=dev_id).exists()


def test_complemento_contestado_e_reenviado_pela_tela_continua_complemento() -> None:
    """RF-079: reenviado com o conteúdo que a tela de aprovações monta, sem `saida_origem_id`, o complemento
    continua complemento: aprovado, não abre outra saída e aprova o `Complemento` da saída de origem.
    """
    ctx = _setup_gastos()
    _, saida = _abrir_e_aprovar(ctx)
    saidas.enviar_recurso(ctx["enviador"].id, saida.id, valor=Dinheiro("300.00"), arquivo=_pdf("t.pdf"))
    saidas.prestar_contas(
        ctx["solicitante"].id, saida.id, valor=Dinheiro("380.00"), descricao="Preço subiu", arquivo=_png()
    )
    pedido = saidas.pedir_complemento(
        ctx["solicitante"].id, saida.id, itens=[{"descricao": "Diferença", "valor": "80.00"}]
    )
    comp = Complemento.objects.get(pk=pedido["id"])
    base = f"/api/v1/aprovacoes/solicitacoes/{comp.solicitacao_id}"

    c_admin = APIClient()
    c_admin.force_authenticate(user=ctx["admin"])
    m_contestar = garantir_motivo(c_admin, "solicitacao.contestar")
    resp = ctx["c_aprov"].post(
        f"{base}/contestar/",
        {"motivo_id": m_contestar, "mensagem": "Detalhe a diferença por item.", "texto": ""},
        format="json",
    )
    assert resp.status_code == 200, resp.content

    # O mesmo corpo de `conteudoEstruturado()` em `AcoesDaSolicitacao.tsx`: sem `saida_origem_id`.
    resp = ctx["c_sol"].post(
        f"{base}/reenviar/",
        {
            "conteudo": {
                "descricao": "Complemento detalhado",
                "categoria_id": str(ctx["cat_saida"].id),
                "setor_id": str(ctx["setor"].id),
                "itens": [{"descricao": "Diferença de 4 bolas", "valor": "80.00"}],
                "cotacao_id": None,
            }
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content

    _aprovar_solicitacao(ctx, comp.solicitacao_id)

    assert not Saida.objects.filter(solicitacao_id=comp.solicitacao_id).exists()
    comp.refresh_from_db()
    assert comp.situacao == SituacaoComplemento.APROVADO
    assert comp.valor == Decimal("80.00")
    assert Saida.objects.filter(solicitante_id=ctx["solicitante"].id).count() == 1
