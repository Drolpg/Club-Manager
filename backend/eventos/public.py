"""API pública do módulo `eventos`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/sdd/02-plan.md).

- `eventos_do_usuario(usuario_id, ...)`: os eventos que o usuário propôs ou em que respondeu à presença do
  ciclo atual, para o perfil. Só leitura; quem pode ver é de quem chama.
"""

from eventos.services.consulta import EventoDoUsuario, PaginaDeEventosDoUsuario, eventos_do_usuario

__all__ = ("EventoDoUsuario", "PaginaDeEventosDoUsuario", "eventos_do_usuario")
