"""Classificação de diretores: cargo e setores (RF-017, RF-018; PER-R08)."""

import uuid
from collections.abc import Iterable

from django.db import transaction

from acesso import public as acesso
from auditoria import public as auditoria
from kernel.errors import BusinessError
from permissoes.models import Cargo, Classificacao, Setor
from permissoes.services.autorizacao import exigir_admin


def _invalido(campo: str, mensagem: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details={campo: [mensagem]}
    )


def _exigir_usuario_ativo(usuario_id: uuid.UUID) -> None:
    usuario = acesso.usuario_por_id(usuario_id)
    if usuario is None:
        raise BusinessError("NOT_FOUND", "Usuário não encontrado.", status=404)
    if not usuario.ativo:
        raise BusinessError("USUARIO_NAO_ESTA_ATIVO", "Só usuário ativo pode ser classificado.")


def _cargo_ativo(cargo_id: uuid.UUID) -> Cargo:
    cargo = Cargo.objects.filter(pk=cargo_id).first()
    if cargo is None:
        raise _invalido("cargo_id", "Cargo não encontrado.")
    if not cargo.ativo:
        raise BusinessError("CARGO_INATIVO", "Este cargo está inativo.")
    return cargo


def _setores_ativos(setor_ids: Iterable[uuid.UUID]) -> list[Setor]:
    ids = set(setor_ids)
    setores = list(Setor.objects.filter(pk__in=ids))
    if len(setores) != len(ids):
        raise _invalido("setor_ids", "Setor não encontrado.")
    if any(not setor.ativo for setor in setores):
        raise BusinessError("SETOR_INATIVO", "Há um setor inativo na lista.")
    return setores


@transaction.atomic
def classificar(
    ator_id: uuid.UUID, usuario_id: uuid.UUID, cargo_id: uuid.UUID | None, setor_ids: Iterable[uuid.UUID]
) -> Classificacao | None:
    """Dá cargo e setores a um diretor ativo, troca os que ele tem, ou tira o cargo (`cargo_id` nulo).

    Sem cargo não há setores (RF-024): tirar o cargo remove a classificação inteira, e o histórico fica na
    auditoria.
    """
    exigir_admin(ator_id)
    _exigir_usuario_ativo(usuario_id)
    setor_ids = list(setor_ids)

    if cargo_id is None:
        if setor_ids:
            raise _invalido("setor_ids", "Informe o cargo antes de informar setores.")
        atual = Classificacao.objects.filter(usuario_id=usuario_id).first()
        if atual is not None:
            # O que a pessoa tinha fica na auditoria, já que a classificação some.
            tinha = {
                "cargo_id": str(atual.cargo_id),
                "setor_ids": sorted(str(s) for s in atual.setores.values_list("id", flat=True)),
            }
            atual.delete()
            auditoria.registrar(
                ator_id=ator_id,
                acao="CLASSIFICACAO_REMOVIDA",
                item_tipo="usuario",
                item_id=usuario_id,
                dados=tinha,
            )
        return None

    cargo = _cargo_ativo(cargo_id)
    setores = _setores_ativos(setor_ids)
    classificacao, _ = Classificacao.objects.update_or_create(
        usuario_id=usuario_id, defaults={"cargo": cargo}
    )
    classificacao.setores.set(setores)
    auditoria.registrar(
        ator_id=ator_id,
        acao="USUARIO_CLASSIFICADO",
        item_tipo="usuario",
        item_id=usuario_id,
        dados={"cargo_id": str(cargo.id), "setor_ids": sorted(str(s.id) for s in setores)},
    )
    return classificacao
