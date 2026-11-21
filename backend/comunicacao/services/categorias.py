"""Categorias de documento: só o admin mantém; usada, é desativada, nunca apagada (RF-141; RN-018; CA-28)."""

import uuid

from django.db import IntegrityError, transaction

from acesso import public as acesso
from auditoria import public as auditoria
from comunicacao.erros import erro, invalido
from comunicacao.models import LIMITE_DO_NOME_DA_CATEGORIA, CategoriaDeDocumento
from comunicacao.services.autorizacao import exigir_leitura_de_gestao

ITEM = "categoria_de_documento"


def _e_admin(usuario_id: uuid.UUID) -> bool:
    usuario = acesso.usuario_por_id(usuario_id)
    return usuario is not None and usuario.ativo and usuario.admin


def _exigir_admin(ator_id: uuid.UUID) -> None:
    if not _e_admin(ator_id):
        raise erro("PERMISSION_DENIED", "Só o admin mantém as categorias de documento.")


def _nome(nome: str) -> str:
    limpo = nome.strip()
    if not limpo:
        raise invalido({"nome": ["Informe o nome da categoria."]})
    if len(limpo) > LIMITE_DO_NOME_DA_CATEGORIA:
        raise invalido({"nome": [f"Use no máximo {LIMITE_DO_NOME_DA_CATEGORIA} caracteres."]})
    return limpo


def _sem_repeticao(nome: str, exceto: uuid.UUID | None = None) -> None:
    mesmas = CategoriaDeDocumento.objects.filter(nome__iexact=nome)
    if exceto is not None:
        mesmas = mesmas.exclude(pk=exceto)
    if mesmas.exists():
        raise erro("CATEGORIA_JA_EXISTE")


def _buscar(categoria_id: uuid.UUID) -> CategoriaDeDocumento:
    categoria = CategoriaDeDocumento.objects.select_for_update().filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND", "Categoria de documento não encontrada.")
    return categoria


def _auditar(ator_id: uuid.UUID, categoria: CategoriaDeDocumento, acao: str) -> None:
    auditoria.registrar(
        ator_id=ator_id, acao=acao, item_tipo=ITEM, item_id=categoria.id, dados={"nome": categoria.nome}
    )


def listar(ator_id: uuid.UUID, *, todas: bool = False) -> list[CategoriaDeDocumento]:
    """As ativas; o admin vê também as inativas com `todas`."""
    exigir_leitura_de_gestao(ator_id)
    consulta = CategoriaDeDocumento.objects.all()
    if not (todas and _e_admin(ator_id)):
        consulta = consulta.filter(ativa=True)
    return list(consulta)


@transaction.atomic
def criar(ator_id: uuid.UUID, nome: str) -> CategoriaDeDocumento:
    _exigir_admin(ator_id)
    limpo = _nome(nome)
    _sem_repeticao(limpo)
    try:
        with transaction.atomic():
            categoria = CategoriaDeDocumento.objects.create(nome=limpo)
    except IntegrityError:
        raise erro("CATEGORIA_JA_EXISTE") from None
    _auditar(ator_id, categoria, "CATEGORIA_DE_DOCUMENTO_CRIADA")
    return categoria


@transaction.atomic
def editar(ator_id: uuid.UUID, categoria_id: uuid.UUID, nome: str) -> CategoriaDeDocumento:
    _exigir_admin(ator_id)
    limpo = _nome(nome)
    categoria = _buscar(categoria_id)
    _sem_repeticao(limpo, exceto=categoria.id)
    categoria.nome = limpo
    categoria.save()
    _auditar(ator_id, categoria, "CATEGORIA_DE_DOCUMENTO_EDITADA")
    return categoria


def _ativar(ator_id: uuid.UUID, categoria_id: uuid.UUID, *, ativa: bool, acao: str) -> CategoriaDeDocumento:
    _exigir_admin(ator_id)
    categoria = _buscar(categoria_id)
    categoria.ativa = ativa
    categoria.save()
    _auditar(ator_id, categoria, acao)
    return categoria


@transaction.atomic
def desativar(ator_id: uuid.UUID, categoria_id: uuid.UUID) -> CategoriaDeDocumento:
    return _ativar(ator_id, categoria_id, ativa=False, acao="CATEGORIA_DE_DOCUMENTO_DESATIVADA")


@transaction.atomic
def reativar(ator_id: uuid.UUID, categoria_id: uuid.UUID) -> CategoriaDeDocumento:
    return _ativar(ator_id, categoria_id, ativa=True, acao="CATEGORIA_DE_DOCUMENTO_REATIVADA")
