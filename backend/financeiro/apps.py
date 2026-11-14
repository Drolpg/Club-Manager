from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    name = "financeiro"
    verbose_name = "Financeiro"

    def ready(self) -> None:
        """Declara permissões, tipos de decisão e notificações ao iniciar."""
        from financeiro import tipos

        tipos.registrar_catalogos()
