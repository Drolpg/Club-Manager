"""Parte 4: Lembretes, atraso automático, questionamentos e isenção (CA-29 a CA-34, CA-46)."""

from datetime import timedelta
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from financeiro import tipos
from financeiro.domain.autorizacao import (
    PERM_COBRANCAS_CRIAR,
    PERM_COBRANCAS_ISENTAR,
    PERM_QUESTIONAMENTOS_DECIDIR,
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

_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _cenario() -> dict[str, Any]:
    admin = novo_diretor("admin", admin=True)
    c_admin = client(admin)
    emissor = novo_diretor("emissor")
    juiz = novo_diretor("juiz")
    devedor = novo_diretor("devedor")
    outro = novo_diretor("outro")
    conceder_permissoes(emissor, PERM_COBRANCAS_CRIAR)
    conceder_permissoes(juiz, PERM_QUESTIONAMENTOS_DECIDIR, PERM_COBRANCAS_ISENTAR)
    conceder_permissoes(outro)

    cat_id = garantir_categoria(c_admin)
    garantir_chave_pix(c_admin, padrao=True)
    m_quest = garantir_motivo(c_admin, tipos.DECISAO_QUESTIONAMENTO_DECIDIR, "Análise da diretoria")
    return {
        "admin": admin,
        "c_admin": c_admin,
        "emissor": emissor,
        "c_emissor": client(emissor),
        "juiz": juiz,
        "c_juiz": client(juiz),
        "devedor": devedor,
        "c_devedor": client(devedor),
        "outro": outro,
        "c_outro": client(outro),
        "cat_id": cat_id,
        "m_quest": m_quest,
    }


def test_ca29_lembretes_tres_dias_e_vencimento_idempotentes_e_pulo_em_validacao() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario()
    hoje = hoje_local()
    venc = hoje + timedelta(days=5)

    c_normal = criar_cobranca(
        ctx["c_emissor"], devedor_id=ctx["devedor"].id, categoria_id=ctx["cat_id"], vencimento=venc
    )
    c_paga = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        categoria_id=ctx["cat_id"],
        vencimento=venc,
        descricao="Já paga",
    )
    resp_pg = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{c_paga['id']}/pagamentos/",
        {
            "forma": "COMPROVANTE",
            "data_pagamento": hoje.isoformat(),
            "comprovante": SimpleUploadedFile("comp.pdf", _PDF_BYTES, content_type="application/pdf"),
        },
        format="multipart",
    )
    assert resp_pg.status_code == 201, resp_pg.content

    # 4 dias antes: fora da janela de 3 dias
    res_d4 = rotina_diaria.executar(venc - timedelta(days=4))
    assert res_d4["lembretes_3_dias"] == 0
    assert res_d4["lembretes_vencimento"] == 0

    # 3 dias antes: envia apenas para a cobrança ABERTA (EM_VALIDACAO fica de fora)
    res_d3 = rotina_diaria.executar(venc - timedelta(days=3))
    assert res_d3["lembretes_3_dias"] == 1
    assert res_d3["lembretes_vencimento"] == 0

    # Rodar novamente no dia seguinte ainda dentro da janela não reenvia (idempotente)
    res_d2 = rotina_diaria.executar(venc - timedelta(days=2))
    assert res_d2["lembretes_3_dias"] == 0

    # No vencimento: envia lembrete do dia uma única vez
    res_d0 = rotina_diaria.executar(venc)
    assert res_d0["lembretes_vencimento"] == 1
    assert res_d0["atrasadas"] == 0
    assert rotina_diaria.executar(venc)["lembretes_vencimento"] == 0

    notifs = notificacoes_do(ctx["c_devedor"])
    assert sum(1 for n in notifs if n["tipo"] == tipos.NOTIF_LEMBRETE_3_DIAS) == 1
    assert sum(1 for n in notifs if n["tipo"] == tipos.NOTIF_VENCIMENTO_HOJE) == 1
    det = ctx["c_devedor"].get(f"{BASE_FIN}cobrancas/{c_normal['id']}/").json()
    assert det["situacao"] == "ABERTA"


def test_ca30_transicao_automatica_para_atrasada_notifica_e_audita_sem_duplicar() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario()
    venc = hoje_local() + timedelta(days=1)

    cobr = criar_cobranca(
        ctx["c_emissor"], devedor_id=ctx["devedor"].id, categoria_id=ctx["cat_id"], vencimento=venc
    )

    res = rotina_diaria.executar(venc + timedelta(days=1))
    assert res["atrasadas"] == 1
    assert rotina_diaria.executar(venc + timedelta(days=2))["atrasadas"] == 0

    det = ctx["c_devedor"].get(f"{BASE_FIN}cobrancas/{cobr['id']}/").json()
    assert det["situacao"] == "ATRASADA"

    hist = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cobr['id']}/historico/").json()
    atraso_reg = [h for h in hist if h["acao"] == "COBRANCA_ATRASADA"]
    assert len(atraso_reg) == 1
    assert atraso_reg[0]["ator"] is None

    notifs_dev = notificacoes_do(ctx["c_devedor"])
    notifs_em = notificacoes_do(ctx["c_emissor"])
    assert any(n["tipo"] == tipos.NOTIF_ATRASADA_DEVEDOR for n in notifs_dev)
    assert any(n["tipo"] == tipos.NOTIF_ATRASADA_FINANCEIRO for n in notifs_em)


def test_ca31_ca32_ca33_questionar_pausar_inadimplencia_e_decidir_manter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from django.utils import timezone

    from financeiro.services import rotina_diaria

    ctx = _cenario()
    hoje = hoje_local()
    venc = hoje + timedelta(days=3)

    cobr = criar_cobranca(
        ctx["c_emissor"], devedor_id=ctx["devedor"].id, categoria_id=ctx["cat_id"], vencimento=venc
    )

    # Outro usuário não pode questionar
    resp_outro = ctx["c_outro"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/questionar/",
        {"texto": "Valor estranho"},
        format="json",
    )
    assert erro(resp_outro) == (403, "SO_O_DEVEDOR")

    # Devedor questiona
    resp_q1 = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/questionar/",
        {"texto": "Já paguei em outro rateio."},
        format="json",
    )
    assert resp_q1.status_code == 201, resp_q1.content
    dados_q1 = resp_q1.json()
    assert dados_q1["tem_questionamento_aberto"] is True
    assert dados_q1["pausada_por_questionamento_em"] == hoje.isoformat()
    assert "questionar" not in dados_q1["acoes"]

    # Segundo questionamento enquanto ABERTO falha (INV-COB-08)
    resp_q2 = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/questionar/",
        {"texto": "Segundo questionamento"},
        format="json",
    )
    assert erro(resp_q2) == (422, "QUESTIONAMENTO_JA_ABERTO")
    assert any(n["tipo"] == tipos.NOTIF_QUESTIONADA for n in notificacoes_do(ctx["c_juiz"]))

    # Enquanto questionamento ABERTO: não lembra nem atrasa na rotina diária (INV-COB-08)
    res_pausada = rotina_diaria.executar(venc + timedelta(days=2))
    assert res_pausada["lembretes_3_dias"] == 0
    assert res_pausada["lembretes_vencimento"] == 0
    assert res_pausada["atrasadas"] == 0

    # Também não aparece em GET /cobrancas/?inadimplentes=true enquanto questionamento está aberto (CA-32)
    cobr_atrasada = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        categoria_id=ctx["cat_id"],
        vencimento=hoje + timedelta(days=1),
        descricao="Já atrasada",
    )
    rotina_diaria.executar(hoje + timedelta(days=2))
    assert (
        ctx["c_devedor"]
        .post(
            f"{BASE_FIN}cobrancas/{cobr_atrasada['id']}/questionar/",
            {"texto": "Cobrança duplicada"},
            format="json",
        )
        .status_code
        == 201
    )
    inad = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/?inadimplentes=true").json()["itens"]
    assert all(item["id"] != cobr_atrasada["id"] for item in inad)

    # Sem permissão não decide questionamento; próprio devedor com permissão também é bloqueado
    resp_sem_perm = ctx["c_outro"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/questionamento/decidir/",
        {"decisao": "MANTER", "motivo_id": ctx["m_quest"], "texto": "Sem permissão"},
        format="json",
    )
    assert erro(resp_sem_perm) == (403, "PERMISSION_DENIED")

    conceder_permissoes(ctx["devedor"], PERM_QUESTIONAMENTOS_DECIDIR)
    resp_dev_dec = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/questionamento/decidir/",
        {"decisao": "MANTER", "motivo_id": ctx["m_quest"], "texto": "Autodecisão"},
        format="json",
    )
    assert erro(resp_dev_dec) == (403, "DEVEDOR_NAO_DECIDE")

    # Juiz decide MANTER em venc + 4 dias -> dias_pausados_inadimplencia soma (venc+4 - venc) = 4
    data_decisao = venc + timedelta(days=4)
    monkeypatch.setattr(timezone, "localdate", lambda: data_decisao)
    resp_dec = ctx["c_juiz"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/questionamento/decidir/",
        {"decisao": "MANTER", "motivo_id": ctx["m_quest"], "texto": "Rateio válido."},
        format="json",
    )
    assert resp_dec.status_code == 200, resp_dec.content
    det = resp_dec.json()
    assert det["tem_questionamento_aberto"] is False
    assert det["pausada_por_questionamento_em"] is None
    assert det["dias_pausados_inadimplencia"] == 4
    assert det["questionamentos"][0]["situacao"] == "DECIDIDO"
    assert det["questionamentos"][0]["decisao"] == "MANTER"
    assert any(n["tipo"] == tipos.NOTIF_QUESTIONAMENTO_DECIDIDO for n in notificacoes_do(ctx["c_devedor"]))

    # Após MANTER, rotina diária marca como ATRASADA normalmente
    assert rotina_diaria.executar(data_decisao)["atrasadas"] == 1
    det_pos = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cobr['id']}/").json()
    assert det_pos["situacao"] == "ATRASADA"


def test_ca33_decidir_questionamento_isentar_e_cancelar() -> None:
    ctx = _cenario()
    hoje = hoje_local()
    m_cancel = garantir_motivo(ctx["c_admin"], tipos.DECISAO_COBRANCA_CANCELAR, "Cancelamento aprovado")

    c1 = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        categoria_id=ctx["cat_id"],
        vencimento=hoje + timedelta(days=3),
    )
    c2 = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        categoria_id=ctx["cat_id"],
        vencimento=hoje + timedelta(days=3),
    )
    assert (
        ctx["c_devedor"]
        .post(f"{BASE_FIN}cobrancas/{c1['id']}/questionar/", {"texto": "Isentar por acordo"}, format="json")
        .status_code
        == 201
    )
    assert (
        ctx["c_devedor"]
        .post(f"{BASE_FIN}cobrancas/{c2['id']}/questionar/", {"texto": "Lançado errado"}, format="json")
        .status_code
        == 201
    )

    resp_is = ctx["c_juiz"].post(
        f"{BASE_FIN}cobrancas/{c1['id']}/questionamento/decidir/",
        {"decisao": "ISENTAR", "motivo_id": ctx["m_quest"], "texto": "Dispensado"},
        format="json",
    )
    assert resp_is.status_code == 200, resp_is.content
    assert resp_is.json()["situacao"] == "ISENTA"
    assert resp_is.json()["acoes"] == []

    # Motivo incompatível com questionamento é recusado com VALIDATION_ERROR (400)
    resp_m_err = ctx["c_juiz"].post(
        f"{BASE_FIN}cobrancas/{c2['id']}/questionamento/decidir/",
        {"decisao": "CANCELAR", "motivo_id": m_cancel, "texto": "Motivo errado"},
        format="json",
    )
    assert erro(resp_m_err) == (400, "VALIDATION_ERROR")

    resp_can = ctx["c_juiz"].post(
        f"{BASE_FIN}cobrancas/{c2['id']}/questionamento/decidir/",
        {"decisao": "CANCELAR", "motivo_id": ctx["m_quest"], "texto": "Cobrança cancelada"},
        format="json",
    )
    assert resp_can.status_code == 200, resp_can.content
    assert resp_can.json()["situacao"] == "CANCELADA"
    assert resp_can.json()["cancelamento"]["texto"] == "Cobrança cancelada"


def test_ca34_ca46_isentar_cobranca_diretamente_cessa_alertas() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario()
    hoje = hoje_local()
    venc = hoje + timedelta(days=2)

    cobr = criar_cobranca(
        ctx["c_emissor"], devedor_id=ctx["devedor"].id, categoria_id=ctx["cat_id"], vencimento=venc
    )

    assert erro(
        ctx["c_outro"].post(
            f"{BASE_FIN}cobrancas/{cobr['id']}/isentar/",
            {"justificativa": "Sem permissão"},
            format="json",
        )
    ) == (403, "PERMISSION_DENIED")

    conceder_permissoes(ctx["devedor"], PERM_COBRANCAS_ISENTAR)
    assert erro(
        ctx["c_devedor"].post(
            f"{BASE_FIN}cobrancas/{cobr['id']}/isentar/",
            {"justificativa": "Autoisenção"},
            format="json",
        )
    ) == (403, "DEVEDOR_NAO_DECIDE")

    # Sem justificativa válida falha validação
    resp_vazio = ctx["c_juiz"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/isentar/",
        {"justificativa": "   "},
        format="json",
    )
    assert erro(resp_vazio) == (400, "VALIDATION_ERROR")

    resp_ok = ctx["c_juiz"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/isentar/",
        {"justificativa": "Diretor afastado por motivo médico."},
        format="json",
    )
    assert resp_ok.status_code == 200, resp_ok.content
    det = resp_ok.json()
    assert det["situacao"] == "ISENTA"
    assert det["isencao"]["justificativa"] == "Diretor afastado por motivo médico."
    assert det["acoes"] == []

    # Lembrete e atraso cessam após isenção (CA-46)
    res_futuro = rotina_diaria.executar(venc + timedelta(days=10))
    assert res_futuro["lembretes_3_dias"] == 0
    assert res_futuro["lembretes_vencimento"] == 0
    assert res_futuro["atrasadas"] == 0

    hist = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cobr['id']}/historico/").json()
    assert any(h["acao"] == "COBRANCA_ISENTA" for h in hist)


def test_inv_cob11_12_17_questionar_em_validacao_e_reabrir_lembretes_negados() -> None:
    ctx = _cenario()
    hoje = hoje_local()
    cobr = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        categoria_id=ctx["cat_id"],
        vencimento=hoje + timedelta(days=1),
    )
    resp_pg = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/pagamentos/",
        {
            "forma": "COMPROVANTE",
            "data_pagamento": hoje.isoformat(),
            "comprovante": SimpleUploadedFile("comp.pdf", _PDF_BYTES, content_type="application/pdf"),
        },
        format="multipart",
    )
    assert resp_pg.status_code == 201

    resp_q = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/questionar/",
        {"texto": "Em validação"},
        format="json",
    )
    assert erro(resp_q) == (422, "NAO_ACEITA_QUESTIONAMENTO")

    resp_is = ctx["c_juiz"].post(
        f"{BASE_FIN}cobrancas/{cobr['id']}/isentar/",
        {"justificativa": "Não pode isentar em validação"},
        format="json",
    )
    assert erro(resp_is) == (422, "NAO_PODE_ISENTAR")
