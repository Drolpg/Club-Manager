from django.apps import AppConfig


class EventosConfig(AppConfig):
    name = "eventos"
    verbose_name = "Eventos"

    def ready(self) -> None:
        """Declara permissões, notificações, o tipo `eventos.evento` e os tratadores ao iniciar."""
        from eventos import handlers, tipos

        tipos.registrar_catalogos()
        handlers.registrar()
