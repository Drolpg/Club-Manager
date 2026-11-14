"""Persistência do aggregate: nada é apagado, versões e decisões não mudam (adendo 1 da technical-spec).

A imutabilidade vale no modelo e também no banco, por gatilho, como na auditoria: os testes por SQL direto
conferem o caminho que passa por fora do `save`.
"""

import uuid
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from aprovacoes.models import Decisao, Imutavel, MotivoDeDecisao, Solicitacao, Versao

pytestmark = pytest.mark.django_db


def _solicitacao() -> Solicitacao:
    return Solicitacao.objects.create(tipo="teste.pedido", solicitante_id=uuid.uuid7(), situacao="EM_ANALISE")


def _versao(solicitacao: Solicitacao, numero: int = 1) -> Versao:
    return Versao.objects.create(
        solicitacao=solicitacao,
        numero=numero,
        conteudo={"descricao": "Bolas"},
        valor=Decimal("10.00"),
        resumo="Bolas",
        autor_id=solicitacao.solicitante_id,
    )


def _motivo() -> MotivoDeDecisao:
    return MotivoDeDecisao.objects.create(tipo_de_decisao="solicitacao.aprovar", texto="Motivo de teste")


def _decisao(versao: Versao) -> Decisao:
    motivo = _motivo()
    return Decisao.objects.create(
        versao=versao, tipo="APROVAR", aprovador_id=uuid.uuid7(), motivo=motivo, motivo_texto=motivo.texto
    )


# --- no modelo ---


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("conteudo", {"descricao": "Outra coisa"}),
        ("valor", Decimal("20.00")),
        ("resumo", "Outro resumo"),
        ("justificativa", "Outra"),
        ("numero", 9),
    ],
)
def test_inv_sol_05_versao_nao_muda(campo: str, valor: object) -> None:
    versao = _versao(_solicitacao())
    setattr(versao, campo, valor)

    with pytest.raises(Imutavel):
        versao.save()


def test_versao_aceita_gravar_as_datas_de_lembrete() -> None:
    versao = _versao(_solicitacao())
    agora = timezone.now()
    versao.lembrete_em = agora
    versao.aviso_ao_admin_em = agora

    versao.save(update_fields=["lembrete_em", "aviso_ao_admin_em"])

    versao.refresh_from_db()
    assert versao.lembrete_em == agora
    assert versao.aviso_ao_admin_em == agora


def test_decisao_nao_muda() -> None:
    decisao = _decisao(_versao(_solicitacao()))
    decisao.texto = "Mudou"

    with pytest.raises(Imutavel):
        decisao.save()


@pytest.mark.parametrize("fabrica", ["solicitacao", "versao", "decisao", "motivo"])
def test_nada_e_apagado(fabrica: str) -> None:
    solicitacao = _solicitacao()
    itens = {
        "solicitacao": lambda: solicitacao,
        "versao": lambda: _versao(solicitacao),
        "decisao": lambda: _decisao(_versao(solicitacao)),
        "motivo": _motivo,
    }
    item = itens[fabrica]()

    with pytest.raises(Imutavel):
        item.delete()


# --- no banco ---


def _sql(comando: str) -> None:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(comando)


@pytest.mark.parametrize(
    "comando",
    [
        "UPDATE aprovacoes_versao SET resumo = 'outro'",
        "UPDATE aprovacoes_versao SET conteudo = '{}'::jsonb",
        "UPDATE aprovacoes_versao SET valor = 1",
        "DELETE FROM aprovacoes_versao",
    ],
)
def test_banco_recusa_alterar_e_apagar_versao(comando: str) -> None:
    versao = _versao(_solicitacao())

    with pytest.raises(DatabaseError):
        _sql(comando)

    versao.refresh_from_db()
    assert versao.resumo == "Bolas"


def test_banco_aceita_gravar_as_datas_de_lembrete() -> None:
    versao = _versao(_solicitacao())

    _sql("UPDATE aprovacoes_versao SET lembrete_em = now(), aviso_ao_admin_em = now()")

    versao.refresh_from_db()
    assert versao.lembrete_em is not None
    assert versao.aviso_ao_admin_em is not None


@pytest.mark.parametrize(
    "comando", ["UPDATE aprovacoes_decisao SET texto = 'outro'", "DELETE FROM aprovacoes_decisao"]
)
def test_banco_recusa_alterar_e_apagar_decisao(comando: str) -> None:
    _decisao(_versao(_solicitacao()))

    with pytest.raises(DatabaseError):
        _sql(comando)

    assert Decisao.objects.get().texto == ""


def test_inv_sol_14_uma_decisao_por_versao_no_banco() -> None:
    versao = _versao(_solicitacao())
    _decisao(versao)

    with pytest.raises(IntegrityError), transaction.atomic():
        _decisao(versao)


def test_numero_da_versao_e_unico_na_solicitacao() -> None:
    solicitacao = _solicitacao()
    _versao(solicitacao)

    with pytest.raises(IntegrityError), transaction.atomic():
        _versao(solicitacao)


@pytest.mark.django_db(transaction=True)
def test_migracoes_revertem_e_reaplicam_com_os_motivos_iniciais() -> None:
    call_command("migrate", "aprovacoes", "zero", verbosity=0)
    assert "aprovacoes_solicitacao" not in connection.introspection.table_names()

    call_command("migrate", "aprovacoes", verbosity=0)
    assert MotivoDeDecisao.objects.count() == 10
    _decisao(_versao(_solicitacao()))
    with pytest.raises(DatabaseError):
        _sql("DELETE FROM aprovacoes_decisao")
