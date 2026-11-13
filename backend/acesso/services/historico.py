"""Histórico de um item com o nome de quem agiu (RF-027)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from acesso.models import Convite, Usuario
from acesso.services.autorizacao import exigir_admin, exigir_gerenciar_convites
from auditoria import public as auditoria
from kernel.errors import BusinessError


@dataclass(frozen=True)
class Ator:
    id: uuid.UUID
    nome: str


@dataclass(frozen=True)
class RegistroDoHistorico:
    """Uma ação do histórico. Não leva `dados`: a auditoria guarda IDs, e o histórico mostra o que importa."""

    acao: str
    ator: Ator | None
    justificativa: str
    criado_em: datetime


def com_nomes(item_tipo: str, item_id: uuid.UUID) -> list[RegistroDoHistorico]:
    """Os registros do item, do mais recente para o mais antigo. Ação do sistema tem `ator` nulo."""
    registros = auditoria.historico_do_item(item_tipo, item_id)
    ator_ids = {r.ator_id for r in registros if r.ator_id is not None}
    nomes = dict(Usuario.objects.filter(pk__in=ator_ids).values_list("id", "nome"))
    return [
        RegistroDoHistorico(
            acao=r.acao,
            ator=Ator(r.ator_id, nomes.get(r.ator_id, "")) if r.ator_id is not None else None,
            justificativa=r.justificativa,
            criado_em=r.criado_em,
        )
        for r in reversed(registros)
    ]


def _nao_encontrado(item: str) -> BusinessError:
    return BusinessError("NOT_FOUND", f"{item} não encontrado.", status=404)


def do_usuario(*, ator: Usuario, usuario_id: uuid.UUID) -> list[RegistroDoHistorico]:
    exigir_admin(ator)
    if not Usuario.objects.filter(pk=usuario_id).exists():
        raise _nao_encontrado("Usuário")
    return com_nomes("usuario", usuario_id)


def do_convite(*, ator: Usuario, convite_id: uuid.UUID) -> list[RegistroDoHistorico]:
    exigir_gerenciar_convites(ator)
    if not Convite.objects.filter(pk=convite_id).exists():
        raise _nao_encontrado("Convite")
    return com_nomes("convite", convite_id)
