"""Fixtures dos testes de `aprovacoes`. As comuns (usuários e clientes) ficam em `backend/conftest.py`.

O motor é exercitado com o tipo `teste.pedido` (com valor e a permissão `teste.aprovar`), registrado pela API
pública e removido no fim de cada teste, falhando ou não. O `ao_mudar` dele guarda o que recebeu.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from rest_framework.test import APIClient

from aprovacoes import public
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError
from tests import apoio
from tests.apoio import Usuario

TIPO = "teste.pedido"
APROVAR_TESTE = "teste.aprovar"
AUTO_APROVAR = "solicitacoes.auto_aprovar"
REABRIR = "solicitacoes.reabrir"
CANCELAR = "solicitacoes.cancelar"
SOLICITACOES = "/api/v1/aprovacoes/solicitacoes/"


def preparar_pedido(conteudo: dict[str, Any], solicitante_id: Any) -> public.ConteudoPreparado:
    """O módulo dono valida e normaliza: exige `descricao` e `valor` maior que zero."""
    erros: dict[str, list[str]] = {}
    descricao = conteudo.get("descricao")
    if not isinstance(descricao, str) or not descricao.strip():
        erros["descricao"] = ["Informe a descrição."]
    try:
        valor = Dinheiro(str(conteudo.get("valor")))
        if valor.quantia <= 0:
            erros["valor"] = ["O valor precisa ser maior que zero."]
    except TypeError, ValueError:
        erros["valor"] = ["Valor inválido."]
    if erros:
        raise BusinessError("VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details=erros)
    assert isinstance(descricao, str)
    return public.ConteudoPreparado(
        conteudo={"descricao": descricao.strip(), "valor": str(valor)}, valor=valor, resumo=descricao.strip()
    )


@dataclass
class TipoDeTeste:
    codigo: str
    recebidas: list[public.MudancaDeSolicitacao] = field(default_factory=list)


@pytest.fixture
def tipo_de_teste(db: None) -> Iterator[TipoDeTeste]:
    tipo = TipoDeTeste(TIPO)
    apoio.registrar_permissao_de_teste(APROVAR_TESTE)
    try:
        public.registrar_tipo(
            codigo=TIPO,
            nome="Pedido de teste",
            permissao_de_aprovar=APROVAR_TESTE,
            tem_valor=True,
            preparar=preparar_pedido,
            ao_mudar=tipo.recebidas.append,
        )
        yield tipo
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste(TIPO)
        apoio.remover_permissao_de_teste(APROVAR_TESTE)


def pedido(descricao: str = "Bolas de treino", valor: str = "150.00") -> dict[str, Any]:
    return {"descricao": descricao, "valor": valor}


def com_cargo(nome_de_usuario: str, *permissoes: str) -> Usuario:
    usuario = apoio.criar_diretor(nome_de_usuario)
    apoio.dar_cargo(usuario)
    for permissao in permissoes:
        apoio.conceder(usuario, permissao)
    return usuario


@pytest.fixture
def diretor_com_cargo(db: None) -> Usuario:
    return com_cargo("caio")


@pytest.fixture
def client_com_cargo(diretor_com_cargo: Usuario) -> APIClient:
    return apoio.cliente_de(diretor_com_cargo)


@pytest.fixture
def aprovador(tipo_de_teste: TipoDeTeste) -> Usuario:
    return com_cargo("dora", APROVAR_TESTE)
