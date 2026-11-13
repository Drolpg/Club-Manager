from django.apps import AppConfig


class PermissoesConfig(AppConfig):
    name = "permissoes"
    verbose_name = "Permissões"

    def ready(self) -> None:
        """Registra as respostas das portas de `acesso`: `permissoes` está acima e `acesso` não o conhece."""
        from acesso import public as acesso
        from permissoes.services import portas

        acesso.registrar_portas(
            pode_gerenciar_convites=portas.pode_gerenciar_convites,
            usuarios_com_cargo=portas.usuarios_com_cargo,
        )
