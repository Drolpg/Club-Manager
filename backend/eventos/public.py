"""API pública do módulo `eventos`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/sdd/02-plan.md).

- `eventos_do_usuario(usuario_id, ...)`: os eventos que o usuário propôs ou em que respondeu à presença do
  ciclo atual, para o perfil. Só leitura; quem pode ver é de quem chama.
- `proximos_eventos(a_partir_de, limite)`: os próximos publicados, para o dashboard. Só leitura.
"""

from eventos.services.consulta import (
    EventoDoUsuario,
    PaginaDeEventosDoUsuario,
    ProximoEvento,
    eventos_do_usuario,
    proximos_eventos,
)

__all__ = (
    "EventoDoUsuario",
    "PaginaDeEventosDoUsuario",
    "ProximoEvento",
    "eventos_do_usuario",
    "proximos_eventos",
)
