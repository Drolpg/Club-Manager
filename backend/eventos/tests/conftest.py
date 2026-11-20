"""Apoio aos testes de serviço de `eventos`. Usuários por `tests/apoio.py`; o motor e o financeiro só pela API
pública ou pelas rotas, como faria outro cliente.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from django.utils import timezone

from eventos.models import CategoriaDeEvento, Evento
from financeiro import public as financeiro
from permissoes import public as permissoes
from tests import apoio
from tests.apoio import Usuario

SOLICITACOES = "/api/v1/aprovacoes/solicitacoes/"
CAIXA = "/api/v1/notificacoes/"


def diretor(nome_de_usuario: str, *codigos: str) -> Usuario:
    usuario = apoio.criar_diretor(nome_de_usuario)
    apoio.dar_cargo(usuario)
    for codigo in codigos:
        apoio.conceder(usuario, codigo)
    return usuario


def motivo(usuario: Usuario, tipo_de_decisao: str) -> str:
    resposta = apoio.cliente_de(usuario).get(
        "/api/v1/aprovacoes/motivos/", {"tipo_de_decisao": tipo_de_decisao}
    )
    assert resposta.status_code == 200, resposta.content
    return str(resposta.json()[0]["id"])


def decidir(usuario: Usuario, solicitacao_id: uuid.UUID, acao: str, **corpo: Any) -> Any:
    """Decide pela rota do motor, com o primeiro motivo do tipo de decisão."""
    corpo.setdefault("motivo_id", motivo(usuario, f"solicitacao.{acao}"))
    corpo.setdefault("texto", "")
    if acao == "contestar":
        corpo.setdefault("mensagem", "Ajuste, por favor.")
    return apoio.cliente_de(usuario).post(f"{SOLICITACOES}{solicitacao_id}/{acao}/", corpo, format="json")


def aprovar(usuario: Usuario, solicitacao_id: uuid.UUID) -> None:
    resposta = decidir(usuario, solicitacao_id, "aprovar")
    assert resposta.status_code == 200, resposta.content


def caixa(usuario: Usuario, tipo: str | None = None) -> list[dict[str, Any]]:
    resposta = apoio.cliente_de(usuario).get(CAIXA, {"limite": 50})
    assert resposta.status_code == 200, resposta.content
    itens = list(resposta.json()["itens"])
    return [n for n in itens if tipo is None or n["tipo"] == tipo]


def categoria(nome: str = "Jogo") -> CategoriaDeEvento:
    return CategoriaDeEvento.objects.get(nome=nome)


def daqui_a(dias: int = 7) -> datetime:
    return timezone.now() + timedelta(days=dias)


def proposta(**mudar: Any) -> dict[str, Any]:
    dados: dict[str, Any] = {
        "titulo": "Amistoso contra o Vila",
        "descricao": "Jogo de fim de ano",
        "inicio": daqui_a(),
        "local": "Campo do bairro",
        "categoria_id": categoria().id,
        "envolve_custo": False,
    }
    dados.update(mudar)
    return dados


def itens_do_orcamento(valor: str = "400.00") -> dict[str, Any]:
    eventos = next(c for c in financeiro.listar_categorias_ativas(natureza="SAIDA") if c.nome == "Eventos")
    return {
        "descricao": "Orçamento do amistoso",
        "categoria_id": eventos.id,
        "setor_id": permissoes.listar_setores_ativos()[0].id,
        "itens": [{"descricao": "Arbitragem", "valor": valor}],
    }


def conteudo_da_tela(valor: str) -> dict[str, Any]:
    """O mesmo corpo de `conteudoEstruturado()` em `AcoesDaSolicitacao.tsx`, para o orçamento."""
    dados = itens_do_orcamento(valor)
    return {
        "descricao": dados["descricao"],
        "categoria_id": str(dados["categoria_id"]),
        "setor_id": str(dados["setor_id"]),
        "itens": dados["itens"],
        "cotacao_id": None,
    }


def recarregado(evento: Evento) -> Evento:
    return Evento.objects.get(pk=evento.pk)


@pytest.fixture
def papeis(db: None) -> dict[str, Usuario]:
    """Proponente, aprovador de eventos (o responsável), aprovador de gastos e um diretor comum."""
    return {
        "proponente": diretor("prop", "eventos.propor"),
        "aprovador": diretor("resp.eventos", "eventos.aprovar"),
        "gastos": diretor("apr.gastos", "gastos.aprovar"),
        "comum": diretor("comum"),
    }
