"""Fixtures dos testes de `aprovacoes`. As comuns (usuários e clientes) ficam em `backend/conftest.py`."""

import pytest
from rest_framework.test import APIClient

from tests import apoio
from tests.apoio import Usuario


@pytest.fixture
def diretor_com_cargo(db: None) -> Usuario:
    usuario = apoio.criar_diretor("caio")
    apoio.dar_cargo(usuario)
    return usuario


@pytest.fixture
def client_com_cargo(diretor_com_cargo: Usuario) -> APIClient:
    return apoio.cliente_de(diretor_com_cargo)
