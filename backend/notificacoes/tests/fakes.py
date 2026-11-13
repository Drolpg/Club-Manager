"""Fake da fronteira com o servidor de e-mail: falha as primeiras vezes e depois entrega."""

import smtplib
from typing import Any, ClassVar

from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend


class ServidorDeEmailInstavel(BaseEmailBackend):
    """Levanta `SMTPException` enquanto `falhas_restantes` for maior que zero; depois guarda o que recebe."""

    falhas_restantes: ClassVar[int] = 0
    chamadas: ClassVar[int] = 0
    entregues: ClassVar[list[EmailMessage]] = []

    @classmethod
    def reiniciar(cls, *, falhas: int) -> None:
        cls.falhas_restantes = falhas
        cls.chamadas = 0
        cls.entregues = []

    def send_messages(self, messages: Any) -> int:
        cls = type(self)
        cls.chamadas += 1
        if cls.falhas_restantes > 0:
            cls.falhas_restantes -= 1
            raise smtplib.SMTPServerDisconnected("servidor fora do ar")
        cls.entregues.extend(messages)
        return len(messages)
