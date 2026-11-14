"""Motivos de decisão: o admin cria, edita, desativa e reativa; quem lê gestão consulta (RF-033; RN-014).

Ordem das conferências: entrada (na rota) → quem pode → existência → regra. Quem não é admin recebe 403 antes
de saber se o motivo existe.
"""

import uuid

from django.db import IntegrityError, transaction

from aprovacoes import tipos
from aprovacoes.models import MotivoDeDecisao
from aprovacoes.services.autorizacao import exigir_admin, exigir_leitura_de_gestao
from auditoria import public as auditoria
from kernel.errors import BusinessError

ITEM_DA_AUDITORIA = "motivo_de_decisao"


def _invalido(campo: str, mensagem: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details={campo: [mensagem]}
    )


def _repetido() -> BusinessError:
    return BusinessError(
        "MOTIVO_JA_EXISTE",
        "Já existe um motivo com este texto neste tipo de decisão. Se ele está inativo, reative-o.",
        status=409,
    )


def _auditar(ator_id: uuid.UUID, motivo: MotivoDeDecisao, acao: str) -> None:
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao,
        item_tipo=ITEM_DA_AUDITORIA,
        item_id=motivo.id,
        dados={"tipo_de_decisao": motivo.tipo_de_decisao},
    )


def _buscar(motivo_id: uuid.UUID) -> MotivoDeDecisao:
    motivo = MotivoDeDecisao.objects.select_for_update().filter(pk=motivo_id).first()
    if motivo is None:
        raise BusinessError("NOT_FOUND", "Motivo não encontrado.", status=404)
    return motivo


def _salvar(motivo: MotivoDeDecisao) -> None:
    repetido = MotivoDeDecisao.objects.filter(
        tipo_de_decisao=motivo.tipo_de_decisao, texto__iexact=motivo.texto
    ).exclude(pk=motivo.pk)
    if repetido.exists():
        raise _repetido()
    try:
        # O savepoint mantém a transação utilizável se duas requisições gravarem o mesmo texto ao mesmo tempo.
        with transaction.atomic():
            motivo.save()
    except IntegrityError as erro:
        raise _repetido() from erro


def listar(
    ator_id: uuid.UUID, *, tipo_de_decisao: str | None = None, incluir_inativos: bool = False
) -> list[MotivoDeDecisao]:
    """Os motivos ativos, por tipo de decisão e texto. Só o admin pede também os inativos."""
    if incluir_inativos:
        exigir_admin(ator_id)
    else:
        exigir_leitura_de_gestao(ator_id)
    motivos = MotivoDeDecisao.objects.all()
    if tipo_de_decisao:
        motivos = motivos.filter(tipo_de_decisao=tipo_de_decisao)
    if not incluir_inativos:
        motivos = motivos.filter(ativo=True)
    return list(motivos)


@transaction.atomic
def criar(*, ator_id: uuid.UUID, tipo_de_decisao: str, texto: str) -> MotivoDeDecisao:
    exigir_admin(ator_id)
    if not tipos.tipo_de_decisao_conhecido(tipo_de_decisao):
        raise _invalido("tipo_de_decisao", "Tipo de decisão desconhecido.")
    motivo = MotivoDeDecisao(tipo_de_decisao=tipo_de_decisao, texto=texto.strip())
    _salvar(motivo)
    _auditar(ator_id, motivo, "MOTIVO_CRIADO")
    return motivo


@transaction.atomic
def editar(*, ator_id: uuid.UUID, motivo_id: uuid.UUID, texto: str) -> MotivoDeDecisao:
    """Muda o texto das opções. As decisões já tomadas guardam o texto que tinham (regra 20)."""
    exigir_admin(ator_id)
    motivo = _buscar(motivo_id)
    motivo.editar(texto.strip())
    _salvar(motivo)
    _auditar(ator_id, motivo, "MOTIVO_EDITADO")
    return motivo


@transaction.atomic
def desativar(*, ator_id: uuid.UUID, motivo_id: uuid.UUID) -> MotivoDeDecisao:
    exigir_admin(ator_id)
    motivo = _buscar(motivo_id)
    if not motivo.ativo:
        raise BusinessError("JA_ESTA_INATIVO", "Este motivo já está inativo.")
    motivo.desativar()
    motivo.save(update_fields=["ativo"])
    _auditar(ator_id, motivo, "MOTIVO_DESATIVADO")
    return motivo


@transaction.atomic
def reativar(*, ator_id: uuid.UUID, motivo_id: uuid.UUID) -> MotivoDeDecisao:
    exigir_admin(ator_id)
    motivo = _buscar(motivo_id)
    if motivo.ativo:
        raise BusinessError("JA_ESTA_ATIVO", "Este motivo já está ativo.")
    motivo.reativar()
    motivo.save(update_fields=["ativo"])
    _auditar(ator_id, motivo, "MOTIVO_REATIVADO")
    return motivo


def motivo_aplicado(motivo_id: uuid.UUID, tipo_de_decisao: str) -> str:
    """O texto a copiar na decisão. Recusa motivo inexistente, inativo ou de outro tipo de decisão."""
    motivo = MotivoDeDecisao.objects.filter(pk=motivo_id).first()
    if motivo is None or not motivo.ativo or motivo.tipo_de_decisao != tipo_de_decisao:
        raise _invalido("motivo_id", "Escolha um motivo ativo para este tipo de decisão.")
    return motivo.texto
