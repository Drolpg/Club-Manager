from collections.abc import Iterator

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from acesso.models import Situacao, Usuario
from acesso.services import usuarios

SENHA = "correta-bateria-grampo"


@pytest.fixture(autouse=True)
def _contadores_zerados() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin(db: None) -> Usuario:
    return usuarios.criar_admin(
        nome="Ana Admin",
        nome_de_usuario="ana.admin",
        email="ana@exemplo.com",
        telefone="11999990000",
        senha=SENHA,
    )


def criar_diretor(nome_de_usuario: str = "bia", situacao: Situacao = Situacao.ATIVO) -> Usuario:
    return usuarios.criar_usuario(
        nome=f"Diretor {nome_de_usuario}",
        nome_de_usuario=nome_de_usuario,
        email=f"{nome_de_usuario}@exemplo.com",
        telefone="11988887777",
        senha=SENHA,
        situacao=situacao,
    )


@pytest.fixture
def diretor(db: None) -> Usuario:
    return criar_diretor()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def entrar(client: APIClient, identificador: str, senha: str = SENHA) -> None:
    resposta = client.post("/api/v1/acesso/sessao/", {"identificador": identificador, "senha": senha})
    assert resposta.status_code == 200, resposta.content


@pytest.fixture
def client_admin(admin: Usuario) -> APIClient:
    client = APIClient()
    entrar(client, admin.nome_de_usuario)
    return client


@pytest.fixture
def client_diretor(diretor: Usuario) -> APIClient:
    client = APIClient()
    entrar(client, diretor.nome_de_usuario)
    return client
