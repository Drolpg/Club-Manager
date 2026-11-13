"""Apoio compartilhado pelos testes de todos os módulos: criar usuários e entrar pela API.

Os testes de outros módulos pegam `Usuario` e `Situacao` daqui, e não de `acesso.models`: a regra de só
importar a API pública de outro módulo vale também para os testes.
"""

from rest_framework.test import APIClient

from acesso.models import Situacao, Usuario
from acesso.services import usuarios

SENHA = "correta-bateria-grampo"


def criar_admin(nome_de_usuario: str = "ana.admin") -> Usuario:
    return usuarios.criar_admin(
        nome="Ana Admin",
        nome_de_usuario=nome_de_usuario,
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


def entrar(client: APIClient, identificador: str, senha: str = SENHA) -> None:
    resposta = client.post("/api/v1/acesso/sessao/", {"identificador": identificador, "senha": senha})
    assert resposta.status_code == 200, resposta.content


def cliente_de(usuario: Usuario) -> APIClient:
    client = APIClient()
    entrar(client, usuario.nome_de_usuario)
    return client


__all__ = ("SENHA", "Situacao", "Usuario", "cliente_de", "criar_admin", "criar_diretor", "entrar")
