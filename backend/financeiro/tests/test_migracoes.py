"""Testes das migrações iniciais de `financeiro` e reversibilidade (CA-01, Decisão 8)."""

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

from aprovacoes import public as aprovacoes
from financeiro.models import CategoriaFinanceira, ChavePix
from permissoes import public as permissoes
from tests import apoio


@pytest.mark.django_db
def test_CA01_sistema_nasce_com_cinco_categorias_entrada_e_sem_chave_pix() -> None:
    nomes = list(CategoriaFinanceira.objects.filter(natureza="ENTRADA").values_list("nome", flat=True))
    assert set(nomes) == {"Ajuda", "Diversos", "Mensalidade", "Patrocínio", "Rifa"}
    assert ChavePix.objects.count() == 0


@pytest.mark.django_db
def test_decisao8_setor_financeiro_nasce_com_quatro_permissoes_operacionais(
    client_admin: APIClient,
) -> None:
    diretor = apoio.criar_diretor("fin_inicial")
    setores = client_admin.get("/api/v1/permissoes/setores/").json()
    cargos = client_admin.get("/api/v1/permissoes/cargos/").json()
    financeiro_id = next(item["id"] for item in setores if item["nome"] == "Financeiro")
    cargo_id = next(item["id"] for item in cargos if item["nome"] == "Tesoureiro")

    resp = client_admin.put(
        f"/api/v1/permissoes/usuarios/{diretor.id}/classificacao/",
        {"cargo_id": cargo_id, "setor_ids": [financeiro_id]},
    )
    assert resp.status_code == 200

    concedidas = permissoes.permissoes_de(diretor.id)
    assert set(concedidas) == {
        "cobrancas.criar",
        "pagamentos.validar",
        "entradas.registrar",
        "entradas.validar",
    }


@pytest.mark.django_db
def test_nasce_com_motivos_iniciais_dos_sete_tipos_de_decisao(client_admin: APIClient) -> None:
    tipos = {
        "financeiro.pagamento_validar",
        "financeiro.pagamento_rejeitar",
        "financeiro.cobranca_cancelar",
        "financeiro.questionamento_decidir",
        "financeiro.divida_decidir",
        "financeiro.entrada_validar",
        "financeiro.entrada_rejeitar",
    }
    resp = client_admin.get("/api/v1/aprovacoes/motivos/")
    assert resp.status_code == 200
    por_tipo: dict[str, list[str]] = {t: [] for t in tipos}
    for item in resp.json():
        if item["tipo_de_decisao"] in por_tipo:
            por_tipo[item["tipo_de_decisao"]].append(item["id"])
    for codigo, ids in por_tipo.items():
        assert len(ids) >= 1, f"Tipo {codigo} sem motivos iniciais"
    # Também garante que todos os 7 tipos estão registrados no motor.
    tipos_motor = {t["codigo"] for t in client_admin.get("/api/v1/aprovacoes/tipos-de-decisao/").json()}
    assert tipos <= tipos_motor
    assert callable(aprovacoes.motivo_aplicado)


@pytest.mark.django_db(transaction=True)
def test_migracoes_financeiro_sao_reversiveis() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("financeiro", "0001_modelos_iniciais")])

    estado_0001 = executor.loader.project_state([("financeiro", "0001_modelos_iniciais")])
    categoria_model = estado_0001.apps.get_model("financeiro", "CategoriaFinanceira")
    assert categoria_model.objects.count() == 0

    call_command("migrate", "financeiro", "zero", verbosity=0)
    executor = MigrationExecutor(connection)
    aplicadas = set(executor.loader.applied_migrations)
    assert ("financeiro", "0001_modelos_iniciais") not in aplicadas
    assert ("financeiro", "0002_permissoes_e_dados_iniciais") not in aplicadas

    try:
        call_command("migrate", "financeiro", verbosity=0)
    finally:
        call_command("migrate", verbosity=0)

    assert CategoriaFinanceira.objects.filter(natureza="ENTRADA").count() == 5
