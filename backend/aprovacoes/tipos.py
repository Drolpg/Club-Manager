"""Registro dos tipos de decisão e dos tipos de solicitação, e as permissões que o motor declara.

Os tipos vivem no código, como o catálogo de permissões: cada módulo declara os seus ao iniciar. Os motivos de
decisão ficam no banco, um conjunto por tipo de decisão. Este módulo declara os três da solicitação; o
Financeiro declara os dele (RN-011). Um tipo de solicitação diz quem o decide, se tem valor, como o conteúdo
é validado (`preparar`) e quem é avisado das mudanças (`ao_mudar`); o motor não conhece quem o registra
(AD-008).
"""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from kernel.dinheiro import Dinheiro
from permissoes import public as permissoes

_FORMATO = re.compile(r"[a-z][a-z_]*(\.[a-z][a-z_]*)+")

APROVAR = "solicitacao.aprovar"
CONTESTAR = "solicitacao.contestar"
RECUSAR = "solicitacao.recusar"


@dataclass(frozen=True)
class TipoDeDecisao:
    codigo: str
    nome: str


_tipos_de_decisao: dict[str, TipoDeDecisao] = {}


def registrar_tipo_de_decisao(codigo: str, nome: str) -> None:
    """Declara um tipo de decisão. O código, no formato `<recurso>.<acao>`, nunca muda de significado."""
    if not _FORMATO.fullmatch(codigo):
        raise ValueError(
            f"Código de tipo de decisão inválido: {codigo!r}. Use <recurso>.<acao>, em minúsculas."
        )
    novo = TipoDeDecisao(codigo, nome)
    existente = _tipos_de_decisao.get(codigo)
    if existente is not None and existente != novo:
        raise ValueError(f"Tipo de decisão {codigo!r} já registrado com outra definição.")
    _tipos_de_decisao[codigo] = novo


def tipo_de_decisao_conhecido(codigo: str) -> bool:
    return codigo in _tipos_de_decisao


def listar_tipos_de_decisao() -> list[TipoDeDecisao]:
    return sorted(_tipos_de_decisao.values(), key=lambda t: t.codigo)


def remover_tipo_de_decisao_para_testes(codigo: str) -> None:
    """Só para os testes desfazerem um registro. O sistema nunca remove um tipo em execução."""
    _tipos_de_decisao.pop(codigo, None)


registrar_tipo_de_decisao(APROVAR, "Aprovar solicitação")
registrar_tipo_de_decisao(CONTESTAR, "Contestar solicitação")
registrar_tipo_de_decisao(RECUSAR, "Recusar solicitação")


# --- Permissões que o motor declara (spec funcional, P5) ---

AUTO_APROVAR = "solicitacoes.auto_aprovar"
REABRIR_DE_OUTROS = "solicitacoes.reabrir"
CANCELAR_DE_OUTROS = "solicitacoes.cancelar"


def registrar_permissoes() -> None:
    permissoes.registrar_permissao(
        AUTO_APROVAR,
        "Auto-aprovar solicitações",
        "Decidir a própria solicitação de um tipo que a pessoa pode aprovar. A decisão fica marcada como "
        "aprovação própria e o admin é avisado. Fica fora do acesso total.",
        fora_do_acesso_total=True,
    )
    permissoes.registrar_permissao(
        REABRIR_DE_OUTROS, "Reabrir solicitações", "Reabrir a solicitação recusada de outra pessoa."
    )
    permissoes.registrar_permissao(
        CANCELAR_DE_OUTROS, "Cancelar solicitações", "Cancelar a solicitação de outra pessoa."
    )


# --- Tipos de solicitação ---


@dataclass(frozen=True)
class ConteudoPreparado:
    """O que o `preparar` do módulo dono devolve: o conteúdo normalizado, o valor e um resumo de uma linha."""

    conteudo: dict[str, Any]
    valor: Dinheiro | None
    resumo: str


class Acontecimento(StrEnum):
    APROVADA = "APROVADA"
    CONTESTADA = "CONTESTADA"
    RECUSADA = "RECUSADA"
    EDITADA = "EDITADA"
    REABERTA = "REABERTA"
    RETIRADA = "RETIRADA"
    CANCELADA = "CANCELADA"


@dataclass(frozen=True)
class MudancaDeSolicitacao:
    """O aviso que o motor dá ao módulo dono do tipo, na mesma transação, a cada mudança de situação."""

    solicitacao_id: uuid.UUID
    tipo: str
    acontecimento: Acontecimento
    versao: int
    valor: Dinheiro | None
    ator_id: uuid.UUID | None
    teto_sugerido: Dinheiro | None = None


type Preparar = Callable[[dict[str, Any], uuid.UUID], ConteudoPreparado]
type AoMudar = Callable[[MudancaDeSolicitacao], None]


@dataclass(frozen=True)
class TipoDeSolicitacao:
    codigo: str
    nome: str
    permissao_de_aprovar: str
    tem_valor: bool
    preparar: Preparar
    ao_mudar: AoMudar
    permissao_de_enviar: str | None = None


_tipos_de_solicitacao: dict[str, TipoDeSolicitacao] = {}


def _exigir_no_catalogo(codigo: str | None) -> None:
    if codigo is not None and permissoes.nome_da_permissao(codigo) is None:
        raise ValueError(f"Permissão {codigo!r} não está no catálogo: registre-a antes do tipo.")


def registrar_tipo(
    *,
    codigo: str,
    nome: str,
    permissao_de_aprovar: str,
    tem_valor: bool,
    preparar: Preparar,
    ao_mudar: AoMudar,
    permissao_de_enviar: str | None = None,
) -> None:
    """Declara um tipo de solicitação, no formato `<modulo>.<tipo>`. Falha ao iniciar se algo está errado."""
    if not _FORMATO.fullmatch(codigo):
        raise ValueError(f"Código de tipo de solicitação inválido: {codigo!r}. Use <modulo>.<tipo>.")
    _exigir_no_catalogo(permissao_de_aprovar)
    _exigir_no_catalogo(permissao_de_enviar)
    novo = TipoDeSolicitacao(
        codigo, nome, permissao_de_aprovar, tem_valor, preparar, ao_mudar, permissao_de_enviar
    )
    existente = _tipos_de_solicitacao.get(codigo)
    if existente is not None and existente != novo:
        raise ValueError(f"Tipo de solicitação {codigo!r} já registrado com outra definição.")
    _tipos_de_solicitacao[codigo] = novo


def obter_tipo(codigo: str) -> TipoDeSolicitacao | None:
    return _tipos_de_solicitacao.get(codigo)


def listar_tipos() -> list[TipoDeSolicitacao]:
    return sorted(_tipos_de_solicitacao.values(), key=lambda t: t.codigo)


def remover_tipo_para_testes(codigo: str) -> None:
    """Só para os testes desfazerem um registro. O sistema nunca remove um tipo em execução."""
    _tipos_de_solicitacao.pop(codigo, None)
