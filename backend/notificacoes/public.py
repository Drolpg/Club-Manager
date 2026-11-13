"""API pública do módulo `notificacoes`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/architecture/project-structure.md).

- `notificar(...)`: registra a notificação para cada destinatário ativo e agenda o e-mail depois do commit.
  Chame dentro da transação do caso de uso; a `chave` identifica o fato e impede a duplicata.
- `registrar_tipo(...)`: cada módulo declara os seus tipos de notificação ao iniciar.
"""

from notificacoes.services.envio import notificar
from notificacoes.tipos import registrar_tipo

__all__ = ("notificar", "registrar_tipo")
