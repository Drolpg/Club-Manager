"""Fixtures dos testes de `permissoes`. As comuns (usuários e clientes) ficam em `backend/conftest.py`."""

from collections.abc import Iterator

import pytest

from permissoes import catalogo

SENSIVEL = "teste.sensivel"
COMUM = "teste.comum"


@pytest.fixture
def permissoes_de_teste() -> Iterator[tuple[str, str]]:
    """Registra uma permissão comum e uma fora do acesso total; remove as duas no fim, falhando ou não."""
    catalogo.registrar_permissao(COMUM, "Comum de teste", "Entra no acesso total.")
    catalogo.registrar_permissao(
        SENSIVEL, "Sensível de teste", "Fica fora do acesso total.", fora_do_acesso_total=True
    )
    try:
        yield COMUM, SENSIVEL
    finally:
        catalogo.remover_para_testes(COMUM)
        catalogo.remover_para_testes(SENSIVEL)
