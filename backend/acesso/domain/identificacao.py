"""Formato dos dados que identificam um usuário (regras 4, 5 e 7 da especificação funcional)."""

import re

_NOME_DE_USUARIO = re.compile(r"[A-Za-z0-9._-]{3,30}")
_TELEFONE = re.compile(r"\+?[0-9]{8,15}")
_SEPARADORES_DE_TELEFONE = re.compile(r"[\s().-]")


def nome_de_usuario_valido(nome_de_usuario: str) -> bool:
    """De 3 a 30 caracteres: letras sem acento, números, ponto, hífen e sublinhado."""
    return _NOME_DE_USUARIO.fullmatch(nome_de_usuario) is not None


def normalizar_email(email: str) -> str:
    """O e-mail é comparado e guardado em minúsculas, para o mesmo endereço nunca virar duas contas."""
    return email.strip().lower()


def normalizar_telefone(telefone: str) -> str:
    """Tira espaços, parênteses, pontos e hifens; mantém os dígitos e o `+` inicial."""
    return _SEPARADORES_DE_TELEFONE.sub("", telefone)


def telefone_valido(telefone_normalizado: str) -> bool:
    """De 8 a 15 dígitos, com `+` opcional na frente. Não confere operadora nem país."""
    return _TELEFONE.fullmatch(telefone_normalizado) is not None
