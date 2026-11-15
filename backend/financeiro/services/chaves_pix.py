"""Cadastro de chaves Pix do clube (admin mantém; apenas uma ativa pode ser padrão)."""

import uuid

from django.db import transaction

from auditoria import public as auditoria
from financeiro.erros import erro
from financeiro.models import ChavePix
from financeiro.services.autorizacao import exigir_admin, exigir_leitura_gestao

ITEM_AUDITORIA = "chave_pix"


def _auditar(ator_id: uuid.UUID, chave: ChavePix, acao: str) -> None:
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao,
        item_tipo=ITEM_AUDITORIA,
        item_id=chave.id,
        dados={"tipo": chave.tipo, "padrao": chave.padrao, "ativa": chave.ativa},
    )


def _buscar_bloqueada(chave_id: uuid.UUID) -> ChavePix:
    chave = ChavePix.objects.select_for_update().filter(pk=chave_id).first()
    if chave is None:
        raise erro("NOT_FOUND")
    return chave


def _desmarcar_padrao_atual(*, exceto_id: uuid.UUID | None = None) -> None:
    qs = ChavePix.objects.select_for_update().filter(padrao=True)
    if exceto_id is not None:
        qs = qs.exclude(pk=exceto_id)
    atual = qs.first()
    if atual is not None:
        atual.desmarcar_padrao()
        atual.save(update_fields=["padrao"])


def listar(ator_id: uuid.UUID, *, incluir_inativas: bool = False) -> list[ChavePix]:
    if incluir_inativas:
        exigir_admin(ator_id)
    else:
        exigir_leitura_gestao(ator_id)
    qs = ChavePix.objects.all()
    if not incluir_inativas:
        qs = qs.filter(ativa=True)
    return list(qs)


@transaction.atomic
def cadastrar(
    *,
    ator_id: uuid.UUID,
    tipo: str,
    chave: str,
    nome_recebedor: str,
    cidade: str,
    padrao: bool,
) -> ChavePix:
    exigir_admin(ator_id)
    if padrao:
        _desmarcar_padrao_atual()
    registro = ChavePix.criar(
        tipo=tipo,
        chave=chave,
        nome_recebedor=nome_recebedor,
        cidade=cidade,
        padrao=padrao,
    )
    registro.save()
    _auditar(ator_id, registro, "CHAVE_PIX_CADASTRADA")
    return registro


@transaction.atomic
def editar(
    *,
    ator_id: uuid.UUID,
    chave_id: uuid.UUID,
    tipo: str,
    chave: str,
    nome_recebedor: str,
    cidade: str,
) -> ChavePix:
    exigir_admin(ator_id)
    registro = _buscar_bloqueada(chave_id)
    registro.editar(tipo=tipo, chave=chave, nome_recebedor=nome_recebedor, cidade=cidade)
    registro.save()
    _auditar(ator_id, registro, "CHAVE_PIX_EDITADA")
    return registro


@transaction.atomic
def marcar_padrao(*, ator_id: uuid.UUID, chave_id: uuid.UUID) -> ChavePix:
    exigir_admin(ator_id)
    registro = _buscar_bloqueada(chave_id)
    if not registro.ativa:
        raise erro("CHAVE_PIX_INATIVA")
    _desmarcar_padrao_atual(exceto_id=registro.id)
    registro.marcar_como_padrao()
    registro.save(update_fields=["padrao"])
    _auditar(ator_id, registro, "CHAVE_PIX_DEFINIDA_PADRAO")
    return registro


@transaction.atomic
def desativar(*, ator_id: uuid.UUID, chave_id: uuid.UUID) -> ChavePix:
    exigir_admin(ator_id)
    registro = _buscar_bloqueada(chave_id)
    registro.desativar()
    registro.save(update_fields=["ativa", "padrao"])
    _auditar(ator_id, registro, "CHAVE_PIX_DESATIVADA")
    return registro


@transaction.atomic
def reativar(*, ator_id: uuid.UUID, chave_id: uuid.UUID) -> ChavePix:
    exigir_admin(ator_id)
    registro = _buscar_bloqueada(chave_id)
    registro.reativar()
    registro.save(update_fields=["ativa"])
    _auditar(ator_id, registro, "CHAVE_PIX_REATIVADA")
    return registro


def historico(*, ator_id: uuid.UUID, chave_id: uuid.UUID) -> list[auditoria.Registro]:
    exigir_admin(ator_id)
    if not ChavePix.objects.filter(pk=chave_id).exists():
        raise erro("NOT_FOUND")
    return auditoria.historico_do_item(ITEM_AUDITORIA, chave_id)
