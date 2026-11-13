"""Registro de notificações, caixa de entrada, e-mail e preferências."""

from django.apps import AppConfig


class NotificacoesConfig(AppConfig):
    name = "notificacoes"
    verbose_name = "Notificações"

    def ready(self) -> None:
        """Declara os tipos do módulo e registra os tratadores dos eventos de `acesso` e `permissoes`.

        Os dois estão abaixo e não conhecem `notificacoes` (ADR-003): quem registra o tratador é este módulo.
        """
        from notificacoes import handlers

        handlers.registrar()
