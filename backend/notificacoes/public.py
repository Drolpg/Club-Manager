"""API pública do módulo `notificacoes`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/sdd/02-plan.md).

- `notificar(...)`: registra a notificação para cada destinatário ativo e agenda o e-mail depois do commit.
  Chame dentro da transação do caso de uso; a `chave` identifica o fato e impede a duplicata.
- `registrar_tipo(...)`: cada módulo declara os seus tipos de notificação ao iniciar.
- `resumo_da_caixa(usuario_id)`: só a quantidade de não lidas, para o perfil. Só leitura; quem pode ver é de
  quem chama.
"""

import uuid
from dataclasses import dataclass

from notificacoes.services import consulta
from notificacoes.services.envio import notificar
from notificacoes.tipos import registrar_tipo

__all__ = ("ResumoDaCaixa", "notificar", "registrar_tipo", "resumo_da_caixa")


@dataclass(frozen=True)
class ResumoDaCaixa:
    nao_lidas: int


def resumo_da_caixa(usuario_id: uuid.UUID) -> ResumoDaCaixa:
    """A quantidade de não lidas do usuário. Não expõe o ID da mais recente nem as notificações."""
    return ResumoDaCaixa(nao_lidas=consulta.resumo(usuario_id).nao_lidas)
