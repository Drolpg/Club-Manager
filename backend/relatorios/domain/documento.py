"""O documento tabular de um relatório (P22): dados puros, sem framework nem biblioteca de PDF.

Cada tipo de relatório monta um `Documento`; os escritores de PDF e de CSV o recebem e não conhecem o
relatório. O `Cabecalho` traz o que todo arquivo mostra; no M11, a marca preenche o nome, o escudo e a cor
(P24).
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class TipoDeColuna(StrEnum):
    TEXTO = "TEXTO"
    DINHEIRO = "DINHEIRO"
    DATA = "DATA"
    INTEIRO = "INTEIRO"
    SIM_NAO = "SIM_NAO"


Valor = str | Decimal | date | int | bool | None


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: TipoDeColuna


@dataclass(frozen=True)
class ItemDoResumo:
    rotulo: str
    valor: Valor
    tipo: TipoDeColuna


@dataclass(frozen=True)
class Tabela:
    titulo: str
    colunas: tuple[Coluna, ...]
    linhas: tuple[tuple[Valor, ...], ...]


@dataclass(frozen=True)
class Documento:
    titulo: str
    parametros: str
    resumo: tuple[ItemDoResumo, ...]
    tabelas: tuple[Tabela, ...]


@dataclass(frozen=True)
class Cabecalho:
    """O que todo arquivo traz no topo. Sem identidade de clube fixa no código (RNF-12)."""

    gerado_em: datetime
    gerado_por: str
    nome: str = "Club Manager"
    escudo: bytes | None = None
    cor: str | None = None
