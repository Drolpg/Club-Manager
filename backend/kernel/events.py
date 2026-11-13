"""Despachante de eventos de integração, em processo e síncrono (ADR-003).

Não é um barramento: não há fila nem entrega posterior. `publish` chama os tratadores na hora, na ordem em que
foram registrados e na transação de quem publicou; a exceção de um tratador propaga e desfaz a operação.
O evento é um `@dataclass(frozen=True)` definido na API pública do módulo que o publica. O `kernel` não
conhece nenhum módulo: o despachante só enxerga o tipo do evento.
"""

from collections.abc import Callable
from typing import Any

type Tratador = Callable[[Any], None]

_tratadores: dict[type, list[Tratador]] = {}


def subscribe(tipo_do_evento: type, tratador: Tratador) -> None:
    """Registra o tratador para o tipo exato do evento. Registrar o mesmo tratador de novo não duplica."""
    registrados = _tratadores.setdefault(tipo_do_evento, [])
    if tratador not in registrados:
        registrados.append(tratador)


def publish(evento: object) -> None:
    """Chama os tratadores do tipo exato do evento (a subclasse não conta). A exceção de um propaga."""
    for tratador in list(_tratadores.get(type(evento), ())):
        tratador(evento)


def unsubscribe_all_for_tests() -> None:
    """Só para os testes: esvazia o registro."""
    _tratadores.clear()


def copiar_registro() -> dict[type, list[Tratador]]:
    """Só para os testes: uma cópia do registro, para a fixture devolvê-lo no fim."""
    return {tipo: list(tratadores) for tipo, tratadores in _tratadores.items()}


def restaurar_registro(registro: dict[type, list[Tratador]]) -> None:
    """Só para os testes: troca o registro pelo que `copiar_registro` guardou."""
    _tratadores.clear()
    _tratadores.update({tipo: list(tratadores) for tipo, tratadores in registro.items()})
