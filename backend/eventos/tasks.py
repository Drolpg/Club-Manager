"""Tarefas agendadas de `eventos`. Cada tarefa só chama um serviço do módulo (ADR-006)."""

from celery import shared_task


@shared_task(name="eventos.processar_rotina_diaria")
def processar_rotina_diaria() -> dict[str, int]:
    """Uma vez por dia, de manhã, depois da rotina do financeiro. Idempotente."""
    from django.utils import timezone

    from eventos.services import rotina_diaria

    return rotina_diaria.executar(timezone.localdate())
