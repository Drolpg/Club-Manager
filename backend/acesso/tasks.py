"""Tarefas do acesso. Cada uma só chama um serviço (ADR-006) e recebe apenas IDs.

Os serviços são importados dentro de cada tarefa porque eles próprios enfileiram tarefas deste arquivo.
"""

import uuid

from celery import shared_task


@shared_task(name="acesso.enviar_email_de_verificacao")
def enviar_email_de_verificacao(usuario_id: str) -> None:
    from acesso.services import emails

    emails.enviar_verificacao(uuid.UUID(usuario_id))


@shared_task(name="acesso.enviar_email_de_recuperacao")
def enviar_email_de_recuperacao(usuario_id: str) -> None:
    from acesso.services import emails

    emails.enviar_recuperacao(uuid.UUID(usuario_id))


@shared_task(name="acesso.descartar_cadastros_vencidos")
def descartar_cadastros_vencidos() -> int:
    """Agendada de hora em hora. Idempotente: rodar de novo não encontra nada para descartar."""
    from acesso.services import cadastro

    return cadastro.descartar_cadastros_vencidos()
