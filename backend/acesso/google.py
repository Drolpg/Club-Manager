"""Fronteira com o Google (ADR-008).

O Google só diz quem é a pessoa. A conta, a situação e as permissões são sempre as do sistema.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class IdentidadeGoogle:
    sub: str
    email: str
    nome: str


class CredencialGoogleInvalida(Exception):
    """A credencial não é um token de identidade válido do Google para este sistema."""


class VerificadorGoogle(Protocol):
    def verificar(self, credencial: str) -> IdentidadeGoogle: ...


class VerificadorGoogleReal:
    """Valida o token de identidade devolvido pelo botão "Entrar com o Google".

    A biblioteca confere a assinatura, a validade, o emissor e o público-alvo (o ID de cliente do clube). Aqui
    se exige também que o Google tenha verificado o e-mail.
    """

    def __init__(self, client_id: str | None = None, transporte: Any = None) -> None:
        self.client_id = settings.GOOGLE_CLIENT_ID if client_id is None else client_id
        self.transporte = transporte

    def verificar(self, credencial: str) -> IdentidadeGoogle:
        # Importado aqui para o resto do sistema não depender da biblioteca do Google.
        from google.auth.transport import requests as transporte_do_google
        from google.oauth2 import id_token

        if not self.client_id:
            raise CredencialGoogleInvalida
        transporte = self.transporte or transporte_do_google.Request()
        try:
            # A biblioteca do Google não tem tipos.
            conteudo: dict[str, Any] = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                credencial, transporte, audience=self.client_id
            )
        except Exception as erro:
            # A biblioteca levanta tipos diferentes para token malformado, vencido ou de outro público.
            raise CredencialGoogleInvalida from erro
        if not conteudo.get("email_verified") or not conteudo.get("email") or not conteudo.get("sub"):
            raise CredencialGoogleInvalida
        return IdentidadeGoogle(
            sub=str(conteudo["sub"]), email=str(conteudo["email"]), nome=str(conteudo.get("name", ""))
        )


def obter_verificador() -> VerificadorGoogle:
    verificador: VerificadorGoogle = import_string(settings.GOOGLE_VERIFIER)()
    return verificador
