"""Registro dos tipos de decisão (e, a partir do checkpoint 3, dos tipos de solicitação).

Os tipos vivem no código, como o catálogo de permissões: cada módulo declara os seus ao iniciar. Os motivos de
decisão ficam no banco, um conjunto por tipo de decisão. Este módulo declara os três da solicitação; o
Financeiro declara os dele (RN-011).
"""

import re
from dataclasses import dataclass

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
