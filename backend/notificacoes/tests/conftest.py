"""Fixtures dos testes de `notificacoes`. As comuns (usuários e clientes) ficam em `backend/conftest.py`."""

from collections.abc import Iterator

import pytest

from notificacoes import tipos

PEDE_ACAO = "teste.pede_acao"
INFORMATIVO = "teste.informativo"


@pytest.fixture
def tipos_de_teste() -> Iterator[tuple[str, str]]:
    """Registra um tipo que pede ação e um informativo; remove os dois no fim, falhando ou não."""
    tipos.registrar_tipo(PEDE_ACAO, pede_acao=True, descricao="Tipo de teste que pede ação.")
    tipos.registrar_tipo(INFORMATIVO, pede_acao=False, descricao="Tipo de teste informativo.")
    try:
        yield PEDE_ACAO, INFORMATIVO
    finally:
        tipos.remover_para_testes(PEDE_ACAO)
        tipos.remover_para_testes(INFORMATIVO)
