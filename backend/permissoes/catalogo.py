"""Catálogo das permissões que o sistema conhece (AD-014).

O catálogo vive no código: cada módulo declara as suas permissões ao iniciar, com `registrar_permissao`.
O painel do admin concede e revoga o que está aqui, e não cria permissão nova, porque uma permissão sem
código que a confira não faz nada.
"""

import re
from dataclasses import dataclass

from permissoes.domain.resolucao import ACESSO_TOTAL

_FORMATO = re.compile(r"[a-z][a-z_]*(\.[a-z][a-z_]*)+")

CONVITES_GERENCIAR = "convites.gerenciar"


@dataclass(frozen=True)
class Permissao:
    codigo: str
    nome: str
    descricao: str
    # A auto-aprovação, por exemplo, é uma permissão à parte, que o acesso total não dá (RN-007).
    fora_do_acesso_total: bool = False


_registro: dict[str, Permissao] = {}


def registrar_permissao(
    codigo: str, nome: str, descricao: str, *, fora_do_acesso_total: bool = False
) -> None:
    """Declara uma permissão. O código, no formato `<recurso>.<acao>`, nunca muda de significado."""
    if not _FORMATO.fullmatch(codigo):
        raise ValueError(f"Código de permissão inválido: {codigo!r}. Use <recurso>.<acao>, em minúsculas.")
    nova = Permissao(codigo, nome, descricao, fora_do_acesso_total)
    existente = _registro.get(codigo)
    if existente is not None and existente != nova:
        raise ValueError(f"Permissão {codigo!r} já registrada com outra definição.")
    _registro[codigo] = nova


def listar() -> list[Permissao]:
    return sorted(_registro.values(), key=lambda p: p.codigo)


def conhecida(codigo: str) -> bool:
    return codigo in _registro


def mapa_para_resolucao() -> dict[str, bool]:
    return {p.codigo: p.fora_do_acesso_total for p in _registro.values()}


def remover_para_testes(codigo: str) -> None:
    """Só para os testes desfazerem um registro. O sistema nunca remove uma permissão em execução."""
    _registro.pop(codigo, None)


registrar_permissao(
    CONVITES_GERENCIAR,
    "Gerenciar convites",
    "Gerar, listar, regenerar e revogar convites de diretor.",
)
registrar_permissao(
    ACESSO_TOTAL,
    "Acesso total",
    "Todas as permissões do catálogo, as de hoje e as futuras, menos a auto-aprovação. Não dá a "
    "administração de usuários, cargos, setores e concessões, que é só do admin. Só pode ser concedido "
    "a uma pessoa.",
)
