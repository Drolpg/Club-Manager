from typing import ClassVar

from acesso.google import CredencialGoogleInvalida, IdentidadeGoogle


class VerificadorGoogleFalso:
    """Fake da fronteira com o Google: cada teste diz que credencial corresponde a que identidade."""

    identidades: ClassVar[dict[str, IdentidadeGoogle]] = {}

    def verificar(self, credencial: str) -> IdentidadeGoogle:
        try:
            return self.identidades[credencial]
        except KeyError:
            raise CredencialGoogleInvalida from None

    @classmethod
    def aceitar(
        cls, credencial: str, *, email: str, nome: str = "Nome no Google", sub: str | None = None
    ) -> None:
        cls.identidades[credencial] = IdentidadeGoogle(sub=sub or f"sub-{email}", email=email, nome=nome)
