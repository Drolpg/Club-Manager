"""Como `eventos` reage ao motor e ao financeiro (ADR-003). Os tratadores entram no checkpoint 5."""

import uuid
from typing import Any

from aprovacoes import public as aprovacoes


def preparar_solicitacao_do_evento(
    conteudo: dict[str, Any], solicitante_id: uuid.UUID
) -> aprovacoes.ConteudoPreparado:
    raise NotImplementedError("O retrato do evento entra no checkpoint 5.")


def ao_mudar_solicitacao_do_evento(mudanca: aprovacoes.MudancaDeSolicitacao) -> None:
    raise NotImplementedError("O recálculo da situação entra no checkpoint 5.")


def registrar() -> None:
    """Inscreve os tratadores de eventos de integração (checkpoint 5)."""
