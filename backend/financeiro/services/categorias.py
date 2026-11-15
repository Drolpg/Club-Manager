"""Cadastro de categorias financeiras (admin mantém; quem lê gestão consulta)."""

import uuid

from django.db import IntegrityError, transaction

from auditoria import public as auditoria
from financeiro.erros import erro
from financeiro.models import CategoriaFinanceira
from financeiro.services.autorizacao import exigir_admin, exigir_leitura_gestao

ITEM_AUDITORIA = "categoria_financeira"


def _auditar(ator_id: uuid.UUID, categoria: CategoriaFinanceira, acao: str) -> None:
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao,
        item_tipo=ITEM_AUDITORIA,
        item_id=categoria.id,
        dados={"natureza": categoria.natureza, "ativa": categoria.ativa},
    )


def _buscar_bloqueada(categoria_id: uuid.UUID) -> CategoriaFinanceira:
    categoria = CategoriaFinanceira.objects.select_for_update().filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND")
    return categoria


def _salvar_unico(categoria: CategoriaFinanceira) -> None:
    existe = (
        CategoriaFinanceira.objects.filter(natureza=categoria.natureza, nome__iexact=categoria.nome)
        .exclude(pk=categoria.pk)
        .exists()
    )
    if existe:
        raise erro("CATEGORIA_JA_EXISTE")
    try:
        with transaction.atomic():
            categoria.save()
    except IntegrityError as exc:
        raise erro("CATEGORIA_JA_EXISTE") from exc


def listar(
    ator_id: uuid.UUID, *, natureza: str | None = None, incluir_inativas: bool = False
) -> list[CategoriaFinanceira]:
    if incluir_inativas:
        exigir_admin(ator_id)
    else:
        exigir_leitura_gestao(ator_id)
    qs = CategoriaFinanceira.objects.all()
    if natureza:
        qs = qs.filter(natureza=natureza)
    if not incluir_inativas:
        qs = qs.filter(ativa=True)
    return list(qs)


@transaction.atomic
def criar(*, ator_id: uuid.UUID, nome: str, natureza: str) -> CategoriaFinanceira:
    exigir_admin(ator_id)
    categoria = CategoriaFinanceira(nome=nome.strip(), natureza=natureza, ativa=True)
    _salvar_unico(categoria)
    _auditar(ator_id, categoria, "CATEGORIA_FINANCEIRA_CRIADA")
    return categoria


@transaction.atomic
def renomear(*, ator_id: uuid.UUID, categoria_id: uuid.UUID, nome: str) -> CategoriaFinanceira:
    exigir_admin(ator_id)
    categoria = _buscar_bloqueada(categoria_id)
    categoria.renomear(nome)
    _salvar_unico(categoria)
    _auditar(ator_id, categoria, "CATEGORIA_FINANCEIRA_RENOMEADA")
    return categoria


@transaction.atomic
def desativar(*, ator_id: uuid.UUID, categoria_id: uuid.UUID) -> CategoriaFinanceira:
    exigir_admin(ator_id)
    categoria = _buscar_bloqueada(categoria_id)
    categoria.desativar()
    categoria.save(update_fields=["ativa"])
    _auditar(ator_id, categoria, "CATEGORIA_FINANCEIRA_DESATIVADA")
    return categoria


@transaction.atomic
def reativar(*, ator_id: uuid.UUID, categoria_id: uuid.UUID) -> CategoriaFinanceira:
    exigir_admin(ator_id)
    categoria = _buscar_bloqueada(categoria_id)
    categoria.reativar()
    categoria.save(update_fields=["ativa"])
    _auditar(ator_id, categoria, "CATEGORIA_FINANCEIRA_REATIVADA")
    return categoria


def historico(*, ator_id: uuid.UUID, categoria_id: uuid.UUID) -> list[auditoria.Registro]:
    exigir_admin(ator_id)
    if not CategoriaFinanceira.objects.filter(pk=categoria_id).exists():
        raise erro("NOT_FOUND")
    return auditoria.historico_do_item(ITEM_AUDITORIA, categoria_id)
