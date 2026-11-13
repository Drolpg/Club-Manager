"""As fixtures ficam em `backend/conftest.py`. Aqui só os nomes que os testes deste módulo importam."""

from tests.apoio import SENHA, criar_diretor, entrar

__all__ = ("SENHA", "criar_diretor", "entrar")
