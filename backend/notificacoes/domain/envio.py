"""Quando uma notificação vai por e-mail (NOT-R03). Função pura."""


def deve_enviar_email(pede_acao: bool, email_informativos: bool) -> bool:
    """A que pede ação sempre vai; a informativa vai, a menos que o destinatário tenha desligado."""
    return pede_acao or email_informativos
