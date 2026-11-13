"""As respostas que `permissoes` dá às portas de `acesso` (adendo 1 da ADR-003)."""

import uuid
from collections.abc import Collection

from permissoes.catalogo import CONVITES_GERENCIAR
from permissoes.models import Classificacao
from permissoes.services import consulta


def pode_gerenciar_convites(usuario_id: uuid.UUID) -> bool:
    """Admin ativo ou quem tem `convites.gerenciar`. O admin tem todas as permissões do catálogo (PER-R02)."""
    return consulta.pode(usuario_id, CONVITES_GERENCIAR)


def usuarios_com_cargo(usuario_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
    """Dos IDs recebidos, os que têm classificação. Uma consulta para todos."""
    return set(Classificacao.objects.filter(usuario_id__in=usuario_ids).values_list("usuario_id", flat=True))
