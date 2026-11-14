"""API pública do módulo `auditoria`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/sdd/02-plan.md).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from auditoria.models import RegistroDeAuditoria


@dataclass(frozen=True)
class Registro:
    """Um registro de auditoria, para leitura. Não é o modelo persistido."""

    ator_id: uuid.UUID | None
    acao: str
    item_tipo: str
    item_id: uuid.UUID
    justificativa: str
    dados: dict[str, Any]
    criado_em: datetime


def registrar(
    *,
    ator_id: uuid.UUID | None,
    acao: str,
    item_tipo: str,
    item_id: uuid.UUID,
    justificativa: str = "",
    dados: dict[str, Any] | None = None,
) -> None:
    """Grava uma ação relevante. Chame dentro da transação do caso de uso (ADR-003).

    `ator_id` é nulo quando a ação vem do sistema ou de um comando no servidor. `dados` leva só IDs e códigos:
    nunca dado pessoal, senha ou token.
    """
    RegistroDeAuditoria.objects.create(
        ator_id=ator_id,
        acao=acao,
        item_tipo=item_tipo,
        item_id=item_id,
        justificativa=justificativa,
        dados=dados or {},
    )


def historico_do_item(item_tipo: str, item_id: uuid.UUID) -> list[Registro]:
    """Os registros de um item, do mais antigo para o mais novo."""
    registros = RegistroDeAuditoria.objects.filter(item_tipo=item_tipo, item_id=item_id)
    return [
        Registro(
            ator_id=r.ator_id,
            acao=r.acao,
            item_tipo=r.item_tipo,
            item_id=r.item_id,
            justificativa=r.justificativa,
            dados=r.dados,
            criado_em=r.criado_em,
        )
        for r in registros
    ]
