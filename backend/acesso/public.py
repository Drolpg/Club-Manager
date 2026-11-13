"""API pública do módulo `acesso`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/architecture/project-structure.md).
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from acesso import portas
from acesso.models import Situacao, Usuario
from acesso.services.historico import Ator, RegistroDoHistorico, com_nomes


@dataclass(frozen=True)
class UsuarioInfo:
    """O que os outros módulos podem saber de um usuário. Não é o modelo persistido."""

    id: uuid.UUID
    nome: str
    nome_de_usuario: str
    email: str
    admin: bool
    ativo: bool


@dataclass(frozen=True)
class CadastroConcluido:
    """Evento de integração: um diretor concluiu o cadastro (conta ativa, sem cargo)."""

    usuario_id: uuid.UUID


@dataclass(frozen=True)
class PapelDeAdminAlterado:
    """Evento de integração: o usuário ganhou (`admin=True`) ou perdeu (`admin=False`) o papel de admin."""

    usuario_id: uuid.UUID
    admin: bool


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


def historico_com_nomes(item_tipo: str, item_id: uuid.UUID) -> list[RegistroDoHistorico]:
    """O histórico de um item, do mais recente para o mais antigo, com o nome de quem agiu."""
    return com_nomes(item_tipo, item_id)


# Portas de consulta que `permissoes` preenche ao iniciar (adendo 1 da ADR-003).
registrar_portas = portas.registrar
restaurar_portas = portas.restaurar
pode_gerenciar_convites = portas.pode_gerenciar_convites
usuarios_com_cargo = portas.usuarios_com_cargo

__all__ = (
    "Ator",
    "CadastroConcluido",
    "PapelDeAdminAlterado",
    "RegistroDoHistorico",
    "UsuarioInfo",
    "admins_ativos",
    "historico_com_nomes",
    "ids_ativos",
    "pode_gerenciar_convites",
    "registrar_portas",
    "restaurar_portas",
    "usuario_por_id",
    "usuarios_com_cargo",
)
