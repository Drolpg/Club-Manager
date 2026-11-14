"""Testes da Parte 1: cadastros, cobrança avulsa/lote, cancelamento e consultas (CA-02..10, 45, 47, 48)."""

from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from auditoria import public as auditoria
from tests import apoio
from tests.apoio import Usuario


def _hoje() -> date:
    return timezone.localdate()


def _motivo_id(client_admin: APIClient, tipo_de_decisao: str) -> str:
    resp = client_admin.get("/api/v1/aprovacoes/motivos/", {"tipo_de_decisao": tipo_de_decisao})
    assert resp.status_code == 200
    return str(resp.json()[0]["id"])


def _categoria_id(client_admin: APIClient, nome: str = "Mensalidade") -> str:
    resp = client_admin.get("/api/v1/financeiro/categorias/", {"natureza": "ENTRADA"})
    assert resp.status_code == 200
    return str(next(item["id"] for item in resp.json() if item["nome"] == nome))


def _criar_chave_padrao(
    client_admin: APIClient, *, tipo: str = "EMAIL", chave: str = "pix@clube.org.br"
) -> str:
    resp = client_admin.post(
        "/api/v1/financeiro/chaves-pix/",
        {
            "tipo": tipo,
            "chave": chave,
            "nome_recebedor": "Clube Atletico Exemplo",
            "cidade": "São Paulo",
            "padrao": True,
        },
    )
    assert resp.status_code == 201, resp.content
    return str(resp.json()["id"])


@pytest.mark.django_db
def test_CA02_admin_mantem_categorias_sem_apagar_e_outros_sao_negados(
    client_admin: APIClient, diretor: Usuario
) -> None:
    apoio.dar_cargo(diretor)
    apoio.conceder(diretor, "cobrancas.criar")
    client_fin = apoio.cliente_de(diretor)

    # Diretor não admin pode listar, mas não cria.
    assert client_fin.get("/api/v1/financeiro/categorias/").status_code == 200
    assert (
        client_fin.post(
            "/api/v1/financeiro/categorias/", {"nome": "Bazar", "natureza": "ENTRADA"}
        ).status_code
        == 403
    )

    criada = client_admin.post(
        "/api/v1/financeiro/categorias/", {"nome": "Material esportivo", "natureza": "SAIDA"}
    )
    assert criada.status_code == 201
    cat_id = criada.json()["id"]

    # Duplicada na mesma natureza -> 409; em natureza oposta -> 201.
    dup = client_admin.post(
        "/api/v1/financeiro/categorias/", {"nome": "material esportivo", "natureza": "SAIDA"}
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "CATEGORIA_JA_EXISTE"

    outra_nat = client_admin.post(
        "/api/v1/financeiro/categorias/", {"nome": "Mensalidade", "natureza": "SAIDA"}
    )
    assert outra_nat.status_code == 201

    renomeada = client_admin.post(f"/api/v1/financeiro/categorias/{cat_id}/renomear/", {"nome": "Uniformes"})
    assert renomeada.status_code == 200
    assert renomeada.json()["nome"] == "Uniformes"

    desativada = client_admin.post(f"/api/v1/financeiro/categorias/{cat_id}/desativar/")
    assert desativada.status_code == 200
    assert not desativada.json()["ativa"]

    ativas = client_fin.get("/api/v1/financeiro/categorias/").json()
    assert all(c["id"] != cat_id for c in ativas)
    todas = client_admin.get("/api/v1/financeiro/categorias/", {"todas": "1"}).json()
    assert any(c["id"] == cat_id and not c["ativa"] for c in todas)

    # Diretor normal não pode pedir `?todas=1`.
    assert client_fin.get("/api/v1/financeiro/categorias/", {"todas": "1"}).status_code == 403

    reativada = client_admin.post(f"/api/v1/financeiro/categorias/{cat_id}/reativar/")
    assert reativada.status_code == 200
    assert reativada.json()["ativa"]

    # CA-48: não existe DELETE.
    assert client_admin.delete(f"/api/v1/financeiro/categorias/{cat_id}/").status_code in (404, 405)

    hist = client_admin.get(f"/api/v1/financeiro/categorias/{cat_id}/historico/")
    assert hist.status_code == 200
    assert [r["acao"] for r in hist.json()] == [
        "CATEGORIA_FINANCEIRA_CRIADA",
        "CATEGORIA_FINANCEIRA_RENOMEADA",
        "CATEGORIA_FINANCEIRA_DESATIVADA",
        "CATEGORIA_FINANCEIRA_REATIVADA",
    ]


@pytest.mark.django_db
def test_CA03_admin_cadastra_chaves_pix_com_padrao_unica_e_valida_formato(
    client_admin: APIClient, diretor: Usuario
) -> None:
    apoio.dar_cargo(diretor)
    client_dir = apoio.cliente_de(diretor)
    assert (
        client_dir.post(
            "/api/v1/financeiro/chaves-pix/",
            {"tipo": "EMAIL", "chave": "a@b.com", "nome_recebedor": "A", "cidade": "SP", "padrao": True},
        ).status_code
        == 403
    )

    invalida = client_admin.post(
        "/api/v1/financeiro/chaves-pix/",
        {
            "tipo": "CPF",
            "chave": "111.111.111-11",
            "nome_recebedor": "Clube",
            "cidade": "São Paulo",
            "padrao": True,
        },
    )
    assert invalida.status_code == 400
    assert invalida.json()["error"]["code"] == "VALIDATION_ERROR"

    id1 = _criar_chave_padrao(client_admin, tipo="EMAIL", chave="Fin@Clube.ORG.br")
    r2 = client_admin.post(
        "/api/v1/financeiro/chaves-pix/",
        {
            "tipo": "TELEFONE",
            "chave": "(11) 98888-7777",
            "nome_recebedor": "Clube Atletico",
            "cidade": "Campinas",
            "padrao": True,
        },
    )
    assert r2.status_code == 201
    id2 = r2.json()["id"]
    assert r2.json()["chave"] == "+5511988887777"

    chaves = client_admin.get("/api/v1/financeiro/chaves-pix/").json()
    assert sum(1 for c in chaves if c["padrao"]) == 1
    assert next(c["padrao"] for c in chaves if c["id"] == id2)
    assert not next(c["padrao"] for c in chaves if c["id"] == id1)

    editada = client_admin.post(
        f"/api/v1/financeiro/chaves-pix/{id1}/editar/",
        {
            "tipo": "CNPJ",
            "chave": "11.222.333/0001-81",
            "nome_recebedor": "Clube CNPJ",
            "cidade": "Santos",
        },
    )
    assert editada.status_code == 200
    assert editada.json()["chave"] == "11222333000181"

    marcada = client_admin.post(f"/api/v1/financeiro/chaves-pix/{id1}/marcar-padrao/")
    assert marcada.status_code == 200
    assert marcada.json()["padrao"]
    assert client_admin.delete(f"/api/v1/financeiro/chaves-pix/{id1}/").status_code in (404, 405)
    assert client_admin.get(f"/api/v1/financeiro/chaves-pix/{id1}/historico/").status_code == 200


@pytest.mark.django_db
def test_CA04_CA07_CA08_cobranca_avulsa_snapshot_pix_notificacao_e_qrcode(client_admin: APIClient) -> None:
    _criar_chave_padrao(client_admin)
    cat_id = _categoria_id(client_admin)
    devedor = apoio.criar_diretor("carlos")
    apoio.dar_cargo(devedor)
    fin = apoio.criar_diretor("fin1")
    apoio.dar_cargo(fin)
    apoio.conceder(fin, "cobrancas.criar")
    client_fin = apoio.cliente_de(fin)

    vencimento = (_hoje() + timedelta(days=7)).isoformat()
    criada = client_fin.post(
        "/api/v1/financeiro/cobrancas/",
        {
            "devedor_id": str(devedor.id),
            "categoria_id": cat_id,
            "descricao": "Mensalidade novembro",
            "valor": "150.00",
            "vencimento": vencimento,
        },
    )
    assert criada.status_code == 201, criada.content
    cob = criada.json()
    cob_id = cob["id"]
    assert cob["situacao"] == "ABERTA"
    assert cob["valor"] == "150.00"
    assert "pix@clube.org.br" in cob["pix_copia_e_cola"]
    assert "150.00" in cob["pix_copia_e_cola"]
    assert "<svg" in cob["qrcode_svg"]

    # Devedor vê na caixa de notificações e em minhas-cobrancas.
    client_dev = apoio.cliente_de(devedor)
    notifs = client_dev.get("/api/v1/notificacoes/").json()["itens"]
    assert any(n["tipo"] == "financeiro.cobranca_criada" and n["pede_acao"] for n in notifs)

    # CA-08: desativar ou trocar chave padrão depois não muda cobrança já gerada.
    chaves = client_admin.get("/api/v1/financeiro/chaves-pix/").json()
    chave_antiga_id = chaves[0]["id"]
    client_admin.post(f"/api/v1/financeiro/chaves-pix/{chave_antiga_id}/desativar/")
    _criar_chave_padrao(client_admin, tipo="EMAIL", chave="nova@clube.org.br")

    detalhe = client_dev.get(f"/api/v1/financeiro/cobrancas/{cob_id}/").json()
    assert detalhe["pix_copia_e_cola"] == cob["pix_copia_e_cola"]
    assert "pix@clube.org.br" in detalhe["pix_copia_e_cola"]
    assert "registrar_pagamento" in detalhe["acoes"]


@pytest.mark.django_db
def test_CA05_CA09_recusa_cobranca_invalida_ou_sem_permissao(client_admin: APIClient) -> None:
    chave_id = _criar_chave_padrao(client_admin)
    cat_id = _categoria_id(client_admin)
    dev_ativo = apoio.criar_diretor("dev_ativo")
    dev_inativo = apoio.criar_diretor("dev_inativo", situacao=apoio.Situacao.INATIVO)
    sem_perm = apoio.criar_diretor("sem_perm")
    apoio.dar_cargo(sem_perm)
    fin = apoio.criar_diretor("fin2")
    apoio.dar_cargo(fin)
    apoio.conceder(fin, "cobrancas.criar")

    client_fin = apoio.cliente_de(fin)
    client_sem = apoio.cliente_de(sem_perm)
    amanha = (_hoje() + timedelta(days=1)).isoformat()

    # CA-09: quem não tem cobrancas.criar é negado.
    assert (
        client_sem.post(
            "/api/v1/financeiro/cobrancas/",
            {
                "devedor_id": str(dev_ativo.id),
                "categoria_id": cat_id,
                "descricao": "Teste",
                "valor": "50.00",
                "vencimento": amanha,
            },
        ).status_code
        == 403
    )

    # Valor zero e negativo -> 422 VALOR_INVALIDO.
    for val in ("0.00", "-10.00"):
        r = client_fin.post(
            "/api/v1/financeiro/cobrancas/",
            {
                "devedor_id": str(dev_ativo.id),
                "categoria_id": cat_id,
                "descricao": "Teste",
                "valor": val,
                "vencimento": amanha,
            },
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALOR_INVALIDO"

    # Vencimento no passado -> 422 VENCIMENTO_NO_PASSADO.
    r_passado = client_fin.post(
        "/api/v1/financeiro/cobrancas/",
        {
            "devedor_id": str(dev_ativo.id),
            "categoria_id": cat_id,
            "descricao": "Teste",
            "valor": "10.00",
            "vencimento": (_hoje() - timedelta(days=1)).isoformat(),
        },
    )
    assert r_passado.status_code == 422
    assert r_passado.json()["error"]["code"] == "VENCIMENTO_NO_PASSADO"

    # Devedor inativo -> 422 DEVEDOR_INATIVO.
    r_inativo = client_fin.post(
        "/api/v1/financeiro/cobrancas/",
        {
            "devedor_id": str(dev_inativo.id),
            "categoria_id": cat_id,
            "descricao": "Teste",
            "valor": "10.00",
            "vencimento": amanha,
        },
    )
    assert r_inativo.status_code == 422
    assert r_inativo.json()["error"]["code"] == "DEVEDOR_INATIVO"

    # Categoria inativa -> 422 CATEGORIA_INATIVA.
    client_admin.post(f"/api/v1/financeiro/categorias/{cat_id}/desativar/")
    r_cat = client_fin.post(
        "/api/v1/financeiro/cobrancas/",
        {
            "devedor_id": str(dev_ativo.id),
            "categoria_id": cat_id,
            "descricao": "Teste",
            "valor": "10.00",
            "vencimento": amanha,
        },
    )
    assert r_cat.status_code == 422
    assert r_cat.json()["error"]["code"] == "CATEGORIA_INATIVA"
    client_admin.post(f"/api/v1/financeiro/categorias/{cat_id}/reativar/")

    # Chave inativa -> 422 CHAVE_PIX_INATIVA; sem chave padrão -> CHAVE_PIX_PADRAO_NAO_CONFIGURADA.
    client_admin.post(f"/api/v1/financeiro/chaves-pix/{chave_id}/desativar/")
    r_chave = client_fin.post(
        "/api/v1/financeiro/cobrancas/",
        {
            "devedor_id": str(dev_ativo.id),
            "categoria_id": cat_id,
            "descricao": "Teste",
            "valor": "10.00",
            "vencimento": amanha,
            "chave_pix_id": chave_id,
        },
    )
    assert r_chave.status_code == 422
    assert r_chave.json()["error"]["code"] == "CHAVE_PIX_INATIVA"

    r_sem_padrao = client_fin.post(
        "/api/v1/financeiro/cobrancas/",
        {
            "devedor_id": str(dev_ativo.id),
            "categoria_id": cat_id,
            "descricao": "Teste",
            "valor": "10.00",
            "vencimento": amanha,
        },
    )
    assert r_sem_padrao.status_code == 422
    assert r_sem_padrao.json()["error"]["code"] == "CHAVE_PIX_PADRAO_NAO_CONFIGURADA"


@pytest.mark.django_db
def test_CA06_lote_atomico_e_todos_ativos_com_cargo(client_admin: APIClient) -> None:
    _criar_chave_padrao(client_admin)
    cat_id = _categoria_id(client_admin)
    d1 = apoio.criar_diretor("dir_um")
    d2 = apoio.criar_diretor("dir_dois")
    sem_cargo = apoio.criar_diretor("sem_cargo")
    inativo = apoio.criar_diretor("inativo_lote", situacao=apoio.Situacao.INATIVO)
    apoio.dar_cargo(d1)
    apoio.dar_cargo(d2)
    apoio.conceder(d1, "cobrancas.criar")
    client_fin = apoio.cliente_de(d1)
    amanha = (_hoje() + timedelta(days=5)).isoformat()

    # Lista com diretor inativo aborta tudo (nenhuma cobrança criada).
    falha = client_fin.post(
        "/api/v1/financeiro/cobrancas/lote/",
        {
            "devedor_ids": [str(d1.id), str(inativo.id)],
            "categoria_id": cat_id,
            "descricao": "Cota extra",
            "valor": "100.00",
            "vencimento": amanha,
        },
    )
    assert falha.status_code == 422
    assert falha.json()["error"]["code"] == "DEVEDOR_INATIVO"
    assert client_fin.get("/api/v1/financeiro/cobrancas/").json()["itens"] == []

    # todos_ativos_com_cargo=true cobra todos ativos com cargo (d1, d2) e exclui sem_cargo.
    sucesso = client_fin.post(
        "/api/v1/financeiro/cobrancas/lote/",
        {
            "todos_ativos_com_cargo": True,
            "categoria_id": cat_id,
            "descricao": "Cota extra",
            "valor": "100.00",
            "vencimento": amanha,
        },
    )
    assert sucesso.status_code == 201, sucesso.content
    criadas = sucesso.json()
    ids_devedores = {item["devedor"]["id"] for item in criadas}
    assert ids_devedores == {str(d1.id), str(d2.id)}
    assert str(sem_cargo.id) not in ids_devedores


@pytest.mark.django_db
def test_CA10_CA45_CA47_cancelar_minhas_cobrancas_e_auditoria(client_admin: APIClient) -> None:
    _criar_chave_padrao(client_admin)
    cat_id = _categoria_id(client_admin)
    dev_sem_cargo = apoio.criar_diretor("sem_cargo_visao")
    outro_sem_cargo = apoio.criar_diretor("outro_sem_cargo")
    fin = apoio.criar_diretor("fin3")
    apoio.dar_cargo(fin)
    apoio.conceder(fin, "cobrancas.criar")
    client_fin = apoio.cliente_de(fin)

    c_res = client_fin.post(
        "/api/v1/financeiro/cobrancas/",
        {
            "devedor_id": str(dev_sem_cargo.id),
            "categoria_id": cat_id,
            "descricao": "Taxa camisa",
            "valor": "90.00",
            "vencimento": (_hoje() + timedelta(days=3)).isoformat(),
        },
    )
    assert c_res.status_code == 201
    cob_id = c_res.json()["id"]

    # Diretor sem cargo NÃO vê lista geral (403), mas vê minhas-cobrancas e o próprio detalhe (CA-45).
    client_dev = apoio.cliente_de(dev_sem_cargo)
    assert client_dev.get("/api/v1/financeiro/cobrancas/").status_code == 403
    minhas = client_dev.get("/api/v1/financeiro/minhas-cobrancas/")
    assert minhas.status_code == 200
    assert [i["id"] for i in minhas.json()["itens"]] == [cob_id]
    assert client_dev.get(f"/api/v1/financeiro/cobrancas/{cob_id}/").status_code == 200

    # Outro diretor sem cargo recebe 403 até para cobrança alheia (evita enumeração de IDs).
    client_outro = apoio.cliente_de(outro_sem_cargo)
    assert client_outro.get(f"/api/v1/financeiro/cobrancas/{cob_id}/").status_code == 403

    # Cancelar sem permissão é negado; fin só tem cobrancas.criar, não cobrancas.cancelar.
    motivo = _motivo_id(client_admin, "financeiro.cobranca_cancelar")
    assert (
        client_fin.post(f"/api/v1/financeiro/cobrancas/{cob_id}/cancelar/", {"motivo_id": motivo}).status_code
        == 403
    )

    # Sem motivo -> 400 VALIDATION_ERROR.
    assert client_admin.post(f"/api/v1/financeiro/cobrancas/{cob_id}/cancelar/", {}).status_code == 400

    # Admin cancela com motivo -> CANCELADA, recusa segundo cancelamento (422) e grava auditoria (CA-47).
    cancelada = client_admin.post(
        f"/api/v1/financeiro/cobrancas/{cob_id}/cancelar/",
        {"motivo_id": motivo, "texto": "Lançada no período errado"},
    )
    assert cancelada.status_code == 200
    assert cancelada.json()["situacao"] == "CANCELADA"
    assert client_admin.delete(f"/api/v1/financeiro/cobrancas/{cob_id}/").status_code == 405

    rep = client_admin.post(f"/api/v1/financeiro/cobrancas/{cob_id}/cancelar/", {"motivo_id": motivo})
    assert rep.status_code == 422
    assert rep.json()["error"]["code"] == "NAO_PODE_CANCELAR"

    hist = client_dev.get(f"/api/v1/financeiro/cobrancas/{cob_id}/historico/")
    assert hist.status_code == 200
    assert [h["acao"] for h in hist.json()] == ["COBRANCA_CRIADA", "COBRANCA_CANCELADA"]
    assert auditoria.historico_do_item("cobranca", cob_id)[-1].acao == "COBRANCA_CANCELADA"
