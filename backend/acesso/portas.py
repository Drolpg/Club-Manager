"""Portas de consulta que `acesso` oferece ao módulo de cima (adendo 1 da ADR-003).

`acesso` precisa de duas respostas que só `permissoes` sabe dar, mas não pode importá-lo. Cada porta tem um
padrão seguro (negar), e `permissoes` registra a implementação ao iniciar (`registrar_portas`, no `ready`).
Sem o registro, `acesso` funciona sozinho: convites só do admin, e ninguém "com cargo".
"""

import uuid
from collections.abc import Callable, Collection
from dataclasses import dataclass

from acesso.models import Situacao, Usuario

type PodeGerenciarConvites = Callable[[uuid.UUID], bool]
type UsuariosComCargo = Callable[[Collection[uuid.UUID]], set[uuid.UUID]]


def _so_admin_ativo(usuario_id: uuid.UUID) -> bool:
    return Usuario.objects.filter(pk=usuario_id, admin=True, situacao=Situacao.ATIVO).exists()


def _ninguem_tem_cargo(usuario_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
    return set()


@dataclass
class _Portas:
    pode_gerenciar_convites: PodeGerenciarConvites = _so_admin_ativo
    usuarios_com_cargo: UsuariosComCargo = _ninguem_tem_cargo


_estado = _Portas()


def registrar(
    *,
    pode_gerenciar_convites: PodeGerenciarConvites | None = None,
    usuarios_com_cargo: UsuariosComCargo | None = None,
) -> None:
    """Troca a implementação das portas informadas; as outras ficam como estão."""
    if pode_gerenciar_convites is not None:
        _estado.pode_gerenciar_convites = pode_gerenciar_convites
    if usuarios_com_cargo is not None:
        _estado.usuarios_com_cargo = usuarios_com_cargo


def restaurar() -> None:
    """Volta aos padrões seguros. Existe para os testes."""
    _estado.pode_gerenciar_convites = _so_admin_ativo
    _estado.usuarios_com_cargo = _ninguem_tem_cargo


def pode_gerenciar_convites(usuario_id: uuid.UUID) -> bool:
    return _estado.pode_gerenciar_convites(usuario_id)


def usuarios_com_cargo(usuario_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
    """Dos IDs recebidos, os que têm cargo. Uma consulta só, para a lista inteira."""
    return _estado.usuarios_com_cargo(usuario_ids)
