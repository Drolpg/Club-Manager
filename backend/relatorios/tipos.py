"""O catálogo de tipos de relatório (P22, CA-27).

Um relatório novo é um tipo registrado aqui: código, nome, formatos, quem pode gerar, como validar os
parâmetros e como montar o conteúdo. O pedido, a geração, o download, a expiração e os escritores só conhecem
o `TipoDeRelatorio`.
"""

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from relatorios.domain.documento import Documento
from relatorios.domain.pedido import Formato


@dataclass(frozen=True)
class Contexto:
    """O que a montagem recebe além dos parâmetros: o instante da geração e quem pediu."""

    hoje: date
    agora: datetime
    usuario_id: uuid.UUID


@dataclass(frozen=True)
class TipoDeRelatorio:
    codigo: str
    nome: str
    formatos: tuple[Formato, ...]
    pode_gerar: Callable[[uuid.UUID], bool]
    # Devolve os parâmetros normalizados, ou levanta `ParametroInvalido`.
    validar_parametros: Callable[[Mapping[str, Any], date], dict[str, Any]]
    # Um documento; três em "Meus dados", que sai em ZIP.
    montar: Callable[[dict[str, Any], Contexto], list[Documento]]


_CATALOGO: dict[str, TipoDeRelatorio] = {}


def registrar_tipo_de_relatorio(tipo: TipoDeRelatorio) -> None:
    _CATALOGO[tipo.codigo] = tipo


def remover_tipo_de_relatorio(codigo: str) -> None:
    """Desfaz o registro de um tipo de teste."""
    _CATALOGO.pop(codigo, None)


def obter(codigo: str) -> TipoDeRelatorio | None:
    return _CATALOGO.get(codigo)


def disponiveis_para(usuario_id: uuid.UUID) -> list[TipoDeRelatorio]:
    """Os tipos que o usuário pode gerar, na ordem do registro."""
    return [tipo for tipo in _CATALOGO.values() if tipo.pode_gerar(usuario_id)]
