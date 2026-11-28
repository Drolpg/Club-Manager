from django.apps import AppConfig


class RelatoriosConfig(AppConfig):
    name = "relatorios"
    verbose_name = "Relatórios"

    def ready(self) -> None:
        """Declara os tipos de notificação e registra os sete tipos de relatório ao iniciar."""
        from relatorios import relatorios
        from relatorios.services import avisos

        avisos.registrar_tipos()
        relatorios.registrar_todos()
