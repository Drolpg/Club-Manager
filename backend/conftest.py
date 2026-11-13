"""Fixtures compartilhadas pelos testes de todos os módulos."""

from collections.abc import Iterator

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from acesso.models import Usuario
from tests import apoio


@pytest.fixture(autouse=True)
def _contadores_zerados() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin(db: None) -> Usuario:
    return apoio.criar_admin()


@pytest.fixture
def diretor(db: None) -> Usuario:
    return apoio.criar_diretor()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def client_admin(admin: Usuario) -> APIClient:
    return apoio.cliente_de(admin)


@pytest.fixture
def client_diretor(diretor: Usuario) -> APIClient:
    return apoio.cliente_de(diretor)
