from django.apps import AppConfig


class AprovacoesConfig(AppConfig):
    name = "aprovacoes"
    verbose_name = "Aprovações"

    def ready(self) -> None:
        """Declara as permissões do motor e os tipos de notificação dele.

        `permissoes` e `notificacoes` iniciam antes (INSTALLED_APPS).
        """
        from aprovacoes import demonstracao, tipos
        from aprovacoes.services import avisos

        tipos.registrar_permissoes()
        avisos.registrar_tipos()
        # Só com DEBUG ligado e a variável definida (adendo 1): em produção, nunca.
        demonstracao.registrar_se_ligado()
