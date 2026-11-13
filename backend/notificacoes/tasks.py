"""Tarefas de notificações. Cada uma só chama um serviço e recebe apenas IDs (ADR-006)."""

import smtplib
import uuid
from typing import Any

from celery import Task, shared_task

# Espera crescente entre as tentativas: 60 s, 2 min, 4 min e 8 min (com variação), até o limite.
_ESPERA_INICIAL = 60
_ESPERA_MAXIMA = 60 * 60
# A primeira execução mais quatro novas tentativas: no máximo 5 (technical-spec, "E-mail").
_NOVAS_TENTATIVAS = 4


class _TarefaDeEmail(Task):  # type: ignore[misc]
    """Quando a tarefa desiste (tentativas esgotadas ou erro que não se repete), grava `FALHOU`."""

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple[Any, ...], kwargs: dict[str, Any], einfo: Any
    ) -> None:
        from notificacoes.services import email

        notificacao_id = args[0] if args else kwargs["notificacao_id"]
        email.registrar_falha(uuid.UUID(notificacao_id))


@shared_task(
    base=_TarefaDeEmail,
    name="notificacoes.enviar_email",
    autoretry_for=(OSError, smtplib.SMTPException),
    retry_backoff=_ESPERA_INICIAL,
    retry_backoff_max=_ESPERA_MAXIMA,
    retry_jitter=True,
    max_retries=_NOVAS_TENTATIVAS,
)
def enviar_email(notificacao_id: str) -> None:
    from notificacoes.services import email

    email.enviar(uuid.UUID(notificacao_id))
