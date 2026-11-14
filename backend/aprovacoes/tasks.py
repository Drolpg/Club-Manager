"""Tarefas de aprovações. Cada uma só chama um serviço do módulo (ADR-006)."""

from celery import shared_task


@shared_task(name="aprovacoes.lembrar_solicitacoes_paradas")
def lembrar_solicitacoes_paradas() -> int:
    """Agendada uma vez por dia, de manhã. Idempotente: rodar de novo não repete nenhum aviso."""
    from django.utils import timezone

    from aprovacoes.services import lembretes

    return lembretes.lembrar_paradas(timezone.now())
