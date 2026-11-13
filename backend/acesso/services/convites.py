"""Convites de diretor (RF-001 a RF-003)."""

import hashlib
import secrets
import uuid

from django.db import transaction
from django.utils import timezone

from acesso.domain.convite import VALIDADE, SituacaoDoConvite
from acesso.models import Convite, Usuario
from acesso.services.autorizacao import exigir_gerenciar_convites
from auditoria import public as auditoria
from kernel.errors import BusinessError


def hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def convite_invalido() -> BusinessError:
    # Uma resposta só para usado, expirado, revogado e inexistente (RN-025).
    return BusinessError("CONVITE_INVALIDO", "Convite inválido ou expirado.", status=404)


def _novo(*, ator: Usuario, substitui: Convite | None = None) -> tuple[Convite, str]:
    token = secrets.token_urlsafe(32)
    agora = timezone.now()
    convite = Convite.objects.create(
        token_hash=hash_do_token(token),
        gerado_por=ator,
        gerado_em=agora,
        expira_em=agora + VALIDADE,
        substitui=substitui,
    )
    auditoria.registrar(
        ator_id=ator.id,
        acao="CONVITE_GERADO",
        item_tipo="convite",
        item_id=convite.id,
        dados={"substitui": str(substitui.id)} if substitui else None,
    )
    return convite, token


def _buscar_com_bloqueio(convite_id: uuid.UUID) -> Convite:
    convite = Convite.objects.select_for_update().filter(pk=convite_id).first()
    if convite is None:
        raise BusinessError("NOT_FOUND", "Convite não encontrado.", status=404)
    return convite


@transaction.atomic
def gerar(*, ator: Usuario) -> tuple[Convite, str]:
    """Devolve o convite e o token em claro, que não fica guardado em lugar nenhum."""
    exigir_gerenciar_convites(ator)
    return _novo(ator=ator)


@transaction.atomic
def regenerar(*, ator: Usuario, convite_id: uuid.UUID) -> tuple[Convite, str]:
    """Invalida o link de um convite ativo ou expirado e cria outro, com 24 horas."""
    exigir_gerenciar_convites(ator)
    convite = _buscar_com_bloqueio(convite_id)
    agora = timezone.now()
    if convite.situacao(agora) not in (SituacaoDoConvite.ATIVO, SituacaoDoConvite.EXPIRADO):
        raise BusinessError(
            "CONVITE_NAO_PODE_SER_REGENERADO", "Só convite ativo ou expirado pode ser regenerado."
        )
    convite.revogar(agora)
    convite.save(update_fields=["revogado_em"])
    auditoria.registrar(
        ator_id=ator.id,
        acao="CONVITE_REVOGADO",
        item_tipo="convite",
        item_id=convite.id,
        dados={"motivo": "regenerado"},
    )
    return _novo(ator=ator, substitui=convite)


@transaction.atomic
def revogar(*, ator: Usuario, convite_id: uuid.UUID) -> Convite:
    exigir_gerenciar_convites(ator)
    convite = _buscar_com_bloqueio(convite_id)
    agora = timezone.now()
    if convite.situacao(agora) != SituacaoDoConvite.ATIVO:
        raise BusinessError("CONVITE_NAO_ESTA_ATIVO", "Só convite ativo pode ser revogado.")
    convite.revogar(agora)
    convite.save(update_fields=["revogado_em"])
    auditoria.registrar(ator_id=ator.id, acao="CONVITE_REVOGADO", item_tipo="convite", item_id=convite.id)
    return convite


def listar(*, ator: Usuario) -> list[Convite]:
    exigir_gerenciar_convites(ator)
    return list(Convite.objects.select_related("gerado_por"))


def consultar(*, token: str) -> Convite:
    """Devolve o convite se o token é de um convite ativo; senão, `CONVITE_INVALIDO`."""
    convite = Convite.objects.filter(token_hash=hash_do_token(token)).first()
    if convite is None or convite.situacao(timezone.now()) != SituacaoDoConvite.ATIVO:
        raise convite_invalido()
    return convite
