"""Testes das migrações de `financeiro`, dados iniciais, constraints e reversibilidade."""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from rest_framework.test import APIClient

from aprovacoes import public as aprovacoes
from financeiro.models import (
    AlvoEstorno,
    CategoriaFinanceira,
    ChavePix,
    Complemento,
    Cotacao,
    Envio,
    Estorno,
    NaoPodeApagar,
    PrestacaoDeContas,
    Saida,
    SituacaoComplemento,
)
from financeiro.tipos import PERMISSOES
from permissoes import public as permissoes
from tests import apoio


@pytest.mark.django_db
def test_CA01_sistema_nasce_com_categorias_iniciais_e_sem_chave_pix() -> None:
    entradas = set(CategoriaFinanceira.objects.filter(natureza="ENTRADA").values_list("nome", flat=True))
    assert entradas == {"Ajuda", "Diversos", "Mensalidade", "Patrocínio", "Rifa"}

    saidas = set(CategoriaFinanceira.objects.filter(natureza="SAIDA").values_list("nome", flat=True))
    assert saidas == {
        "Arbitragem",
        "Taxas e inscrições",
        "Material esportivo",
        "Transporte",
        "Alimentação",
        "Eventos",
        "Diversos",
    }
    assert ChavePix.objects.count() == 0


@pytest.mark.django_db
def test_decisao8_e_P7_setor_financeiro_nasce_com_sete_permissoes_e_sem_estorno(
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
    # Só o catálogo do financeiro: outros módulos também concedem permissões aos setores iniciais (M8 em
    # diante), e o teste não deve quebrar a cada um.
    do_financeiro = {codigo for codigo, _, _ in PERMISSOES}
    assert set(concedidas) & do_financeiro == {
        "cobrancas.criar",
        "pagamentos.validar",
        "entradas.registrar",
        "entradas.validar",
        "gastos.aprovar",
        "saidas.enviar",
        "saidas.liquidar",
    }
    assert "financeiro.estornar" not in concedidas


@pytest.mark.django_db
def test_nasce_com_motivos_iniciais_dos_nove_tipos_de_decisao(client_admin: APIClient) -> None:
    tipos = {
        "financeiro.pagamento_validar",
        "financeiro.pagamento_rejeitar",
        "financeiro.cobranca_cancelar",
        "financeiro.questionamento_decidir",
        "financeiro.divida_decidir",
        "financeiro.entrada_validar",
        "financeiro.entrada_rejeitar",
        "financeiro.prestacao_devolver",
        "financeiro.estornar",
    }
    resp = client_admin.get("/api/v1/aprovacoes/motivos/")
    assert resp.status_code == 200
    por_tipo: dict[str, list[str]] = {t: [] for t in tipos}
    for item in resp.json():
        if item["tipo_de_decisao"] in por_tipo:
            por_tipo[item["tipo_de_decisao"]].append(item["id"])
    for codigo, ids in por_tipo.items():
        assert len(ids) >= 1, f"Tipo {codigo} sem motivos iniciais"
    tipos_motor = {t["codigo"] for t in client_admin.get("/api/v1/aprovacoes/tipos-de-decisao/").json()}
    assert tipos <= tipos_motor
    assert callable(aprovacoes.motivo_aplicado)


@pytest.mark.django_db
def test_constraints_e_imutabilidade_de_cotacao_saida_envio_complemento_e_estorno() -> None:
    cat = CategoriaFinanceira.objects.get(nome="Diversos", natureza="SAIDA")
    solicitacao_id = uuid.uuid7()
    solicitante_id = uuid.uuid7()
    setor_id = uuid.uuid7()

    cotacao = Cotacao.objects.create(
        enviada_por_id=solicitante_id,
        chave="cotacoes/teste.pdf",
        nome="orcamento.pdf",
        mime="application/pdf",
        tamanho=1200,
    )
    with pytest.raises(NaoPodeApagar):
        cotacao.save()
    with pytest.raises(NaoPodeApagar):
        cotacao.delete()

    saida = Saida.objects.create(
        solicitacao_id=solicitacao_id,
        versao_aprovada=1,
        solicitante_id=solicitante_id,
        categoria=cat,
        categoria_nome=cat.nome,
        setor_id=setor_id,
        setor_nome="Esportes",
        cotacao=cotacao,
        descricao="Compra de uniformes",
        valor_aprovado=Decimal("500.00"),
    )
    with pytest.raises(NaoPodeApagar):
        saida.delete()

    # Não permite duas saídas ativas para a mesma solicitação.
    with pytest.raises(IntegrityError), transaction.atomic():
        Saida.objects.create(
            solicitacao_id=solicitacao_id,
            versao_aprovada=2,
            solicitante_id=solicitante_id,
            categoria=cat,
            categoria_nome=cat.nome,
            setor_id=setor_id,
            setor_nome="Esportes",
            descricao="Duplicada",
            valor_aprovado=Decimal("500.00"),
        )

    envio = Envio.objects.create(
        saida=saida,
        valor=Decimal("500.00"),
        enviado_por_id=uuid.uuid7(),
        enviado_em=timezone.now(),
        comprovante_chave="envios/ted.pdf",
        comprovante_nome="ted.pdf",
        comprovante_mime="application/pdf",
        comprovante_tamanho=500,
    )
    with pytest.raises(NaoPodeApagar):
        envio.save()
    with pytest.raises(NaoPodeApagar):
        envio.delete()

    # Apenas um Complemento EM_ANDAMENTO por saída.
    Complemento.objects.create(
        saida=saida,
        solicitacao_id=uuid.uuid7(),
        valor=Decimal("100.00"),
        situacao=SituacaoComplemento.EM_ANDAMENTO,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Complemento.objects.create(
            saida=saida,
            solicitacao_id=uuid.uuid7(),
            valor=Decimal("50.00"),
            situacao=SituacaoComplemento.EM_ANDAMENTO,
        )

    # Apenas uma PrestacaoDeContas VIGENTE por saída.
    PrestacaoDeContas.objects.create(
        saida=saida,
        valor=Decimal("500.00"),
        descricao="Nota fiscal ok",
        registrada_por_id=solicitante_id,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        PrestacaoDeContas.objects.create(
            saida=saida,
            valor=Decimal("450.00"),
            descricao="Segunda vigente inválida",
            registrada_por_id=solicitante_id,
        )

    # CheckConstraint de alvo exclusivo em Estorno e imutabilidade.
    with pytest.raises(IntegrityError), transaction.atomic():
        Estorno.objects.create(
            alvo_tipo=AlvoEstorno.SAIDA,
            saida=None,
            valor=Decimal("500.00"),
            motivo_id=uuid.uuid7(),
            motivo_texto="Erro",
            justificativa="Inconsistente",
            registrado_por_id=uuid.uuid7(),
            registrado_em=datetime.now(tz=timezone.get_current_timezone()),
        )

    estorno = Estorno.objects.create(
        alvo_tipo=AlvoEstorno.SAIDA,
        saida=saida,
        valor=Decimal("500.00"),
        motivo_id=uuid.uuid7(),
        motivo_texto="Erro de lançamento",
        justificativa="Estorno de teste",
        registrado_por_id=uuid.uuid7(),
        registrado_em=timezone.now(),
    )
    with pytest.raises(NaoPodeApagar):
        estorno.save()
    with pytest.raises(NaoPodeApagar):
        estorno.delete()


@pytest.mark.django_db(transaction=True)
def test_migracoes_financeiro_sao_reversiveis() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("financeiro", "0002_permissoes_e_dados_iniciais")])
    estado_0002 = executor.loader.project_state([("financeiro", "0002_permissoes_e_dados_iniciais")])
    categoria_0002 = estado_0002.apps.get_model("financeiro", "CategoriaFinanceira")
    assert categoria_0002.objects.filter(natureza="SAIDA").count() == 0

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
    assert ("financeiro", "0003_saidas_cotacoes_estornos_e_permissoes") not in aplicadas

    try:
        call_command("migrate", "financeiro", verbosity=0)
    finally:
        call_command("migrate", verbosity=0)

    assert CategoriaFinanceira.objects.filter(natureza="ENTRADA").count() == 5
    assert CategoriaFinanceira.objects.filter(natureza="SAIDA").count() == 7
