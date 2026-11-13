"""Cargos e setores do clube (RF-015, RF-016). As mesmas regras valem para os dois."""

import uuid

from django.db import IntegrityError, transaction

from acesso import public as acesso
from auditoria import public as auditoria
from kernel.errors import BusinessError
from permissoes.models import Cargo, Classificacao, Setor
from permissoes.services.autorizacao import exigir_admin

type Modelo = type[Cargo] | type[Setor]
type Item = Cargo | Setor


def _tipo(modelo: Modelo) -> str:
    return "cargo" if modelo is Cargo else "setor"


def _auditar(ator_id: uuid.UUID, item: Item, acao: str) -> None:
    tipo = _tipo(type(item))
    auditoria.registrar(ator_id=ator_id, acao=f"{tipo.upper()}_{acao}", item_tipo=tipo, item_id=item.id)


def _nome_em_uso() -> BusinessError:
    return BusinessError("NOME_EM_USO", "Já existe um item com este nome.", status=409)


def _buscar(modelo: Modelo, item_id: uuid.UUID) -> Item:
    item = modelo.objects.select_for_update().filter(pk=item_id).first()
    if item is None:
        raise BusinessError("NOT_FOUND", "Item não encontrado.", status=404)
    return item


def _salvar_nome(modelo: Modelo, item: Item) -> None:
    if modelo.objects.filter(nome__iexact=item.nome).exclude(pk=item.pk).exists():
        raise _nome_em_uso()
    try:
        with transaction.atomic():
            item.save()
    except IntegrityError as erro:
        raise _nome_em_uso() from erro


def listar(modelo: Modelo) -> list[Item]:
    return list(modelo.objects.all())


@transaction.atomic
def criar(modelo: Modelo, *, ator_id: uuid.UUID, nome: str) -> Item:
    exigir_admin(ator_id)
    item = modelo(nome=nome.strip())
    _salvar_nome(modelo, item)
    _auditar(ator_id, item, "CRIADO")
    return item


@transaction.atomic
def renomear(modelo: Modelo, *, ator_id: uuid.UUID, item_id: uuid.UUID, nome: str) -> Item:
    exigir_admin(ator_id)
    item = _buscar(modelo, item_id)
    item.renomear(nome.strip())
    _salvar_nome(modelo, item)
    _auditar(ator_id, item, "RENOMEADO")
    return item


def _usuarios_ativos_com(item: Item) -> int:
    filtro = {"cargo": item} if isinstance(item, Cargo) else {"setores": item}
    ids = list(Classificacao.objects.filter(**filtro).values_list("usuario_id", flat=True))
    return len(acesso.ids_ativos(ids))


@transaction.atomic
def desativar(modelo: Modelo, *, ator_id: uuid.UUID, item_id: uuid.UUID) -> Item:
    """Só desativa o que nenhum usuário ativo tem: o admin reclassifica as pessoas antes (PER-R07)."""
    exigir_admin(ator_id)
    item = _buscar(modelo, item_id)
    if not item.ativo:
        raise BusinessError("JA_ESTA_INATIVO", "Este item já está inativo.")
    em_uso = _usuarios_ativos_com(item)
    if em_uso:
        raise BusinessError(
            f"{_tipo(modelo).upper()}_EM_USO",
            f"{em_uso} usuário(s) ativo(s) têm este item. Reclassifique-os antes de desativar.",
            details={"usuarios": em_uso},
        )
    item.desativar()
    item.save(update_fields=["ativo"])
    _auditar(ator_id, item, "DESATIVADO")
    return item


@transaction.atomic
def reativar(modelo: Modelo, *, ator_id: uuid.UUID, item_id: uuid.UUID) -> Item:
    exigir_admin(ator_id)
    item = _buscar(modelo, item_id)
    if item.ativo:
        raise BusinessError("JA_ESTA_ATIVO", "Este item já está ativo.")
    item.reativar()
    item.save(update_fields=["ativo"])
    _auditar(ator_id, item, "REATIVADO")
    return item


def historico(modelo: Modelo, *, ator_id: uuid.UUID, item_id: uuid.UUID) -> list[acesso.RegistroDoHistorico]:
    """O histórico de um cargo ou setor, do mais recente para o mais antigo. Só o admin vê (P8)."""
    exigir_admin(ator_id)
    if not modelo.objects.filter(pk=item_id).exists():
        raise BusinessError("NOT_FOUND", "Item não encontrado.", status=404)
    return acesso.historico_com_nomes(_tipo(modelo), item_id)
