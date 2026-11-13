"""Tokens de verificação de e-mail, assinados com a chave do sistema. Não ficam guardados em lugar nenhum."""

import uuid

from django.core import signing

from acesso.domain.cadastro import PRAZO_DE_VERIFICACAO
from acesso.models import Usuario
from kernel.errors import BusinessError

_SAL = "acesso.verificacao-de-email"


def link_invalido() -> BusinessError:
    return BusinessError("LINK_INVALIDO", "Este link é inválido ou venceu. Peça outro.", status=400)


def gerar_token_de_verificacao(usuario: Usuario) -> str:
    return signing.dumps({"u": str(usuario.id), "e": usuario.email}, salt=_SAL)


def ler_token_de_verificacao(token: str) -> tuple[uuid.UUID, str]:
    """Devolve o ID do usuário e o e-mail a verificar, ou levanta `LINK_INVALIDO`."""
    try:
        dados = signing.loads(token, salt=_SAL, max_age=PRAZO_DE_VERIFICACAO)
        return uuid.UUID(dados["u"]), str(dados["e"])
    except (signing.BadSignature, KeyError, ValueError, TypeError) as erro:
        raise link_invalido() from erro
