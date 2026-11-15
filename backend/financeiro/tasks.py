"""Tarefas agendadas do módulo financeiro. Cada tarefa só chama um serviço (ADR-006)."""

from celery import shared_task


@shared_task(name="financeiro.processar_rotina_diaria")
def processar_rotina_diaria() -> dict[str, int]:
    """Executa a rotina diária uma vez por dia, de forma idempotente."""
    from django.utils import timezone

    from financeiro.services import rotina_diaria

    return rotina_diaria.executar(timezone.localdate())
