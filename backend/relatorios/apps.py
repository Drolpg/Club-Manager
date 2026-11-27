from django.apps import AppConfig


class RelatoriosConfig(AppConfig):
    name = "relatorios"
    verbose_name = "Relatórios"

    def ready(self) -> None:
        """Declara os tipos de notificação ao iniciar."""
        from relatorios.services import avisos

        avisos.registrar_tipos()
