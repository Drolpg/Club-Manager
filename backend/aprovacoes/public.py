"""API pública do módulo `aprovacoes`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/architecture/project-structure.md).

- `registrar_tipo(...)`: um módulo registra um tipo de solicitação ao iniciar, com a permissão de quem decide,
  se tem valor, o `preparar` que valida o conteúdo e o `ao_mudar` que recebe cada `MudancaDeSolicitacao`.
- `enviar(...)`: o módulo dono abre uma solicitação em processo e recebe o ID (adendo 1 da technical-spec).
- `registrar_tipo_de_decisao(codigo, nome)`: um módulo declara os tipos de decisão dele ao iniciar (RN-011).
- `motivo_aplicado(motivo_id, tipo_de_decisao)`: o texto do motivo a copiar na decisão; recusa motivo
  inexistente, inativo ou de outro tipo de decisão com `VALIDATION_ERROR` em `motivo_id`.
"""

import uuid
from typing import Any

from aprovacoes.services import solicitacoes
from aprovacoes.services.motivos import motivo_aplicado
from aprovacoes.tipos import (
    Acontecimento,
    ConteudoPreparado,
    MudancaDeSolicitacao,
    registrar_tipo,
    registrar_tipo_de_decisao,
)


def enviar(
    *,
    tipo: str,
    conteudo: dict[str, Any],
    solicitante_id: uuid.UUID,
    aprovador_indicado_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Envia uma solicitação em nome do solicitante, com as mesmas regras da rota, e devolve o ID dela."""
    solicitacao = solicitacoes.enviar(
        ator_id=solicitante_id, tipo=tipo, conteudo=conteudo, aprovador_indicado_id=aprovador_indicado_id
    )
    return solicitacao.id


__all__ = (
    "Acontecimento",
    "ConteudoPreparado",
    "MudancaDeSolicitacao",
    "enviar",
    "motivo_aplicado",
    "registrar_tipo",
    "registrar_tipo_de_decisao",
)
