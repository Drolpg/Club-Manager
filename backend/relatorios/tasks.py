"""Tarefas do Celery de `relatorios`: cada uma só chama um serviço do módulo (ADR-006).

Recebem só o ID do pedido, nunca token nem dado. Sem `retry` automático: a falha vira `FALHOU` com aviso, e
repetir é decisão de quem pediu (D3).
"""

import uuid

from celery import shared_task


@shared_task(name="relatorios.gerar_relatorio")
def gerar_relatorio(pedido_id: str) -> None:
    from relatorios.services import geracao

    geracao.gerar(uuid.UUID(pedido_id))


@shared_task(name="relatorios.processar_rotina_diaria")
def processar_rotina_diaria() -> dict[str, int]:
    """Uma vez por dia, às 03h00: expira os arquivos e dá como falha o que parou (D8). Idempotente."""
    from django.utils import timezone

    from relatorios.services import rotina_diaria

    return rotina_diaria.executar(timezone.now())
