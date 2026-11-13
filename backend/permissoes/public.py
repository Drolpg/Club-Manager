"""API pública do módulo `permissoes`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/architecture/project-structure.md). Só devolve dataclasses, nunca modelos.

- `pode(usuario_id, codigo)` e `quem_pode(codigo)`: quem tem uma permissão do catálogo.
- `le_gestao(usuario_id)`: lê os dados de gestão (admin ativo, ou ativo com cargo ativo).
- `permissoes_de(usuario_id)` e `classificacao_de(usuario_id)`: o que o painel e a página inicial mostram.
- `registrar_permissao(...)`: cada módulo declara as suas permissões ao iniciar (AD-014).
"""

import uuid
from dataclasses import dataclass

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


@dataclass(frozen=True)
class ClassificacaoAlterada:
    """Evento de integração: o usuário foi classificado, reclassificado ou ficou sem cargo."""

    usuario_id: uuid.UUID


@dataclass(frozen=True)
class ConcessaoIndividualAlterada:
    """Evento de integração: o usuário ganhou (`concedida=True`) ou perdeu uma permissão concedida a ele."""

    usuario_id: uuid.UUID
    permissao: str
    concedida: bool


__all__ = (
    "ClassificacaoAlterada",
    "ClassificacaoInfo",
    "ConcessaoIndividualAlterada",
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
