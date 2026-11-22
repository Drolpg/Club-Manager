"""API pública do módulo `comunicacao`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/sdd/02-plan.md).

- `ultimos_comunicados(limite)`: os publicados mais recentes, para o dashboard. Só leitura; quem pode ver é de
  quem chama.
"""

from comunicacao.services.consulta import ComunicadoRecente, ultimos_comunicados

__all__ = ("ComunicadoRecente", "ultimos_comunicados")
