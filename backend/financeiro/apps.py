from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    name = "financeiro"
    verbose_name = "Financeiro"

    def ready(self) -> None:
        """Declara permissões, tipos de decisão, notificações e tratadores ao iniciar."""
        from financeiro import handlers, tipos

        tipos.registrar_catalogos()
        handlers.registrar()
