"""Parte 3: Recorrências, suspensões, geração automática e rotina diária (CA-21 a CA-28)."""

import uuid
from datetime import date
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from financeiro import tipos
from financeiro.domain.autorizacao import (
    PERM_COBRANCAS_CRIAR,
    PERM_COBRANCAS_SUSPENDER,
    PERM_PAGAMENTOS_VALIDAR,
)
from financeiro.tests.conftest import (
    BASE_FIN,
    client,
    conceder_permissoes,
    erro,
    garantir_categoria,
    garantir_chave_pix,
    garantir_motivo,
    notificacoes_do,
    novo_diretor,
)
from tests.apoio import Situacao

pytestmark = pytest.mark.django_db

_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _cenario_recorrencia() -> dict[str, Any]:
    admin = novo_diretor("admin", admin=True)
    c_admin = client(admin)
    emissor = novo_diretor("emissor")
    validador = novo_diretor("validador")
    suspensor = novo_diretor("suspensor")
    devedor = novo_diretor("devedor")
    outro_cargo = novo_diretor("outro")
    conceder_permissoes(emissor, PERM_COBRANCAS_CRIAR)
    conceder_permissoes(validador, PERM_PAGAMENTOS_VALIDAR)
    conceder_permissoes(suspensor, PERM_COBRANCAS_SUSPENDER)
    conceder_permissoes(outro_cargo)

    cat_id = garantir_categoria(c_admin)
    pix_id = garantir_chave_pix(c_admin, padrao=True)
    m_val = garantir_motivo(c_admin, tipos.DECISAO_PAGAMENTO_VALIDAR, "Conferido")
    return {
        "admin": admin,
        "c_admin": c_admin,
        "emissor": emissor,
        "c_emissor": client(emissor),
        "validador": validador,
        "c_validador": client(validador),
        "suspensor": suspensor,
        "c_suspensor": client(suspensor),
        "devedor": devedor,
        "c_devedor": client(devedor),
        "c_outro_cargo": client(outro_cargo),
        "cat_id": cat_id,
        "pix_id": pix_id,
        "m_val": m_val,
    }


def _criar_recorrencia(
    c_emissor: Any,
    *,
    devedor_id: uuid.UUID,
    cat_id: str,
    pix_id: str,
    periodicidade: str = "MENSAL",
    dia_vencimento: int = 10,
    mes_vencimento: int | None = None,
    antecedencia_dias: int = 10,
    valor: str = "200.00",
    a_partir_de: date = date(2026, 3, 1),
    descricao: str = "Mensalidade diretoria",
) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "devedor_id": str(devedor_id),
        "categoria_id": cat_id,
        "descricao": descricao,
        "valor": valor,
        "periodicidade": periodicidade,
        "dia_vencimento": dia_vencimento,
        "mes_vencimento": mes_vencimento,
        "antecedencia_dias": antecedencia_dias,
        "limite_de_inadimplencia": 30,
        "chave_pix_id": pix_id,
        "a_partir_de": a_partir_de.isoformat(),
    }
    resp = c_emissor.post(f"{BASE_FIN}recorrencias/", corpo, format="json")
    assert resp.status_code == 201, resp.content
    dados: dict[str, Any] = resp.json()
    return dados


def test_ca21_ca22_geracao_mensal_na_janela_e_idempotencia() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario_recorrencia()
    _criar_recorrencia(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        cat_id=ctx["cat_id"],
        pix_id=ctx["pix_id"],
        dia_vencimento=10,
        antecedencia_dias=10,
        a_partir_de=date(2026, 4, 1),
    )

    # Dia 30/03 é 11 dias antes de 10/04 -> fora da janela
    assert rotina_diaria.executar(date(2026, 3, 30))["recorrencias_geradas"] == 0

    # Dia 31/03 é 10 dias antes de 10/04 -> gera competência 2026-04 e notifica
    res1 = rotina_diaria.executar(date(2026, 3, 31))
    assert res1["recorrencias_geradas"] == 1

    # Rodar novamente no mesmo dia ou em dias seguidos não duplica (CA-22)
    assert rotina_diaria.executar(date(2026, 3, 31))["recorrencias_geradas"] == 0
    assert rotina_diaria.executar(date(2026, 4, 1))["recorrencias_geradas"] == 0
    assert rotina_diaria.executar(date(2026, 4, 5))["recorrencias_geradas"] == 0

    minhas = ctx["c_devedor"].get(f"{BASE_FIN}minhas-cobrancas/").json()["itens"]
    assert len(minhas) == 1
    assert minhas[0]["competencia"] == "2026-04"
    assert minhas[0]["vencimento"] == "2026-04-10"
    assert any(n["tipo"] == tipos.NOTIF_COBRANCA_CRIADA for n in notificacoes_do(ctx["c_devedor"]))


def test_ca23_recorrencia_semanal_e_anual_e_mes_curto() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario_recorrencia()
    # Semanal: sexta-feira (5), antecedência 4 dias
    _criar_recorrencia(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        cat_id=ctx["cat_id"],
        pix_id=ctx["pix_id"],
        periodicidade="SEMANAL",
        dia_vencimento=5,
        antecedencia_dias=4,
        a_partir_de=date(2026, 5, 1),
        descricao="Rateio semanal",
    )
    # Anual: 31 de fevereiro ajusta para 28/02/2027 (ano não bissexto)
    _criar_recorrencia(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        cat_id=ctx["cat_id"],
        pix_id=ctx["pix_id"],
        periodicidade="ANUAL",
        dia_vencimento=31,
        mes_vencimento=2,
        antecedencia_dias=5,
        a_partir_de=date(2027, 2, 1),
        descricao="Anuidade diretoria",
    )

    # 2026-05-04 é segunda -> 4 dias antes de sexta 2026-05-08
    res_sem = rotina_diaria.executar(date(2026, 5, 4))
    assert res_sem["recorrencias_geradas"] == 1
    # 2027-02-23 -> 5 dias antes de 2027-02-28 (anual) e também dentro da janela semanal de 2027-W08
    res_anual = rotina_diaria.executar(date(2027, 2, 23))
    assert res_anual["recorrencias_geradas"] == 2

    lista = ctx["c_emissor"].get(f"{BASE_FIN}cobrancas/").json()["itens"]
    pares = {(i["descricao"], i["competencia"], i["vencimento"]) for i in lista}
    assert ("Rateio semanal", "2026-W19", "2026-05-08") in pares
    assert ("Anuidade diretoria", "2027", "2027-02-28") in pares


def test_ca24_ca25_editar_desativar_e_devedor_inativo() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario_recorrencia()
    cat2 = garantir_categoria(ctx["c_admin"], nome="Taxa extra")
    rec = _criar_recorrencia(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        cat_id=ctx["cat_id"],
        pix_id=ctx["pix_id"],
        dia_vencimento=10,
        antecedencia_dias=5,
        valor="100.00",
        a_partir_de=date(2026, 6, 1),
    )

    assert rotina_diaria.executar(date(2026, 6, 5))["recorrencias_geradas"] == 1

    # Edita recorrência -> só futuras usam os dados novos
    r_edit = ctx["c_emissor"].post(
        f"{BASE_FIN}recorrencias/{rec['id']}/editar/",
        {
            "categoria_id": cat2,
            "descricao": "Mensalidade reajustada",
            "valor": "180.00",
            "dia_vencimento": 15,
            "mes_vencimento": None,
            "antecedencia_dias": 5,
            "limite_de_inadimplencia": 20,
            "chave_pix_id": ctx["pix_id"],
        },
        format="json",
    )
    assert r_edit.status_code == 200, r_edit.content
    assert rotina_diaria.executar(date(2026, 7, 10))["recorrencias_geradas"] == 1

    itens = ctx["c_devedor"].get(f"{BASE_FIN}minhas-cobrancas/").json()["itens"]
    por_comp = {i["competencia"]: i for i in itens}
    assert por_comp["2026-06"]["valor"] == "100.00"
    assert por_comp["2026-07"]["valor"] == "180.00"
    assert por_comp["2026-07"]["descricao"] == "Mensalidade reajustada"

    # Desativa recorrência -> não gera mais (CA-25)
    assert ctx["c_emissor"].post(f"{BASE_FIN}recorrencias/{rec['id']}/desativar/").status_code == 200
    assert rotina_diaria.executar(date(2026, 8, 10))["recorrencias_geradas"] == 0

    # Histórico da recorrência contém criação, alteração e desativação
    r_hist = ctx["c_outro_cargo"].get(f"{BASE_FIN}recorrencias/{rec['id']}/historico/")
    assert r_hist.status_code == 200
    assert len(r_hist.json()) == 3

    # Devedor inativo não gera cobranças (CA-25)
    inativo = novo_diretor("inativo_rec", situacao=Situacao.INATIVO)
    r_inat = ctx["c_emissor"].post(
        f"{BASE_FIN}recorrencias/",
        {
            "devedor_id": str(inativo.id),
            "categoria_id": ctx["cat_id"],
            "descricao": "Tentativa inativo",
            "valor": "50.00",
            "periodicidade": "MENSAL",
            "dia_vencimento": 10,
            "antecedencia_dias": 5,
            "a_partir_de": "2026-06-01",
        },
        format="json",
    )
    assert erro(r_inat) == (422, "DEVEDOR_INATIVO")


def test_ca26_ca27_suspensao_valida_nao_gera_no_periodo_e_validacao_de_entrada() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario_recorrencia()
    rec = _criar_recorrencia(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        cat_id=ctx["cat_id"],
        pix_id=ctx["pix_id"],
        dia_vencimento=10,
        antecedencia_dias=5,
        a_partir_de=date(2026, 4, 1),
    )

    # Sem justificativa ou com fim antes do início -> recusa 400 VALIDATION_ERROR (CA-27)
    r_sem_just = ctx["c_suspensor"].post(
        f"{BASE_FIN}suspensoes/",
        {
            "diretor_id": str(ctx["devedor"].id),
            "inicio": "2026-05-01",
            "fim": "2026-05-31",
            "justificativa": " ",
        },
        format="json",
    )
    assert erro(r_sem_just) == (400, "VALIDATION_ERROR")

    r_fim_antes = ctx["c_suspensor"].post(
        f"{BASE_FIN}suspensoes/",
        {
            "diretor_id": str(ctx["devedor"].id),
            "inicio": "2026-05-10",
            "fim": "2026-05-01",
            "justificativa": "Licença médica",
        },
        format="json",
    )
    assert erro(r_fim_antes) == (400, "VALIDATION_ERROR")

    # Sem permissão de suspender -> 403
    assert (
        ctx["c_outro_cargo"]
        .post(
            f"{BASE_FIN}suspensoes/",
            {
                "diretor_id": str(ctx["devedor"].id),
                "inicio": "2026-05-01",
                "fim": "2026-05-20",
                "justificativa": "Viagem oficial",
            },
            format="json",
        )
        .status_code
        == 403
    )

    # Cria suspensão cobrindo vencimento 10/05/2026
    r_susp = ctx["c_suspensor"].post(
        f"{BASE_FIN}suspensoes/",
        {
            "diretor_id": str(ctx["devedor"].id),
            "recorrencia_id": rec["id"],
            "inicio": "2026-05-01",
            "fim": "2026-05-20",
            "justificativa": "Licença médica",
        },
        format="json",
    )
    assert r_susp.status_code == 201, r_susp.content
    susp_id = r_susp.json()["id"]

    # Abril gera normalmente; maio NÃO gera durante a suspensão; após 20/05 maio NÃO gera retroativo
    assert rotina_diaria.executar(date(2026, 4, 5))["recorrencias_geradas"] == 1
    assert rotina_diaria.executar(date(2026, 5, 5))["recorrencias_geradas"] == 0
    assert rotina_diaria.executar(date(2026, 5, 21))["recorrencias_geradas"] == 0
    # Junho gera normalmente
    assert rotina_diaria.executar(date(2026, 6, 5))["recorrencias_geradas"] == 1

    # Encerrar suspensão
    r_enc = ctx["c_suspensor"].post(f"{BASE_FIN}suspensoes/{susp_id}/encerrar/")
    assert r_enc.status_code == 200
    assert r_enc.json()["situacao"] == "ENCERRADA"
    assert erro(ctx["c_suspensor"].post(f"{BASE_FIN}suspensoes/{susp_id}/encerrar/")) == (
        422,
        "SUSPENSAO_JA_ENCERRADA",
    )

    comps = {c["competencia"] for c in ctx["c_devedor"].get(f"{BASE_FIN}minhas-cobrancas/").json()["itens"]}
    assert comps == {"2026-04", "2026-06"}


def test_ca28_ciclo_completo_recorrencia_ate_pagamento_no_historico() -> None:
    from financeiro.services import rotina_diaria

    ctx = _cenario_recorrencia()
    _criar_recorrencia(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        cat_id=ctx["cat_id"],
        pix_id=ctx["pix_id"],
        dia_vencimento=15,
        antecedencia_dias=5,
        a_partir_de=date(2026, 9, 1),
    )

    assert rotina_diaria.executar(date(2026, 9, 10))["recorrencias_geradas"] == 1
    cob_id = ctx["c_devedor"].get(f"{BASE_FIN}minhas-cobrancas/").json()["itens"][0]["id"]

    anexo = SimpleUploadedFile("rec.pdf", _PDF_BYTES, content_type="application/pdf")
    assert (
        ctx["c_devedor"]
        .post(
            f"{BASE_FIN}cobrancas/{cob_id}/pagamentos/",
            {
                "forma": "COMPROVANTE",
                "data_pagamento": date(2026, 9, 11).isoformat(),
                "comprovante": anexo,
            },
            format="multipart",
        )
        .status_code
        == 201
    )
    assert (
        ctx["c_validador"]
        .post(
            f"{BASE_FIN}cobrancas/{cob_id}/validar-pagamento/",
            {"motivo_id": ctx["m_val"], "texto": "Pago"},
            format="json",
        )
        .status_code
        == 200
    )

    hist = ctx["c_devedor"].get(f"{BASE_FIN}cobrancas/{cob_id}/historico/").json()
    acoes = [item["acao"] for item in hist]
    assert acoes == [
        "COBRANCA_GERADA_RECORRENCIA",
        "COBRANCA_PAGAMENTO_REGISTRADO",
        "COBRANCA_PAGAMENTO_VALIDADO",
    ]
    assert hist[0]["ator"] is None
    assert hist[1]["ator"]["id"] == str(ctx["devedor"].id)
    assert hist[2]["ator"]["id"] == str(ctx["validador"].id)


def test_task_rotina_diaria_agendada() -> None:
    from financeiro.tasks import processar_rotina_diaria

    res = processar_rotina_diaria()
    assert isinstance(res, dict)
    assert "recorrencias_geradas" in res
    assert res["recorrencias_geradas"] == 0
