"""Parte 6: Entradas sem devedor, UsuarioDesativado, API pública, paridade e cobertura."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from financeiro import tipos
from financeiro.domain.autorizacao import (
    PERM_COBRANCAS_CRIAR,
    PERM_COBRANCAS_SUSPENDER,
    PERM_ENTRADAS_REGISTRAR,
    PERM_ENTRADAS_VALIDAR,
)
from financeiro.tests.conftest import (
    BASE_FIN,
    client,
    conceder_permissoes,
    criar_cobranca,
    erro,
    garantir_categoria,
    garantir_chave_pix,
    garantir_motivo,
    hoje_local,
    notificacoes_do,
    novo_diretor,
)

pytestmark = pytest.mark.django_db

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _cenario() -> dict[str, Any]:
    admin = novo_diretor("admin", admin=True)
    c_admin = client(admin)
    registrador = novo_diretor("registrador")
    validador = novo_diretor("validador")
    emissor = novo_diretor("emissor")
    suspensor = novo_diretor("suspensor")
    outro = novo_diretor("outro")
    conceder_permissoes(registrador, PERM_ENTRADAS_REGISTRAR)
    conceder_permissoes(validador, PERM_ENTRADAS_VALIDAR)
    conceder_permissoes(emissor, PERM_COBRANCAS_CRIAR)
    conceder_permissoes(suspensor, PERM_COBRANCAS_SUSPENDER)
    conceder_permissoes(outro)

    cat_entrada = garantir_categoria(c_admin, natureza="ENTRADA")
    cat_saida = garantir_categoria(c_admin, natureza="SAIDA")
    pix_id = garantir_chave_pix(c_admin, padrao=True)
    m_val = garantir_motivo(c_admin, tipos.DECISAO_ENTRADA_VALIDAR, "Extrato conferido")
    m_rej = garantir_motivo(c_admin, tipos.DECISAO_ENTRADA_REJEITAR, "Comprovante ilegível")
    return {
        "admin": admin,
        "c_admin": c_admin,
        "registrador": registrador,
        "c_registrador": client(registrador),
        "validador": validador,
        "c_validador": client(validador),
        "emissor": emissor,
        "c_emissor": client(emissor),
        "suspensor": suspensor,
        "c_suspensor": client(suspensor),
        "outro": outro,
        "c_outro": client(outro),
        "cat_entrada": cat_entrada,
        "cat_saida": cat_saida,
        "pix_id": pix_id,
        "m_val": m_val,
        "m_rej": m_rej,
    }


def test_ca42_a_45_ciclo_entradas_sigilo_e_resumo_somente_validadas() -> None:
    ctx = _cenario()
    hoje = hoje_local()

    # Sem evidência nem comprovante falha validação
    resp_sem = ctx["c_registrador"].post(
        f"{BASE_FIN}entradas/",
        {
            "categoria_id": ctx["cat_entrada"],
            "valor": "500.00",
            "data": hoje.isoformat(),
            "origem": "Rifa da camisa",
        },
        format="json",
    )
    assert erro(resp_sem) == (400, "VALIDATION_ERROR")

    # Categoria de SAIDA recusada para Entrada
    resp_saida = ctx["c_registrador"].post(
        f"{BASE_FIN}entradas/",
        {
            "categoria_id": ctx["cat_saida"],
            "valor": "500.00",
            "data": hoje.isoformat(),
            "origem": "Erro de categoria",
            "evidencia_texto": "Texto",
        },
        format="json",
    )
    assert erro(resp_saida) == (422, "CATEGORIA_INATIVA")

    # Entrada 1 com arquivo comprovante -> entra EM_VALIDACAO
    arq = SimpleUploadedFile("recibo_patrocinio.png", _PNG_BYTES, content_type="image/png")
    resp_e1 = ctx["c_registrador"].post(
        f"{BASE_FIN}entradas/",
        {
            "categoria_id": ctx["cat_entrada"],
            "valor": "1200.00",
            "data": hoje.isoformat(),
            "origem": "Padaria Central",
            "evidencia_texto": "Depósito identificado",
            "comprovante": arq,
        },
        format="multipart",
    )
    assert resp_e1.status_code == 201, resp_e1.content
    e1 = resp_e1.json()
    assert e1["situacao"] == "EM_VALIDACAO"
    assert e1["comprovante_disponivel"] is True
    assert e1["acoes"] == []  # registrador não pode validar/rejeitar a própria entrada

    # Entrada 2 com texto apenas (será rejeitada)
    resp_e2 = ctx["c_registrador"].post(
        f"{BASE_FIN}entradas/",
        {
            "categoria_id": ctx["cat_entrada"],
            "valor": "300.00",
            "data": hoje.isoformat(),
            "origem": "Doação anônima",
            "evidencia_texto": "Aguardando depósito",
        },
        format="json",
    )
    assert resp_e2.status_code == 201, resp_e2.content
    e2 = resp_e2.json()

    assert any(n["tipo"] == tipos.NOTIF_ENTRADA_REGISTRADA for n in notificacoes_do(ctx["c_validador"]))

    # Antes da validação, resumo é zero
    resumo_inicial = ctx["c_outro"].get(f"{BASE_FIN}entradas/resumo/").json()
    assert resumo_inicial["quantidade"] == 0
    assert Decimal(resumo_inicial["total"]) == Decimal("0.00")

    # Sigilo do comprovante: outro diretor sem permissão NÃO acessa (403); registrador e validador sim
    assert erro(ctx["c_outro"].get(f"{BASE_FIN}entradas/{e1['id']}/comprovante/")) == (
        403,
        "PERMISSION_DENIED",
    )
    r_comp_reg = ctx["c_registrador"].get(f"{BASE_FIN}entradas/{e1['id']}/comprovante/")
    assert r_comp_reg.status_code == 200
    assert r_comp_reg["X-Content-Type-Options"] == "nosniff"
    r_comp_val = ctx["c_validador"].get(f"{BASE_FIN}entradas/{e1['id']}/comprovante/")
    assert r_comp_val.status_code == 200

    # Registrador com permissão de validar ainda é bloqueado (INV-ENT-05)
    conceder_permissoes(ctx["registrador"], PERM_ENTRADAS_VALIDAR)
    assert erro(
        ctx["c_registrador"].post(
            f"{BASE_FIN}entradas/{e1['id']}/validar/",
            {"motivo_id": ctx["m_val"], "texto": "Autovalidação"},
            format="json",
        )
    ) == (403, "REGISTRADOR_NAO_VALIDA")

    # Validador valida e1 e rejeita e2
    det_v = ctx["c_validador"].get(f"{BASE_FIN}entradas/{e1['id']}/").json()
    assert det_v["acoes"] == ["validar", "rejeitar"]

    resp_val = ctx["c_validador"].post(
        f"{BASE_FIN}entradas/{e1['id']}/validar/",
        {"motivo_id": ctx["m_val"], "texto": "Caiu na conta do clube."},
        format="json",
    )
    assert resp_val.status_code == 200, resp_val.content
    assert resp_val.json()["situacao"] == "VALIDADA"
    assert resp_val.json()["acoes"] == []

    resp_rej = ctx["c_validador"].post(
        f"{BASE_FIN}entradas/{e2['id']}/rejeitar/",
        {"motivo_id": ctx["m_rej"], "texto": "Não localizado no extrato."},
        format="json",
    )
    assert resp_rej.status_code == 200, resp_rej.content
    assert resp_rej.json()["situacao"] == "REJEITADA"

    # Apenas entradas VALIDADAS contam no resumo (INV-ENT-01)
    resumo_final = ctx["c_outro"].get(f"{BASE_FIN}entradas/resumo/").json()
    assert resumo_final["quantidade"] == 1
    assert Decimal(resumo_final["total"]) == Decimal("1200.00")

    # Filtros e histórico
    list_val = ctx["c_outro"].get(f"{BASE_FIN}entradas/?situacao=VALIDADA").json()["itens"]
    assert [item["id"] for item in list_val] == [e1["id"]]
    hist = ctx["c_outro"].get(f"{BASE_FIN}entradas/{e1['id']}/historico/").json()
    assert {h["acao"] for h in hist} >= {"ENTRADA_REGISTRADA", "ENTRADA_VALIDADA"}
    assert any(n["tipo"] == tipos.NOTIF_ENTRADA_DECIDIDA for n in notificacoes_do(ctx["c_registrador"]))


def test_evento_usuario_desativado_encerra_suspensoes_e_notifica_sem_apagar_cobrancas() -> None:
    ctx = _cenario()
    hoje = hoje_local()
    alvo = novo_diretor("alvo")
    conceder_permissoes(alvo)

    cob = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=alvo.id,
        categoria_id=ctx["cat_entrada"],
        vencimento=hoje + timedelta(days=5),
    )
    resp_susp = ctx["c_suspensor"].post(
        f"{BASE_FIN}suspensoes/",
        {
            "diretor_id": str(alvo.id),
            "inicio": hoje.isoformat(),
            "fim": (hoje + timedelta(days=30)).isoformat(),
            "justificativa": "Férias",
        },
        format="json",
    )
    assert resp_susp.status_code == 201, resp_susp.content
    susp_id = resp_susp.json()["id"]

    # Desativar o diretor via API de acesso dispara UsuarioDesativado
    resp_desat = ctx["c_admin"].post(f"/api/v1/acesso/usuarios/{alvo.id}/desativar/")
    assert resp_desat.status_code == 200, resp_desat.content

    # Suspensão vigente encerrada automaticamente
    susp_todas = ctx["c_emissor"].get(f"{BASE_FIN}suspensoes/?todas=true").json()
    susp_alvo = next(s for s in susp_todas if s["id"] == susp_id)
    assert susp_alvo["situacao"] == "ENCERRADA"
    assert susp_alvo["encerrada_em"] is not None

    # Cobrança aberta não foi cancelada nem apagada
    det_cob = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cob['id']}/").json()
    assert det_cob["situacao"] == "ABERTA"

    # Quem cria cobranças é notificado sobre o diretor desativado
    assert any(n["tipo"] == tipos.NOTIF_DIRETOR_DESATIVADO for n in notificacoes_do(ctx["c_emissor"]))


def test_financeiro_public_api_e_devolucao_de_saida() -> None:
    from financeiro import public as financeiro_pub
    from kernel.dinheiro import Dinheiro

    ctx = _cenario()
    hoje = hoje_local()

    cat_info = financeiro_pub.obter_categoria_ativa(uuid.UUID(ctx["cat_entrada"]), natureza="ENTRADA")
    assert cat_info.id == uuid.UUID(ctx["cat_entrada"])
    assert cat_info.natureza == "ENTRADA"

    cats_ent = financeiro_pub.listar_categorias_ativas(natureza="ENTRADA")
    assert any(c.id == cat_info.id for c in cats_ent)

    entrada_id = financeiro_pub.registrar_devolucao_de_saida(
        categoria_id=cat_info.id,
        valor=Dinheiro("180.00"),
        data=hoje,
        origem="Sobra de adiantamento de viagem",
        referencia="Prestação #42",
        registrada_por_id=ctx["registrador"].id,
    )
    det = ctx["c_validador"].get(f"{BASE_FIN}entradas/{entrada_id}/").json()
    assert det["tipo"] == "DEVOLUCAO"
    assert det["situacao"] == "EM_VALIDACAO"

    # Ainda não validada -> não entra no resumo público
    assert financeiro_pub.resumo_entradas_validadas().total == Decimal("0.00")
    assert (
        ctx["c_validador"]
        .post(
            f"{BASE_FIN}entradas/{entrada_id}/validar/",
            {"motivo_id": ctx["m_val"], "texto": "Devolução conferida"},
            format="json",
        )
        .status_code
        == 200
    )
    resumo = financeiro_pub.resumo_entradas_validadas(de=hoje, ate=hoje, categoria_id=cat_info.id)
    assert resumo.quantidade == 1
    assert resumo.total == Decimal("180.00")


def test_recorrencias_e_suspensoes_validacoes_filtros_e_historicos() -> None:
    ctx = _cenario()
    hoje = hoje_local()
    alvo = novo_diretor("socio")
    conceder_permissoes(alvo)

    # Validações de agenda na criação de recorrência
    r_sem_err = ctx["c_emissor"].post(
        f"{BASE_FIN}recorrencias/",
        {
            "devedor_id": str(alvo.id),
            "categoria_id": ctx["cat_entrada"],
            "descricao": "Dia inválido semanal",
            "valor": "50.00",
            "periodicidade": "SEMANAL",
            "dia_vencimento": 9,
        },
        format="json",
    )
    assert erro(r_sem_err) == (400, "VALIDATION_ERROR")

    r_anual_err = ctx["c_emissor"].post(
        f"{BASE_FIN}recorrencias/",
        {
            "devedor_id": str(alvo.id),
            "categoria_id": ctx["cat_entrada"],
            "descricao": "Anual sem mês",
            "valor": "50.00",
            "periodicidade": "ANUAL",
            "dia_vencimento": 10,
        },
        format="json",
    )
    assert erro(r_anual_err) == (400, "VALIDATION_ERROR")

    r_mensal = ctx["c_emissor"].post(
        f"{BASE_FIN}recorrencias/",
        {
            "devedor_id": str(alvo.id),
            "categoria_id": ctx["cat_entrada"],
            "descricao": "Mensalidade regular",
            "valor": "90.00",
            "periodicidade": "MENSAL",
            "dia_vencimento": 15,
            "chave_pix_id": ctx["pix_id"],
            "a_partir_de": date(hoje.year, hoje.month, 1).isoformat(),
        },
        format="json",
    )
    assert r_mensal.status_code == 201
    rec_id = r_mensal.json()["id"]

    # Listagem e histórico de recorrência
    lista_recs = ctx["c_outro"].get(f"{BASE_FIN}recorrencias/?devedor_id={alvo.id}").json()
    assert len(lista_recs) == 1
    assert ctx["c_emissor"].post(f"{BASE_FIN}recorrencias/{rec_id}/desativar/").status_code == 200
    assert ctx["c_outro"].get(f"{BASE_FIN}recorrencias/").json() == []
    assert len(ctx["c_outro"].get(f"{BASE_FIN}recorrencias/?todas=true").json()) == 1
    assert len(ctx["c_outro"].get(f"{BASE_FIN}recorrencias/{rec_id}/historico/").json()) >= 2
    assert erro(ctx["c_outro"].get(f"{BASE_FIN}recorrencias/{uuid.uuid7()}/historico/")) == (
        404,
        "NOT_FOUND",
    )

    # Suspensão: erros e listagem/encerramento/histórico
    r_susp_inval = ctx["c_suspensor"].post(
        f"{BASE_FIN}suspensoes/",
        {
            "diretor_id": str(alvo.id),
            "inicio": (hoje + timedelta(days=5)).isoformat(),
            "fim": hoje.isoformat(),
            "justificativa": "Fim anterior ao início",
        },
        format="json",
    )
    assert erro(r_susp_inval) == (400, "VALIDATION_ERROR")

    r_susp_ok = ctx["c_suspensor"].post(
        f"{BASE_FIN}suspensoes/",
        {
            "diretor_id": str(alvo.id),
            "recorrencia_id": rec_id,
            "inicio": hoje.isoformat(),
            "justificativa": "Suspensão indeterminada",
        },
        format="json",
    )
    assert r_susp_ok.status_code == 201
    susp_id = r_susp_ok.json()["id"]
    assert len(ctx["c_outro"].get(f"{BASE_FIN}suspensoes/?diretor_id={alvo.id}").json()) == 1
    assert ctx["c_suspensor"].post(f"{BASE_FIN}suspensoes/{susp_id}/encerrar/").status_code == 200
    assert erro(ctx["c_suspensor"].post(f"{BASE_FIN}suspensoes/{susp_id}/encerrar/")) == (
        422,
        "SUSPENSAO_JA_ENCERRADA",
    )
    assert len(ctx["c_outro"].get(f"{BASE_FIN}suspensoes/{susp_id}/historico/").json()) == 2


def test_paridade_acoes_cobranca_com_execucao_nas_rotas() -> None:
    ctx = _cenario()
    devedor = novo_diretor("dev_paridade")
    conceder_permissoes(devedor)
    cob = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=devedor.id,
        categoria_id=ctx["cat_entrada"],
        vencimento=hoje_local() + timedelta(days=2),
    )

    c_dev = client(devedor)
    det_dev = c_dev.get(f"{BASE_FIN}cobrancas/{cob['id']}/").json()
    assert set(det_dev["acoes"]) == {"registrar_pagamento", "questionar"}

    det_outro = ctx["c_outro"].get(f"{BASE_FIN}cobrancas/{cob['id']}/").json()
    assert det_outro["acoes"] == []
    assert erro(
        ctx["c_outro"].post(
            f"{BASE_FIN}cobrancas/{cob['id']}/isentar/", {"justificativa": "Nao"}, format="json"
        )
    ) == (
        403,
        "PERMISSION_DENIED",
    )

    det_admin = ctx["c_admin"].get(f"{BASE_FIN}cobrancas/{cob['id']}/").json()
    assert {"isentar", "cancelar"} <= set(det_admin["acoes"])
