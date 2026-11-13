"""Prazo de verificação de um cadastro com senha (regra 8 da especificação funcional)."""

from datetime import datetime, timedelta

PRAZO_DE_VERIFICACAO = timedelta(hours=24)


def cadastro_vencido(*, agora: datetime, criado_em: datetime) -> bool:
    """Cadastro que não foi verificado em 24 horas não verifica mais e é descartado (ACE-R06)."""
    return agora >= criado_em + PRAZO_DE_VERIFICACAO
