"""Parte 10: Contrato HTTP das rotas de gastos, cotações, caixa, saídas e estornos."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

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
from financeiro.models import CategoriaFinanceira
from financeiro.tests.conftest import (
    BASE_APROV,
    BASE_FIN,
    client,
    conceder_permissoes,
    criar_cobranca,
    erro,
    garantir_chave_pix,
    garantir_motivo,
    hoje_local,
    novo_diretor,
)
from permissoes import public as permissoes
from tests.apoio import criar_diretor

pytestmark = pytest.mark.django_db

_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _pdf(nome: str = "doc.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, _PDF, content_type="application/pdf")


def _png(nome: str = "img.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, _PNG, content_type="image/png")


def _cenario_http() -> dict[str, Any]:
    admin = novo_diretor("adm_h", admin=True)
    sem_cargo = criar_diretor("semcargo_h")
    sol = novo_diretor("sol_h")
    aprov = novo_diretor("apr_h")
    env = novo_diretor("env_h")
    liq = novo_diretor("liq_h")
    val_ent = novo_diretor("val_h")
    fin_sem_estorno = novo_diretor("fin_h")
    estornador = novo_diretor("est_h")

    conceder_permissoes(sol)
    conceder_permissoes(aprov, PERM_GASTOS_APROVAR)
    conceder_permissoes(env, PERM_SAIDAS_ENVIAR)
    conceder_permissoes(liq, PERM_SAIDAS_LIQUIDAR)
    conceder_permissoes(val_ent, PERM_ENTRADAS_VALIDAR)
    conceder_permissoes(
        fin_sem_estorno,
        PERM_COBRANCAS_CRIAR,
        PERM_PAGAMENTOS_VALIDAR,
        PERM_ENTRADAS_REGISTRAR,
        PERM_ENTRADAS_VALIDAR,
        PERM_GASTOS_APROVAR,
        PERM_SAIDAS_ENVIAR,
        PERM_SAIDAS_LIQUIDAR,
    )
    conceder_permissoes(estornador, PERM_FINANCEIRO_ESTORNAR)

    c_admin = client(admin)
    c_sem_cargo = client(sem_cargo)
    c_sol = client(sol)
    c_aprov = client(aprov)
    c_env = client(env)
    c_liq = client(liq)
    c_val = client(val_ent)
    c_fin = client(fin_sem_estorno)
    c_est = client(estornador)

    cat_saida = CategoriaFinanceira.objects.get(nome="Transporte", natureza="SAIDA")
    cat_ent = CategoriaFinanceira.objects.get(nome="Patrocínio", natureza="ENTRADA")
    cat_div = CategoriaFinanceira.objects.get(nome="Diversos", natureza="ENTRADA")
    setor = permissoes.listar_setores_ativos()[0]
    pix_id = garantir_chave_pix(c_admin, padrao=True)

    return {
        "admin": admin,
        "sol": sol,
        "aprov": aprov,
        "env": env,
        "liq": liq,
        "val_ent": val_ent,
        "c_admin": c_admin,
        "c_anon": APIClient(),
        "c_sem_cargo": c_sem_cargo,
        "c_sol": c_sol,
        "c_aprov": c_aprov,
        "c_env": c_env,
        "c_liq": c_liq,
        "c_val": c_val,
        "c_fin": c_fin,
        "c_est": c_est,
        "cat_saida_id": str(cat_saida.id),
        "cat_ent_id": str(cat_ent.id),
        "cat_div_id": str(cat_div.id),
        "setor_id": str(setor.id),
        "pix_id": pix_id,
        "m_apr": garantir_motivo(c_admin, "solicitacao.aprovar"),
        "m_cont": garantir_motivo(c_admin, "solicitacao.contestar"),
        "m_dev_p": garantir_motivo(c_admin, tipos.DECISAO_PRESTACAO_DEVOLVER),
        "m_val_e": garantir_motivo(c_admin, tipos.DECISAO_ENTRADA_VALIDAR),
        "m_val_p": garantir_motivo(c_admin, tipos.DECISAO_PAGAMENTO_VALIDAR),
        "m_est": garantir_motivo(c_admin, tipos.DECISAO_ESTORNAR),
    }


def _aprovar(c_aprov: Any, sol_id: str, motivo_id: str) -> None:
    r = c_aprov.post(
        f"{BASE_APROV}solicitacoes/{sol_id}/aprovar/",
        {"motivo_id": motivo_id, "texto": "Aprovado"},
        format="json",
    )
    assert r.status_code == 200, r.content


def test_http_401_403_404_barreiras_e_anexos_nosniff() -> None:
    ctx = _cenario_http()
    fake_id = str(uuid.uuid7())

    for url in (
        f"{BASE_FIN}caixa/",
        f"{BASE_FIN}referencias-gastos/",
        f"{BASE_FIN}saidas/",
        f"{BASE_FIN}estornos/",
    ):
        assert ctx["c_anon"].get(url).status_code == 401
        assert ctx["c_sem_cargo"].get(url).status_code == 403

    # Ordem 403 antes de 404 para anexos de cotação, envio e prestação (P6).
    for anexo_url in (
        f"{BASE_FIN}cotacoes/{fake_id}/",
        f"{BASE_FIN}saidas/{fake_id}/envios/{fake_id}/comprovante/",
        f"{BASE_FIN}saidas/{fake_id}/prestacoes/{fake_id}/comprovante/",
    ):
        assert ctx["c_anon"].get(anexo_url).status_code == 401
        assert ctx["c_sem_cargo"].get(anexo_url).status_code == 403
        assert ctx["c_sol"].get(anexo_url).status_code == 404

    # Upload inválido e válido de cotação.
    bad_up = ctx["c_sol"].post(
        f"{BASE_FIN}cotacoes/",
        {"arquivo": SimpleUploadedFile("script.txt", b"alert(1)", content_type="text/plain")},
        format="multipart",
    )
    assert bad_up.status_code == 400

    up = ctx["c_sol"].post(f"{BASE_FIN}cotacoes/", {"arquivo": _pdf("cot.pdf")}, format="multipart")
    assert up.status_code == 201, up.content
    cot = up.json()
    assert cot["nome"] == "cot.pdf"

    dl_sem_cargo = ctx["c_sem_cargo"].get(f"{BASE_FIN}cotacoes/{cot['id']}/")
    assert dl_sem_cargo.status_code == 403

    dl = ctx["c_env"].get(f"{BASE_FIN}cotacoes/{cot['id']}/")
    assert dl.status_code == 200
    assert dl["X-Content-Type-Options"] == "nosniff"
    assert dl["Cache-Control"] == "private, no-store"
    assert dl.content == _PDF


def test_http_ciclo_completo_gasto_saida_devolucao_complemento_liquidacao() -> None:
    ctx = _cenario_http()

    refs = ctx["c_sol"].get(f"{BASE_FIN}referencias-gastos/")
    assert refs.status_code == 200, refs.content
    dados_refs = refs.json()
    assert any(c["id"] == ctx["cat_saida_id"] for c in dados_refs["categorias_saida"])
    assert any(a["id"] == str(ctx["aprov"].id) for a in dados_refs["aprovadores_gastos"])

    cot_id = (
        ctx["c_sol"]
        .post(f"{BASE_FIN}cotacoes/", {"arquivo": _pdf("orc.pdf")}, format="multipart")
        .json()["id"]
    )
    # Quem não aprova o próprio pedido não indica aprovador; sem indicação cria em 201.
    gasto_invalido = ctx["c_sol"].post(
        f"{BASE_FIN}gastos/",
        {
            "descricao": "Fretamento ônibus",
            "categoria_id": ctx["cat_saida_id"],
            "setor_id": ctx["setor_id"],
            "itens": [{"descricao": "Ida e volta", "valor": "500.00"}],
            "cotacao_id": cot_id,
            "aprovador_indicado_id": str(ctx["aprov"].id),
        },
        format="json",
    )
    assert erro(gasto_invalido) == (422, "APROVADOR_INVALIDO")

    gasto = ctx["c_sol"].post(
        f"{BASE_FIN}gastos/",
        {
            "descricao": "Fretamento ônibus",
            "categoria_id": ctx["cat_saida_id"],
            "setor_id": ctx["setor_id"],
            "itens": [{"descricao": "Ida e volta", "valor": "500.00"}],
            "cotacao_id": cot_id,
        },
        format="json",
    )
    assert gasto.status_code == 201, gasto.content
    sol_id = gasto.json()["id"]
    assert Decimal(gasto.json()["valor"]) == Decimal("500.00")

    # Enquanto em análise, não entra em comprometido; após aprovar, soma 500.00.
    caixa_antes = ctx["c_aprov"].get(f"{BASE_FIN}caixa/").json()
    assert caixa_antes["total_comprometido"] == "0.00"
    _aprovar(ctx["c_aprov"], sol_id, ctx["m_apr"])
    assert ctx["c_aprov"].get(f"{BASE_FIN}caixa/").json()["total_comprometido"] == "500.00"

    lista_env = ctx["c_env"].get(f"{BASE_FIN}saidas/?pendentes_envio=1")
    assert lista_env.status_code == 200
    assert len(lista_env.json()["itens"]) == 1
    saida_id = lista_env.json()["itens"][0]["id"]

    # Sem permissão `saidas.enviar` -> 403; com envio sem comprovante -> 400.
    assert ctx["c_sol"].post(f"{BASE_FIN}saidas/{saida_id}/envios/", {"valor": "500.00"}).status_code == 403
    assert ctx["c_env"].post(f"{BASE_FIN}saidas/{saida_id}/envios/", {"valor": "500.00"}).status_code == 400

    env_resp = ctx["c_env"].post(
        f"{BASE_FIN}saidas/{saida_id}/envios/",
        {"valor": "500.00", "comprovante": _pdf("ted500.pdf")},
        format="multipart",
    )
    assert env_resp.status_code == 201, env_resp.content
    envio_id = env_resp.json()["envios"][0]["id"]

    dl_env = ctx["c_sol"].get(f"{BASE_FIN}saidas/{saida_id}/envios/{envio_id}/comprovante/")
    assert dl_env.status_code == 200
    assert dl_env["X-Content-Type-Options"] == "nosniff"
    assert dl_env["Cache-Control"] == "private, no-store"

    # Terceiro não presta contas; solicitante envia e liquidador devolve prestação.
    p_terc = ctx["c_env"].post(
        f"{BASE_FIN}saidas/{saida_id}/prestacoes/",
        {"valor": "450.00", "descricao": "Terceiro", "comprovante": _png("nf.png")},
        format="multipart",
    )
    assert erro(p_terc) == (403, "SO_O_SOLICITANTE")

    p_ok = ctx["c_sol"].post(
        f"{BASE_FIN}saidas/{saida_id}/prestacoes/",
        {"valor": "500.00", "descricao": "Recibo inicial", "comprovante": _png("nf1.png")},
        format="multipart",
    )
    assert p_ok.status_code == 201, p_ok.content
    prest_id = p_ok.json()["prestacoes"][0]["id"]
    dl_prest = ctx["c_liq"].get(f"{BASE_FIN}saidas/{saida_id}/prestacoes/{prest_id}/comprovante/")
    assert dl_prest.status_code == 200
    assert dl_prest["X-Content-Type-Options"] == "nosniff"
    assert dl_prest["Cache-Control"] == "private, no-store"

    assert (
        ctx["c_sol"]
        .post(f"{BASE_FIN}saidas/{saida_id}/devolver-prestacao/", {"motivo_id": ctx["m_dev_p"]})
        .status_code
        == 403
    )
    devol_p = ctx["c_liq"].post(
        f"{BASE_FIN}saidas/{saida_id}/devolver-prestacao/",
        {"motivo_id": ctx["m_dev_p"], "texto": "Valor correto foi 450"},
        format="json",
    )
    assert devol_p.status_code == 200
    assert devol_p.json()["situacao"] == "RECURSO_ENVIADO"

    # Prestação corrigida para 450 -> sobra 50 -> devolução vinculada preservando sigilo (INV-ENT-04).
    p_ok2 = ctx["c_sol"].post(
        f"{BASE_FIN}saidas/{saida_id}/prestacoes/",
        {"valor": "450.00", "descricao": "NF ajustada 450"},
        format="json",
    )
    assert p_ok2.status_code == 201
    dev_sobra = ctx["c_sol"].post(
        f"{BASE_FIN}saidas/{saida_id}/devolucoes/",
        {"valor": "50.00", "evidencia_texto": "Pix devolvido", "comprovante": _pdf("dev50.pdf")},
        format="multipart",
    )
    assert dev_sobra.status_code == 201, dev_sobra.content
    dev_id = dev_sobra.json()["id"]
    assert dev_sobra.json()["saida_id"] == saida_id

    # Comprovante da devolução é restrito (P6 / INV-ENT-04): env e aprovador não têm `entradas.validar`.
    assert ctx["c_env"].get(f"{BASE_FIN}entradas/{dev_id}/comprovante/").status_code == 403
    assert ctx["c_val"].get(f"{BASE_FIN}entradas/{dev_id}/comprovante/").status_code == 200

    assert (
        ctx["c_val"]
        .post(
            f"{BASE_FIN}entradas/{dev_id}/validar/",
            {"motivo_id": ctx["m_val_e"], "texto": "Confirmado"},
            format="json",
        )
        .status_code
        == 200
    )

    liq_resp = ctx["c_liq"].post(f"{BASE_FIN}saidas/{saida_id}/liquidar/", {}, format="json")
    assert liq_resp.status_code == 200, liq_resp.content
    assert liq_resp.json()["situacao"] == "LIQUIDADA"
    assert ctx["c_env"].get(f"{BASE_FIN}caixa/").json()["total_saidas_liquidadas"] == "450.00"

    hist = ctx["c_sol"].get(f"{BASE_FIN}saidas/{saida_id}/historico/")
    assert hist.status_code == 200
    acoes_hist = {item["acao"] for item in hist.json()}
    assert {"SAIDA_ABERTA", "RECURSO_ENVIADO", "PRESTACAO_DEVOLVIDA", "SAIDA_LIQUIDADA"} <= acoes_hist


def test_http_complemento_sem_reembolso_cancelamento_e_estornos() -> None:
    ctx = _cenario_http()

    # Saída 1: cancelamento pré-envio via aprovacoes/cancelar/.
    g1 = (
        ctx["c_sol"]
        .post(
            f"{BASE_FIN}gastos/",
            {
                "descricao": "Compra cancelável",
                "categoria_id": ctx["cat_saida_id"],
                "setor_id": ctx["setor_id"],
                "itens": [{"descricao": "Item", "valor": "120.00"}],
            },
            format="json",
        )
        .json()["id"]
    )
    _aprovar(ctx["c_aprov"], g1, ctx["m_apr"])
    s1_id = ctx["c_env"].get(f"{BASE_FIN}saidas/?pendentes_envio=1").json()["itens"][0]["id"]
    canc = ctx["c_sol"].post(
        f"{BASE_APROV}solicitacoes/{g1}/cancelar/",
        {"motivo": "Não precisou mais"},
        format="json",
    )
    assert canc.status_code == 200
    assert ctx["c_sol"].get(f"{BASE_FIN}saidas/{s1_id}/").json()["situacao"] == "CANCELADA"

    # Saída 2: gasto maior com complemento aprovado + segundo envio + estorno.
    g2 = (
        ctx["c_sol"]
        .post(
            f"{BASE_FIN}gastos/",
            {
                "descricao": "Passagens",
                "categoria_id": ctx["cat_saida_id"],
                "setor_id": ctx["setor_id"],
                "itens": [{"descricao": "Passagem", "valor": "200.00"}],
            },
            format="json",
        )
        .json()["id"]
    )
    _aprovar(ctx["c_aprov"], g2, ctx["m_apr"])
    s2_id = ctx["c_env"].get(f"{BASE_FIN}saidas/?pendentes_envio=1").json()["itens"][0]["id"]
    ctx["c_env"].post(
        f"{BASE_FIN}saidas/{s2_id}/envios/",
        {"valor": "200.00", "comprovante": _pdf("t200.pdf")},
        format="multipart",
    )
    ctx["c_sol"].post(
        f"{BASE_FIN}saidas/{s2_id}/prestacoes/",
        {"valor": "260.00", "descricao": "Subiu tarifa"},
        format="json",
    )
    comp = ctx["c_sol"].post(
        f"{BASE_FIN}saidas/{s2_id}/complementos/",
        {"itens": [{"descricao": "Diferença", "valor": "60.00"}]},
        format="json",
    )
    assert comp.status_code == 201, comp.content
    comp_data = comp.json()
    _aprovar(ctx["c_aprov"], comp_data["solicitacao_id"], ctx["m_apr"])

    env_comp = ctx["c_env"].post(
        f"{BASE_FIN}saidas/{s2_id}/envios/",
        {"valor": "60.00", "complemento_id": comp_data["id"], "comprovante": _pdf("t60.pdf")},
        format="multipart",
    )
    assert env_comp.status_code == 201, env_comp.content
    assert ctx["c_liq"].post(f"{BASE_FIN}saidas/{s2_id}/liquidar/", {}, format="json").status_code == 200

    # Saída 3: gasto maior liquidado sem reembolso com justificativa obrigatória.
    g3 = (
        ctx["c_sol"]
        .post(
            f"{BASE_FIN}gastos/",
            {
                "descricao": "Pedágio extra",
                "categoria_id": ctx["cat_saida_id"],
                "setor_id": ctx["setor_id"],
                "itens": [{"descricao": "Pedágio", "valor": "100.00"}],
            },
            format="json",
        )
        .json()["id"]
    )
    _aprovar(ctx["c_aprov"], g3, ctx["m_apr"])
    s3_id = ctx["c_env"].get(f"{BASE_FIN}saidas/?pendentes_envio=1").json()["itens"][0]["id"]
    ctx["c_env"].post(
        f"{BASE_FIN}saidas/{s3_id}/envios/",
        {"valor": "100.00", "comprovante": _pdf("t100.pdf")},
        format="multipart",
    )
    ctx["c_sol"].post(
        f"{BASE_FIN}saidas/{s3_id}/prestacoes/",
        {"valor": "130.00", "descricao": "30 sem reembolso"},
        format="json",
    )
    assert ctx["c_liq"].post(f"{BASE_FIN}saidas/{s3_id}/liquidar/", {}, format="json").status_code == 400
    liq3 = ctx["c_liq"].post(
        f"{BASE_FIN}saidas/{s3_id}/liquidar/",
        {"justificativa": "Sem reembolso"},
        format="json",
    )
    assert liq3.status_code == 200
    assert liq3.json()["valor_nao_reembolsado"] == "30.00"

    # Estorno: `c_fin` sem `financeiro.estornar` recebe 403; `c_est` estorna saída s2.
    assert (
        ctx["c_fin"]
        .post(
            f"{BASE_FIN}saidas/{s2_id}/estornar/",
            {"motivo_id": ctx["m_est"], "justificativa": "Teste"},
            format="json",
        )
        .status_code
        == 403
    )
    est_s2 = ctx["c_est"].post(
        f"{BASE_FIN}saidas/{s2_id}/estornar/",
        {"motivo_id": ctx["m_est"], "justificativa": "Saída duplicada"},
        format="json",
    )
    assert est_s2.status_code == 201, est_s2.content
    assert est_s2.json()["alvo_tipo"] == "SAIDA"
    assert est_s2.json()["registro"]["situacao"] == "ESTORNADA"
    assert est_s2.json()["registro"]["estorno"]["motivo_texto"]

    assert erro(
        ctx["c_est"].post(
            f"{BASE_FIN}saidas/{s2_id}/estornar/",
            {"motivo_id": ctx["m_est"], "justificativa": "Repetir"},
            format="json",
        )
    ) == (422, "NAO_PODE_ESTORNAR")

    # Entrada e cobrança estornáveis + exposição de `estorno` + bloqueio de recibo.
    ent_id = (
        ctx["c_fin"]
        .post(
            f"{BASE_FIN}entradas/",
            {
                "categoria_id": ctx["cat_ent_id"],
                "valor": "300.00",
                "data": hoje_local().isoformat(),
                "origem": "Patrocínio camisa",
                "evidencia_texto": "TED",
            },
            format="json",
        )
        .json()["id"]
    )
    ctx["c_val"].post(
        f"{BASE_FIN}entradas/{ent_id}/validar/",
        {"motivo_id": ctx["m_val_e"], "texto": "Ok"},
        format="json",
    )
    est_ent = ctx["c_admin"].post(
        f"{BASE_FIN}entradas/{ent_id}/estornar/",
        {"motivo_id": ctx["m_est"], "justificativa": "Estorno entrada"},
        format="json",
    )
    assert est_ent.status_code == 201
    assert ctx["c_sol"].get(f"{BASE_FIN}entradas/{ent_id}/").json()["estorno"]["justificativa"] == (
        "Estorno entrada"
    )

    cob_id = criar_cobranca(
        ctx["c_fin"],
        devedor_id=ctx["sol"].id,
        categoria_id=ctx["cat_div_id"],
        valor="90.00",
        vencimento=hoje_local() + timedelta(days=3),
        chave_pix_id=ctx["pix_id"],
    )["id"]
    ctx["c_sol"].post(
        f"{BASE_FIN}cobrancas/{cob_id}/pagamentos/",
        {"forma": "COMPROVANTE", "data_pagamento": hoje_local().isoformat(), "comprovante": _pdf("p.pdf")},
        format="multipart",
    )
    ctx["c_fin"].post(
        f"{BASE_FIN}cobrancas/{cob_id}/validar-pagamento/",
        {"motivo_id": ctx["m_val_p"], "texto": "Conferido"},
        format="json",
    )
    est_cob = ctx["c_est"].post(
        f"{BASE_FIN}cobrancas/{cob_id}/estornar/",
        {"motivo_id": ctx["m_est"], "justificativa": "Comprovante cancelado"},
        format="json",
    )
    assert est_cob.status_code == 201
    det_cob = ctx["c_sol"].get(f"{BASE_FIN}cobrancas/{cob_id}/").json()
    assert det_cob["situacao"] == "ESTORNADA"
    assert det_cob["estorno"]["justificativa"] == "Comprovante cancelado"
    assert erro(ctx["c_sol"].get(f"{BASE_FIN}cobrancas/{cob_id}/recibo/")) == (422, "NAO_ESTA_PAGA")

    # Paginação de estornos por cursor e filtro.
    p1 = ctx["c_sol"].get(f"{BASE_FIN}estornos/?limite=2").json()
    assert len(p1["itens"]) == 2
    assert p1["tem_mais"] is True
    p2 = ctx["c_sol"].get(f"{BASE_FIN}estornos/?limite=2&antes={p1['itens'][-1]['id']}").json()
    assert len(p2["itens"]) == 1
    assert p2["tem_mais"] is False
    assert len(ctx["c_sol"].get(f"{BASE_FIN}estornos/?alvo_tipo=COBRANCA").json()["itens"]) == 1
