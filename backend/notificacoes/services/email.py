"""Envio do e-mail de uma notificação. O envio de verdade entra no checkpoint 3."""

import uuid


def enviar(notificacao_id: uuid.UUID) -> None:
    raise NotImplementedError("O envio do e-mail entra no checkpoint 3.")
