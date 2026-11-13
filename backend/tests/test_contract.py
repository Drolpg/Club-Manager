"""O contrato da API é conferido em `acesso/tests/test_documentacao.py`: ele passou a exigir admin."""

from config.celery import app as celery_app


def test_celery_le_a_configuracao_do_django() -> None:
    assert celery_app.main == "club_manager"
    assert celery_app.conf.task_always_eager is True
    assert celery_app.conf.timezone == "America/Sao_Paulo"


def test_tarefa_agendada_de_descarte_esta_na_agenda() -> None:
    agenda = celery_app.conf.beat_schedule

    assert agenda["acesso.descartar_cadastros_vencidos"]["task"] == "acesso.descartar_cadastros_vencidos"
    assert agenda["acesso.descartar_cadastros_vencidos"]["schedule"] == 60 * 60
