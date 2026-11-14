from django.apps import AppConfig


class AprovacoesConfig(AppConfig):
    name = "aprovacoes"
    verbose_name = "Aprovações"

    def ready(self) -> None:
        """Declara as permissões do motor no catálogo de `permissoes`, que inicia antes (INSTALLED_APPS)."""
        from aprovacoes import tipos

        tipos.registrar_permissoes()
