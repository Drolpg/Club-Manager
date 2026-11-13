"""Que permissões um usuário tem, e de onde vem cada uma (PER-R01 a PER-R05).

Função pura: recebe os fatos já lidos do banco e devolve a resposta. As permissões de um usuário são a união
das concedidas ao cargo dele, aos setores dele e a ele mesmo (RF-021).
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

# Concessão especial, só para usuário: dá todas as permissões do catálogo, menos as marcadas como fora dela.
ACESSO_TOTAL = "acesso.total"


class TipoDeOrigem(StrEnum):
    ADMIN = "ADMIN"
    CARGO = "CARGO"
    SETOR = "SETOR"
    INDIVIDUAL = "INDIVIDUAL"
    ACESSO_TOTAL = "ACESSO_TOTAL"


@dataclass(frozen=True)
class Origem:
    tipo: TipoDeOrigem
    id: uuid.UUID | None = None
    nome: str | None = None


@dataclass(frozen=True)
class Grupo:
    """Um cargo ou um setor do usuário, com as permissões concedidas a ele."""

    id: uuid.UUID
    nome: str
    ativo: bool
    permissoes: frozenset[str]


@dataclass(frozen=True)
class Fatos:
    ativo: bool
    admin: bool
    # Código da permissão → se ela fica fora do acesso total.
    catalogo: Mapping[str, bool]
    cargo: Grupo | None
    setores: Sequence[Grupo]
    individuais: frozenset[str]


def resolver_permissoes(fatos: Fatos) -> dict[str, list[Origem]]:
    """Devolve cada permissão do usuário com todas as origens dela.

    A ordem das origens é: admin, cargo, setores, individual, acesso total.
    """
    if not fatos.ativo:
        return {}

    # Só existe permissão que está no catálogo; o acesso total é uma concessão, não uma permissão.
    concediveis = [codigo for codigo in fatos.catalogo if codigo != ACESSO_TOTAL]
    resultado: dict[str, list[Origem]] = {}

    def acrescentar(codigo: str, origem: Origem) -> None:
        if codigo in concediveis:
            resultado.setdefault(codigo, []).append(origem)

    if fatos.admin:
        for codigo in concediveis:
            acrescentar(codigo, Origem(TipoDeOrigem.ADMIN))

    grupos = [(TipoDeOrigem.CARGO, fatos.cargo)] if fatos.cargo else []
    grupos += [(TipoDeOrigem.SETOR, setor) for setor in fatos.setores]
    for tipo, grupo in grupos:
        if grupo.ativo:
            for codigo in sorted(grupo.permissoes):
                acrescentar(codigo, Origem(tipo, grupo.id, grupo.nome))

    for codigo in sorted(fatos.individuais):
        acrescentar(codigo, Origem(TipoDeOrigem.INDIVIDUAL))

    if ACESSO_TOTAL in fatos.individuais and ACESSO_TOTAL in fatos.catalogo:
        for codigo in concediveis:
            if not fatos.catalogo[codigo]:
                acrescentar(codigo, Origem(TipoDeOrigem.ACESSO_TOTAL))

    return resultado
