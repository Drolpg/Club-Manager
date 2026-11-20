"""Categorias de evento: só o admin mantém; usada, é desativada, nunca apagada (RN-018; CA-01)."""

import uuid

from django.db import IntegrityError, transaction

from acesso import public as acesso
from auditoria import public as auditoria
from eventos.erros import erro, invalido
from eventos.models import LIMITE_DO_NOME_DA_CATEGORIA, CategoriaDeEvento
from eventos.services.autorizacao import exigir_leitura_de_gestao


def _e_admin(usuario_id: uuid.UUID) -> bool:
    usuario = acesso.usuario_por_id(usuario_id)
    return usuario is not None and usuario.ativo and usuario.admin


def _exigir_admin(ator_id: uuid.UUID) -> None:
    if not _e_admin(ator_id):
        raise erro("PERMISSION_DENIED", "Só o admin mantém as categorias de evento.")


def _nome(nome: str) -> str:
    limpo = nome.strip()
    if not limpo:
        raise invalido({"nome": ["Informe o nome da categoria."]})
    if len(limpo) > LIMITE_DO_NOME_DA_CATEGORIA:
        raise invalido({"nome": [f"Use no máximo {LIMITE_DO_NOME_DA_CATEGORIA} caracteres."]})
    return limpo


def _sem_repeticao(nome: str, exceto: uuid.UUID | None = None) -> None:
    mesmas = CategoriaDeEvento.objects.filter(nome__iexact=nome)
    if exceto is not None:
        mesmas = mesmas.exclude(pk=exceto)
    if mesmas.exists():
        raise erro("CATEGORIA_JA_EXISTE")


def _buscar(categoria_id: uuid.UUID) -> CategoriaDeEvento:
    categoria = CategoriaDeEvento.objects.select_for_update().filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND", "Categoria de evento não encontrada.")
    return categoria


def _auditar(ator_id: uuid.UUID, categoria: CategoriaDeEvento, acao: str) -> None:
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao,
        item_tipo="categoria_de_evento",
        item_id=categoria.id,
        dados={"nome": categoria.nome},
    )


def listar(ator_id: uuid.UUID, *, todas: bool = False) -> list[CategoriaDeEvento]:
    """As ativas; o admin vê também as inativas com `todas`."""
    exigir_leitura_de_gestao(ator_id)
    consulta = CategoriaDeEvento.objects.all()
    if not (todas and _e_admin(ator_id)):
        consulta = consulta.filter(ativa=True)
    return list(consulta)


@transaction.atomic
def criar(ator_id: uuid.UUID, nome: str) -> CategoriaDeEvento:
    _exigir_admin(ator_id)
    limpo = _nome(nome)
    _sem_repeticao(limpo)
    try:
        with transaction.atomic():
            categoria = CategoriaDeEvento.criar(limpo)
    except IntegrityError:
        raise erro("CATEGORIA_JA_EXISTE") from None
    _auditar(ator_id, categoria, "CATEGORIA_DE_EVENTO_CRIADA")
    return categoria


@transaction.atomic
def editar(ator_id: uuid.UUID, categoria_id: uuid.UUID, nome: str) -> CategoriaDeEvento:
    _exigir_admin(ator_id)
    limpo = _nome(nome)
    categoria = _buscar(categoria_id)
    _sem_repeticao(limpo, exceto=categoria.id)
    categoria.editar(limpo)
    _auditar(ator_id, categoria, "CATEGORIA_DE_EVENTO_EDITADA")
    return categoria


@transaction.atomic
def desativar(ator_id: uuid.UUID, categoria_id: uuid.UUID) -> CategoriaDeEvento:
    _exigir_admin(ator_id)
    categoria = _buscar(categoria_id)
    categoria.desativar()
    _auditar(ator_id, categoria, "CATEGORIA_DE_EVENTO_DESATIVADA")
    return categoria


@transaction.atomic
def reativar(ator_id: uuid.UUID, categoria_id: uuid.UUID) -> CategoriaDeEvento:
    _exigir_admin(ator_id)
    categoria = _buscar(categoria_id)
    categoria.reativar()
    _auditar(ator_id, categoria, "CATEGORIA_DE_EVENTO_REATIVADA")
    return categoria
