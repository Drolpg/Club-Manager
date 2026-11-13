"""Concessões de permissão a cargo, setor ou usuário (RF-019, RF-020, RF-022, RF-023; PER-R06)."""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from acesso import public as acesso
from auditoria import public as auditoria
from kernel.errors import BusinessError
from permissoes import catalogo
from permissoes.domain.resolucao import ACESSO_TOTAL
from permissoes.models import AlvoDaConcessao, Cargo, Concessao, Setor
from permissoes.services.autorizacao import exigir_admin

# O tipo do alvo é também o tipo do item no histórico da auditoria.
_ITEM_DA_AUDITORIA = {
    AlvoDaConcessao.CARGO: "cargo",
    AlvoDaConcessao.SETOR: "setor",
    AlvoDaConcessao.USUARIO: "usuario",
}


@dataclass(frozen=True)
class ConcessaoInfo:
    """Uma concessão com o nome do alvo, pronta para a API mostrar."""

    id: uuid.UUID
    permissao: str
    alvo_tipo: str
    alvo_id: uuid.UUID
    alvo_nome: str
    concedida_em: datetime
    revogada_em: datetime | None


def _invalido(campo: str, mensagem: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details={campo: [mensagem]}
    )


def _alvo_id(concessao: Concessao) -> uuid.UUID:
    alvo_id = {
        AlvoDaConcessao.CARGO: concessao.cargo_id,
        AlvoDaConcessao.SETOR: concessao.setor_id,
        AlvoDaConcessao.USUARIO: concessao.usuario_id,
    }[AlvoDaConcessao(concessao.alvo_tipo)]
    if alvo_id is None:
        raise RuntimeError(f"Concessão {concessao.id} sem alvo do tipo {concessao.alvo_tipo}.")
    return alvo_id


def _auditar(ator_id: uuid.UUID, acao: str, concessao: Concessao) -> None:
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao,
        item_tipo=_ITEM_DA_AUDITORIA[AlvoDaConcessao(concessao.alvo_tipo)],
        item_id=_alvo_id(concessao),
        dados={"permissao": concessao.permissao, "concessao_id": str(concessao.id)},
    )


def _validar_alvo(alvo_tipo: AlvoDaConcessao, alvo_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Confere que o alvo existe e devolve o campo do modelo que o referencia."""
    if alvo_tipo is AlvoDaConcessao.CARGO:
        existe, campo = Cargo.objects.filter(pk=alvo_id).exists(), "cargo_id"
    elif alvo_tipo is AlvoDaConcessao.SETOR:
        existe, campo = Setor.objects.filter(pk=alvo_id).exists(), "setor_id"
    else:
        existe, campo = acesso.usuario_por_id(alvo_id) is not None, "usuario_id"
    if not existe:
        raise _invalido("alvo_id", "Alvo não encontrado.")
    return {campo: alvo_id}


def _ativa(permissao: str, alvo_tipo: AlvoDaConcessao, alvo: dict[str, uuid.UUID]) -> Concessao | None:
    return Concessao.objects.filter(
        permissao=permissao, alvo_tipo=alvo_tipo, revogada_em__isnull=True, **alvo
    ).first()


@transaction.atomic
def conceder(
    ator_id: uuid.UUID, permissao: str, alvo_tipo: str, alvo_id: uuid.UUID
) -> tuple[Concessao, bool]:
    """Concede uma permissão do catálogo. Devolve a concessão e se ela foi criada agora.

    Se o alvo já tem a permissão, devolve a concessão existente, sem criar outra nem auditar (RF-022).
    """
    exigir_admin(ator_id)
    if not catalogo.conhecida(permissao):
        raise _invalido("permissao", "Permissão desconhecida.")
    try:
        tipo = AlvoDaConcessao(alvo_tipo)
    except ValueError:
        raise _invalido("alvo_tipo", "Tipo de alvo desconhecido.") from None
    if permissao == ACESSO_TOTAL and tipo is not AlvoDaConcessao.USUARIO:
        raise BusinessError(
            "ACESSO_TOTAL_SO_PARA_USUARIO", "O acesso total só pode ser concedido a uma pessoa."
        )
    alvo = _validar_alvo(tipo, alvo_id)

    existente = _ativa(permissao, tipo, alvo)
    if existente is not None:
        return existente, False
    try:
        # O savepoint mantém a transação utilizável se duas requisições concederem ao mesmo tempo.
        with transaction.atomic():
            concessao = Concessao.objects.create(
                permissao=permissao,
                alvo_tipo=tipo,
                concedida_por_id=ator_id,
                concedida_em=timezone.now(),
                **alvo,
            )
    except IntegrityError:
        existente = _ativa(permissao, tipo, alvo)
        if existente is None:
            raise
        return existente, False
    _auditar(ator_id, "PERMISSAO_CONCEDIDA", concessao)
    return concessao, True


@transaction.atomic
def revogar(ator_id: uuid.UUID, concessao_id: uuid.UUID) -> Concessao:
    exigir_admin(ator_id)
    concessao = Concessao.objects.select_for_update().filter(pk=concessao_id).first()
    if concessao is None:
        raise BusinessError("NOT_FOUND", "Concessão não encontrada.", status=404)
    if not concessao.ativa:
        raise BusinessError("CONCESSAO_JA_REVOGADA", "Esta concessão já foi revogada.")
    concessao.revogar(por=ator_id, agora=timezone.now())
    concessao.save(update_fields=["revogada_por_id", "revogada_em"])
    _auditar(ator_id, "PERMISSAO_REVOGADA", concessao)
    return concessao


def listar_ativas(ator_id: uuid.UUID) -> list[Concessao]:
    exigir_admin(ator_id)
    return list(Concessao.objects.filter(revogada_em__isnull=True).select_related("cargo", "setor"))


def descrever(concessoes: Iterable[Concessao]) -> list[ConcessaoInfo]:
    """Junta o nome do alvo a cada concessão. O nome do usuário vem de `acesso`, uma consulta por pessoa."""
    nomes_de_usuarios: dict[uuid.UUID, str] = {}

    def nome_do_alvo(concessao: Concessao) -> str:
        if concessao.cargo is not None:
            return concessao.cargo.nome
        if concessao.setor is not None:
            return concessao.setor.nome
        usuario_id = _alvo_id(concessao)
        if usuario_id not in nomes_de_usuarios:
            usuario = acesso.usuario_por_id(usuario_id)
            nomes_de_usuarios[usuario_id] = usuario.nome if usuario else ""
        return nomes_de_usuarios[usuario_id]

    return [
        ConcessaoInfo(
            id=c.id,
            permissao=c.permissao,
            alvo_tipo=c.alvo_tipo,
            alvo_id=_alvo_id(c),
            alvo_nome=nome_do_alvo(c),
            concedida_em=c.concedida_em,
            revogada_em=c.revogada_em,
        )
        for c in concessoes
    ]
