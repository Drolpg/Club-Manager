"""Feed de comunicados e documentos."""

from django.apps import AppConfig


class ComunicacaoConfig(AppConfig):
    name = "comunicacao"
    verbose_name = "Comunicação"

    def ready(self) -> None:
        """Declara as permissões e os tipos de notificação ao iniciar."""
        from comunicacao import tipos

        tipos.registrar_catalogos()
