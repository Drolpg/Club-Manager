"""API pública do módulo `acesso`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/architecture/project-structure.md).
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from acesso.models import Situacao, Usuario


@dataclass(frozen=True)
class UsuarioInfo:
    """O que os outros módulos podem saber de um usuário. Não é o modelo persistido."""

    id: uuid.UUID
    nome: str
    nome_de_usuario: str
    email: str
    admin: bool
    ativo: bool


def _info(usuario: Usuario) -> UsuarioInfo:
    return UsuarioInfo(
        id=usuario.id,
        nome=usuario.nome,
        nome_de_usuario=usuario.nome_de_usuario,
        email=usuario.email,
        admin=usuario.admin,
        ativo=usuario.is_active,
    )


def usuario_por_id(usuario_id: uuid.UUID) -> UsuarioInfo | None:
    usuario = Usuario.objects.filter(pk=usuario_id).first()
    return _info(usuario) if usuario else None


def admins_ativos() -> list[UsuarioInfo]:
    return [_info(u) for u in Usuario.objects.filter(admin=True, situacao=Situacao.ATIVO)]


def ids_ativos(usuario_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """Dos IDs recebidos, os que são de usuários ativos."""
    return set(
        Usuario.objects.filter(pk__in=list(usuario_ids), situacao=Situacao.ATIVO).values_list("id", flat=True)
    )
