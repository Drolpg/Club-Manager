"""Tipos de notificação que o sistema conhece.

O tipo vive no código: o módulo que gera a notificação declara o seu com `registrar_tipo`, ao iniciar, e diz
se ela pede ação do destinatário ou só informa (RN 4). Mesmo padrão do catálogo de permissões.
"""

import re
from dataclasses import dataclass

_FORMATO = re.compile(r"[a-z][a-z_]*(\.[a-z][a-z_]*)+")


@dataclass(frozen=True)
class TipoDeNotificacao:
    codigo: str
    pede_acao: bool
    descricao: str


_registro: dict[str, TipoDeNotificacao] = {}


def registrar_tipo(codigo: str, *, pede_acao: bool, descricao: str) -> None:
    """Declara um tipo. O código, no formato `<modulo>.<fato>`, nunca muda de significado."""
    if not _FORMATO.fullmatch(codigo):
        raise ValueError(f"Código de tipo inválido: {codigo!r}. Use <modulo>.<fato>, em minúsculas.")
    novo = TipoDeNotificacao(codigo, pede_acao, descricao)
    existente = _registro.get(codigo)
    if existente is not None and existente != novo:
        raise ValueError(f"Tipo {codigo!r} já registrado com outra definição.")
    _registro[codigo] = novo


def conhecido(codigo: str) -> bool:
    return codigo in _registro


def obter(codigo: str) -> TipoDeNotificacao:
    """O tipo registrado. Código desconhecido é erro de programação, não de usuário."""
    try:
        return _registro[codigo]
    except KeyError:
        raise ValueError(f"Tipo de notificação desconhecido: {codigo!r}.") from None


def listar() -> list[TipoDeNotificacao]:
    return sorted(_registro.values(), key=lambda t: t.codigo)


def remover_para_testes(codigo: str) -> None:
    """Só para os testes desfazerem um registro. O sistema nunca remove um tipo em execução."""
    _registro.pop(codigo, None)
