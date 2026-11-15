"""Parte 5: Inadimplência, convocação, justificativa, perdão e renegociação (CA-35 a CA-41)."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from financeiro import tipos
from financeiro.domain.autorizacao import PERM_COBRANCAS_CRIAR, PERM_DIVIDAS_DECIDIR
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


def _cenario() -> dict[str, Any]:
    admin = novo_diretor("admin", admin=True)
    c_admin = client(admin)
    emissor = novo_diretor("emissor")
    decisor = novo_diretor("decisor")
    devedor = novo_diretor("devedor")
    outro = novo_diretor("outro")
    conceder_permissoes(emissor, PERM_COBRANCAS_CRIAR)
    conceder_permissoes(decisor, PERM_DIVIDAS_DECIDIR)
    conceder_permissoes(outro)

    cat_id = garantir_categoria(c_admin)
    garantir_chave_pix(c_admin, padrao=True)
    m_divida = garantir_motivo(c_admin, tipos.DECISAO_DIVIDA_DECIDIR, "Deliberação da diretoria")
    return {
        "admin": admin,
        "c_admin": c_admin,
        "emissor": emissor,
        "c_emissor": client(emissor),
        "decisor": decisor,
        "c_decisor": client(decisor),
        "devedor": devedor,
        "c_devedor": client(devedor),
        "outro": outro,
        "c_outro": client(outro),
        "cat_id": cat_id,
        "m_divida": m_divida,
    }


def _criar_atrasada(
    ctx: dict[str, Any], *, limite_dias: int = 10, valor: str = "300.00", dias_apos_venc: int = 1
) -> tuple[dict[str, Any], Any]:
    from financeiro.services import rotina_diaria

    hoje = hoje_local()
    venc = hoje + timedelta(days=1)
    cob = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        categoria_id=ctx["cat_id"],
        valor=valor,
        vencimento=venc,
        limite_de_inadimplencia=limite_dias,
    )
    rotina_diaria.executar(venc + timedelta(days=dias_apos_venc))
    return cob, venc


def test_ca35_convocacao_automatica_no_limite_e_respeito_aos_dias_pausados() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario()
    cob, venc = _criar_atrasada(ctx, limite_dias=10)

    # Simula 4 dias pausados por questionamento resolvido (novo limite = venc + 10 + 4 = venc + 14)
    from financeiro.models import Cobranca

    c_obj = Cobranca.objects.get(pk=cob["id"])
    c_obj.dias_pausados_inadimplencia = 4
    c_obj.save(update_fields=["dias_pausados_inadimplencia"])

    # 13 dias após vencimento ainda está no limite estendido pela pausa -> não convoca
    res_antes = rotina_diaria.executar(venc + timedelta(days=13))
    assert res_antes["convocadas"] == 0

    # 14 dias após vencimento -> convoca uma única vez
    res_no_dia = rotina_diaria.executar(venc + timedelta(days=14))
    assert res_no_dia["convocadas"] == 1
    assert rotina_diaria.executar(venc + timedelta(days=15))["convocadas"] == 0

    det = ctx["c_devedor"].get(f"{BASE_FIN}cobrancas/{cob['id']}/").json()
    assert det["tem_convocacao_aberta"] is True
    assert det["convocacao"]["convocado_em"] is not None
    assert "justificar_divida" in det["acoes"]

    hist = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cob['id']}/historico/").json()
    conv_reg = [h for h in hist if h["acao"] == "COBRANCA_DEVEDOR_CONVOCADO"]
    assert len(conv_reg) == 1
    assert conv_reg[0]["ator"] is None

    assert any(n["tipo"] == tipos.NOTIF_DEVEDOR_CONVOCADO for n in notificacoes_do(ctx["c_devedor"]))
    assert any(n["tipo"] == tipos.NOTIF_CONVOCACAO_FINANCEIRO for n in notificacoes_do(ctx["c_decisor"]))


def test_ca36_justificar_divida_exclusiva_devedor_e_exige_convocacao() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario()
    cob, venc = _criar_atrasada(ctx, limite_dias=5)

    # Antes da convocação não há convocação aberta
    resp_sem_conv = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/justificar-divida/",
        {"texto": "Aguardando pagamento"},
        format="json",
    )
    assert erro(resp_sem_conv) == (422, "SEM_CONVOCACAO_ABERTA")

    rotina_diaria.executar(venc + timedelta(days=5))

    # Outro usuário não pode justificar
    resp_outro = ctx["c_outro"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/justificar-divida/",
        {"texto": "Terceiro falando"},
        format="json",
    )
    assert erro(resp_outro) == (403, "SO_O_DEVEDOR")

    resp_ok = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/justificar-divida/",
        {"texto": "Salário atrasado neste mês."},
        format="json",
    )
    assert resp_ok.status_code == 200, resp_ok.content
    det = resp_ok.json()
    assert det["convocacao"]["justificativa_do_devedor"] == "Salário atrasado neste mês."
    assert det["convocacao"]["justificada_em"] is not None

    hist = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cob['id']}/historico/").json()
    assert any(h["acao"] == "COBRANCA_DIVIDA_JUSTIFICADA" for h in hist)
    assert any(n["tipo"] == tipos.NOTIF_DIVIDA_JUSTIFICADA for n in notificacoes_do(ctx["c_decisor"]))


def test_ca37_perdoar_divida_atrasada_fecha_convocacao_e_bloqueia_devedor() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario()
    hoje = hoje_local()
    aberta = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        categoria_id=ctx["cat_id"],
        vencimento=hoje + timedelta(days=5),
    )

    # Cobrança ainda ABERTA não pode ser perdoada
    resp_aberta = ctx["c_decisor"].post(
        f"{BASE_FIN}cobrancas/{aberta['id']}/perdoar/",
        {"motivo_id": ctx["m_divida"], "texto": "Ainda não venceu"},
        format="json",
    )
    assert erro(resp_aberta) == (422, "NAO_ESTA_ATRASADA")

    cob, venc = _criar_atrasada(ctx, limite_dias=5)
    rotina_diaria.executar(venc + timedelta(days=5))

    # Sem permissão -> 403; próprio devedor com permissão -> 403 DEVEDOR_NAO_DECIDE
    assert erro(
        ctx["c_outro"].post(
            f"{BASE_FIN}cobrancas/{cob['id']}/perdoar/",
            {"motivo_id": ctx["m_divida"], "texto": "Sem perm"},
            format="json",
        )
    ) == (403, "PERMISSION_DENIED")

    conceder_permissoes(ctx["devedor"], PERM_DIVIDAS_DECIDIR)
    assert erro(
        ctx["c_devedor"].post(
            f"{BASE_FIN}cobrancas/{cob['id']}/perdoar/",
            {"motivo_id": ctx["m_divida"], "texto": "Autoperdão"},
            format="json",
        )
    ) == (403, "DEVEDOR_NAO_DECIDE")

    resp_ok = ctx["c_decisor"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/perdoar/",
        {"motivo_id": ctx["m_divida"], "texto": "Caso excepcional aprovado."},
        format="json",
    )
    assert resp_ok.status_code == 200, resp_ok.content
    det = resp_ok.json()
    assert det["situacao"] == "PERDOADA"
    assert det["perdao"]["texto"] == "Caso excepcional aprovado."
    assert det["tem_convocacao_aberta"] is False
    assert det["convocacao"]["decisao"] == "PERDOAR"
    assert det["acoes"] == []

    hist = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cob['id']}/historico/").json()
    assert any(h["acao"] == "COBRANCA_PERDOADA" for h in hist)
    assert any(n["tipo"] == tipos.NOTIF_DIVIDA_DECIDIDA for n in notificacoes_do(ctx["c_devedor"]))


def test_ca38_ca39_inv_ren_renegociar_atrasada_cria_parcelas_e_eh_atomica() -> None:
    from financeiro.models import Cobranca, NaoPodeApagar, Renegociacao
    from financeiro.services import rotina_diaria

    ctx = _cenario()
    cob, venc = _criar_atrasada(ctx, limite_dias=5, valor="300.00")
    rotina_diaria.executar(venc + timedelta(days=5))
    hoje = hoje_local()

    # Lista vazia falha sem alterar a cobrança
    resp_vazia = ctx["c_decisor"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/renegociar/",
        {"motivo_id": ctx["m_divida"], "texto": "Sem parcelas", "parcelas": []},
        format="json",
    )
    assert erro(resp_vazia) == (422, "PARCELAS_INVALIDAS")

    # Parcela 2 no passado deve desfazer toda a transação (INV-REN-02): nem parcela 1, nem Renegociacao
    resp_inval = ctx["c_decisor"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/renegociar/",
        {
            "motivo_id": ctx["m_divida"],
            "texto": "Segunda parcela inválida",
            "parcelas": [
                {"valor": "150.00", "vencimento": (hoje + timedelta(days=10)).isoformat()},
                {"valor": "150.00", "vencimento": (hoje - timedelta(days=1)).isoformat()},
            ],
        },
        format="json",
    )
    assert erro(resp_inval) == (422, "VENCIMENTO_NO_PASSADO")
    assert Cobranca.objects.filter(cobranca_origem_id=cob["id"]).count() == 0
    assert Renegociacao.objects.filter(cobranca_original_id=cob["id"]).count() == 0
    assert Cobranca.objects.get(pk=cob["id"]).situacao == "ATRASADA"

    # Renegociação válida em 2 parcelas
    p1_venc = hoje + timedelta(days=15)
    p2_venc = hoje + timedelta(days=45)
    resp_ok = ctx["c_decisor"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/renegociar/",
        {
            "motivo_id": ctx["m_divida"],
            "texto": "Acordo em 2x.",
            "parcelas": [
                {"valor": "120.00", "vencimento": p1_venc.isoformat()},
                {"valor": "130.00", "vencimento": p2_venc.isoformat()},
            ],
        },
        format="json",
    )
    assert resp_ok.status_code == 200, resp_ok.content
    det = resp_ok.json()
    assert det["situacao"] == "RENEGOCIADA"
    assert det["tem_convocacao_aberta"] is False
    assert det["renegociacao"]["quantidade_parcelas"] == 2
    assert Decimal(det["renegociacao"]["valor_acordado"]) == Decimal("250.00")
    assert len(det["parcelas"]) == 2
    assert all(p["cobranca_origem_id"] == cob["id"] for p in det["parcelas"])
    assert all(p["situacao"] == "ABERTA" for p in det["parcelas"])

    # Renegociação é imutável (INV-REN-01)
    reneg_obj = Renegociacao.objects.get(cobranca_original_id=cob["id"])
    reneg_obj.decisao_texto = "Alterado"
    with pytest.raises(NaoPodeApagar):
        reneg_obj.save()

    hist_orig = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cob['id']}/historico/").json()
    assert any(h["acao"] == "COBRANCA_RENEGOCIADA" for h in hist_orig)
    for p in det["parcelas"]:
        hist_p = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{p['id']}/historico/").json()
        assert any(h["acao"] == "COBRANCA_CRIADA" for h in hist_p)


def test_ca40_ca41_manter_divida_fecha_convocacao_e_mantem_atrasada() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario()
    cob, venc = _criar_atrasada(ctx, limite_dias=5)

    # Sem convocação aberta -> erro
    assert erro(
        ctx["c_decisor"].post(
            f"{BASE_FIN}cobrancas/{cob['id']}/manter-divida/",
            {"motivo_id": ctx["m_divida"], "texto": "Manter sem convocação"},
            format="json",
        )
    ) == (422, "SEM_CONVOCACAO_ABERTA")

    rotina_diaria.executar(venc + timedelta(days=5))

    conceder_permissoes(ctx["devedor"], PERM_DIVIDAS_DECIDIR)
    assert erro(
        ctx["c_devedor"].post(
            f"{BASE_FIN}cobrancas/{cob['id']}/manter-divida/",
            {"motivo_id": ctx["m_divida"], "texto": "Autodecisão"},
            format="json",
        )
    ) == (403, "DEVEDOR_NAO_DECIDE")

    resp_ok = ctx["c_decisor"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/manter-divida/",
        {"motivo_id": ctx["m_divida"], "texto": "Cobrança mantida integralmente."},
        format="json",
    )
    assert resp_ok.status_code == 200, resp_ok.content
    det = resp_ok.json()
    assert det["situacao"] == "ATRASADA"
    assert det["tem_convocacao_aberta"] is False
    assert det["convocacao"]["decisao"] == "MANTER"
    assert "manter_divida" not in det["acoes"]
    det_dev = ctx["c_devedor"].get(f"{BASE_FIN}cobrancas/{cob['id']}/").json()
    assert "registrar_pagamento" in det_dev["acoes"]

    hist = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/{cob['id']}/historico/").json()
    assert any(h["acao"] == "COBRANCA_DIVIDA_MANTIDA" for h in hist)
    assert any(n["tipo"] == tipos.NOTIF_DIVIDA_DECIDIDA for n in notificacoes_do(ctx["c_devedor"]))
