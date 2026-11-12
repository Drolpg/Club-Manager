"""Aplicação Celery: fila e agendador (ADR-006).

O worker roda com o agendador embutido (`celery -A config worker -B`). As tarefas de cada módulo ficam em
`<modulo>/tasks.py` e são descobertas sozinhas.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("club_manager")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
