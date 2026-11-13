"""Caixa de entrada: listar, resumir e ler as notificações do próprio usuário (RF-031, RF-032).

Toda consulta filtra por `destinatario_id` (NOT-R06). A notificação de outra pessoa é tratada como se não
existisse, inclusive para o admin (RN 2): o admin audita pelo histórico dos itens, não pela caixa alheia.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from kernel.errors import BusinessError
from notificacoes.models import Notificacao

LIMITE_PADRAO = 20
LIMITE_MAXIMO = 50


@dataclass(frozen=True)
class ItemDaCaixa:
    """O que a API mostra de uma notificação. Não expõe a chave, o item nem o estado do e-mail."""

    id: uuid.UUID
    tipo: str
    pede_acao: bool
    titulo: str
    texto: str
    caminho: str
    criada_em: datetime
    lida_em: datetime | None


@dataclass(frozen=True)
class PaginaDaCaixa:
    itens: tuple[ItemDaCaixa, ...]
    tem_mais: bool


@dataclass(frozen=True)
class Resumo:
    nao_lidas: int
    mais_recente_id: uuid.UUID | None


def _minhas(usuario_id: uuid.UUID) -> QuerySet[Notificacao]:
    return Notificacao.objects.filter(destinatario_id=usuario_id)


def _item(notificacao: Notificacao) -> ItemDaCaixa:
    return ItemDaCaixa(
        id=notificacao.id,
        tipo=notificacao.tipo,
        pede_acao=notificacao.pede_acao,
        titulo=notificacao.titulo,
        texto=notificacao.texto,
        caminho=notificacao.caminho,
        criada_em=notificacao.criada_em,
        lida_em=notificacao.lida_em,
    )


def _nao_encontrada() -> BusinessError:
    return BusinessError("NOT_FOUND", "Notificação não encontrada.", status=404)


def listar(
    usuario_id: uuid.UUID, *, antes: uuid.UUID | None = None, limite: int = LIMITE_PADRAO
) -> PaginaDaCaixa:
    """As notificações do usuário, da mais recente para a mais antiga, `limite` por vez (1 a 50).

    `antes` é o ID da última que o cliente já recebeu: devolve as que vêm depois dela na ordem da caixa.
    """
    consulta = _minhas(usuario_id)
    if antes is not None:
        referencia = _minhas(usuario_id).filter(pk=antes).first()
        if referencia is None:
            # Cursor de outra pessoa é tratado como cursor que não existe: não revela nada.
            raise BusinessError(
                "VALIDATION_ERROR",
                "Os dados enviados são inválidos.",
                status=400,
                details={"antes": ["Notificação não encontrada."]},
            )
        consulta = consulta.filter(
            Q(criada_em__lt=referencia.criada_em) | Q(criada_em=referencia.criada_em, id__lt=referencia.id)
        )
    # Uma a mais que o pedido, só para saber se ainda há outras depois desta página.
    achadas = list(consulta.order_by("-criada_em", "-id")[: limite + 1])
    return PaginaDaCaixa(itens=tuple(_item(n) for n in achadas[:limite]), tem_mais=len(achadas) > limite)


def resumo(usuario_id: uuid.UUID) -> Resumo:
    """A quantidade de não lidas e o ID da última que chegou (o site compara com a consulta anterior)."""
    nao_lidas = _minhas(usuario_id).filter(lida_em__isnull=True).count()
    mais_recente = _minhas(usuario_id).order_by("-criada_em", "-id").values_list("id", flat=True).first()
    return Resumo(nao_lidas=nao_lidas, mais_recente_id=mais_recente)


@transaction.atomic
def ler(usuario_id: uuid.UUID, notificacao_id: uuid.UUID) -> ItemDaCaixa:
    """Marca como lida. Ler de novo devolve a notificação sem mudar a data da primeira leitura (CA-12)."""
    notificacao = _minhas(usuario_id).select_for_update().filter(pk=notificacao_id).first()
    if notificacao is None:
        raise _nao_encontrada()
    if notificacao.lida_em is None:
        notificacao.marcar_lida(timezone.now())
        notificacao.save(update_fields=["lida_em"])
    return _item(notificacao)


@transaction.atomic
def ler_todas(usuario_id: uuid.UUID) -> int:
    """Marca como lidas todas as não lidas do usuário. As já lidas e as de outros ficam como estão."""
    return _minhas(usuario_id).filter(lida_em__isnull=True).update(lida_em=timezone.now())
