"""API pública do módulo `aprovacoes`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/architecture/project-structure.md).

- `registrar_tipo_de_decisao(codigo, nome)`: um módulo declara os tipos de decisão dele ao iniciar (RN-011).
- `motivo_aplicado(motivo_id, tipo_de_decisao)`: o texto do motivo a copiar na decisão; recusa motivo
  inexistente, inativo ou de outro tipo de decisão com `VALIDATION_ERROR` em `motivo_id`.
"""

from aprovacoes.services.motivos import motivo_aplicado
from aprovacoes.tipos import registrar_tipo_de_decisao

__all__ = ("motivo_aplicado", "registrar_tipo_de_decisao")
