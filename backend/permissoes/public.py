"""API pública do módulo `permissoes`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/architecture/project-structure.md). Só devolve dataclasses, nunca modelos.

- `pode(usuario_id, codigo)` e `quem_pode(codigo)`: quem tem uma permissão do catálogo.
- `le_gestao(usuario_id)`: lê os dados de gestão (admin ativo, ou ativo com cargo ativo).
- `permissoes_de(usuario_id)` e `classificacao_de(usuario_id)`: o que o painel e a página inicial mostram.
- `registrar_permissao(...)`: cada módulo declara as suas permissões ao iniciar (AD-014).
"""

from permissoes.catalogo import registrar_permissao
from permissoes.domain.resolucao import Origem, TipoDeOrigem
from permissoes.services.consulta import (
    ClassificacaoInfo,
    ItemInfo,
    classificacao_de,
    le_gestao,
    permissoes_de,
    pode,
    quem_pode,
)

__all__ = (
    "ClassificacaoInfo",
    "ItemInfo",
    "Origem",
    "TipoDeOrigem",
    "classificacao_de",
    "le_gestao",
    "permissoes_de",
    "pode",
    "quem_pode",
    "registrar_permissao",
)
