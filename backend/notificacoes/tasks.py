"""Tarefas de notificações. Cada uma só chama um serviço e recebe apenas IDs (ADR-006)."""

import uuid

from celery import shared_task


@shared_task(name="notificacoes.enviar_email")
def enviar_email(notificacao_id: str) -> None:
    from notificacoes.services import email

    email.enviar(uuid.UUID(notificacao_id))
