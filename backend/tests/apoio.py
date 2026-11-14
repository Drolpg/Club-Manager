"""Apoio aos testes de todos os módulos: criar usuários, dar cargo e permissão, e entrar pela API.

Os testes de outros módulos pegam `Usuario` e `Situacao` daqui, e não de `acesso.models`: a regra de só
importar a API pública de outro módulo vale também para os testes. Pelo mesmo motivo, registrar e remover uma
permissão de teste do catálogo, ou dar cargo e permissão sem passar pelas rotas, ficam aqui.
"""

from django.utils import timezone
from rest_framework.test import APIClient

from acesso.models import Situacao, Usuario
from acesso.services import usuarios
from aprovacoes import tipos as tipos_de_solicitacao
from permissoes import catalogo
from permissoes.models import AlvoDaConcessao, Cargo, Classificacao, Concessao

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


def dar_cargo(usuario: Usuario, cargo: str = "Diretor") -> None:
    """Classifica o usuário com um cargo ativo, sem setores. Cria o cargo se ele não existir."""
    item, _ = Cargo.objects.get_or_create(nome=cargo)
    Classificacao.objects.update_or_create(usuario_id=usuario.id, defaults={"cargo": item})


def conceder(usuario: Usuario, permissao: str) -> None:
    """Concede uma permissão do catálogo direto ao usuário."""
    Concessao.objects.create(
        permissao=permissao,
        alvo_tipo=AlvoDaConcessao.USUARIO,
        usuario_id=usuario.id,
        concedida_por_id=usuario.id,
        concedida_em=timezone.now(),
    )


def registrar_permissao_de_teste(codigo: str, *, fora_do_acesso_total: bool = False) -> None:
    catalogo.registrar_permissao(
        codigo, f"Permissão de teste {codigo}", "Só para testes.", fora_do_acesso_total=fora_do_acesso_total
    )


def remover_permissao_de_teste(codigo: str) -> None:
    catalogo.remover_para_testes(codigo)


def remover_tipo_de_solicitacao_de_teste(codigo: str) -> None:
    """Desfaz o `aprovacoes.public.registrar_tipo` de um teste."""
    tipos_de_solicitacao.remover_tipo_para_testes(codigo)


__all__ = (
    "SENHA",
    "Situacao",
    "Usuario",
    "cliente_de",
    "conceder",
    "criar_admin",
    "criar_diretor",
    "dar_cargo",
    "entrar",
    "registrar_permissao_de_teste",
    "remover_permissao_de_teste",
    "remover_tipo_de_solicitacao_de_teste",
)
