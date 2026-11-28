"""API pública do módulo `eventos`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/sdd/02-plan.md).

- `eventos_do_usuario(usuario_id, ...)`: os eventos que o usuário propôs ou em que respondeu à presença do
  ciclo atual, para o perfil. Só leitura; quem pode ver é de quem chama.
- `proximos_eventos(a_partir_de, limite)`: os próximos publicados, para o dashboard. Só leitura.
- `eventos_do_periodo(de, ate)`: os eventos com data no período, de qualquer situação, com o motivo do
  cancelamento e as presenças do ciclo atual, para o relatório de eventos. Só leitura.
"""

from eventos.services.consulta import (
    EventoDoPeriodo,
    EventoDoUsuario,
    PaginaDeEventosDoUsuario,
    ProximoEvento,
    eventos_do_periodo,
    eventos_do_usuario,
    proximos_eventos,
)

__all__ = (
    "EventoDoPeriodo",
    "EventoDoUsuario",
    "PaginaDeEventosDoUsuario",
    "ProximoEvento",
    "eventos_do_periodo",
    "eventos_do_usuario",
    "proximos_eventos",
)
