"""Apoio aos testes de serviço de `comunicacao`. Usuários por `tests/apoio.py`; as notificações, pela caixa
de entrada (a rota de `notificacoes`), como faria outro cliente.
"""

import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any
from unittest import mock

import pytest

from auditoria import public as auditoria
from comunicacao.domain.autorizacao import (
    PERM_ENVIAR_DOCUMENTOS,
    PERM_GERENCIAR,
    PERM_PUBLICAR,
    PERM_REGISTRAR_ATAS,
)
from comunicacao.models import CategoriaDeDocumento, Comunicado, Documento, VersaoDeDocumento
from tests import apoio
from tests.apoio import Usuario

CAIXA = "/api/v1/notificacoes/"


def diretor(nome_de_usuario: str, *codigos: str) -> Usuario:
    usuario = apoio.criar_diretor(nome_de_usuario)
    apoio.dar_cargo(usuario)
    for codigo in codigos:
        apoio.conceder(usuario, codigo)
    return usuario


def caixa(usuario: Usuario, tipo: str | None = None) -> list[dict[str, Any]]:
    resposta = apoio.cliente_de(usuario).get(CAIXA, {"limite": 50})
    assert resposta.status_code == 200, resposta.content
    itens = list(resposta.json()["itens"])
    return [n for n in itens if tipo is None or n["tipo"] == tipo]


def acoes_de(item_tipo: str, item_id: uuid.UUID) -> list[str]:
    return [r.acao for r in auditoria.historico_do_item(item_tipo, item_id)]


def registros_de(item_tipo: str, item_id: uuid.UUID, acao: str) -> list[Any]:
    return [r for r in auditoria.historico_do_item(item_tipo, item_id) if r.acao == acao]


def categoria(nome: str = "Institucional") -> CategoriaDeDocumento:
    return CategoriaDeDocumento.objects.get(nome=nome)


def documento(
    titulo: str = "Estatuto",
    *,
    enviado_por: Usuario | None = None,
    arquivado: bool = False,
    ata: bool = False,
) -> Documento:
    """Cria o documento direto no modelo (o serviço de documentos vem no checkpoint 6)."""
    campos: dict[str, Any] = {
        "titulo": titulo,
        "enviado_por_id": (enviado_por.id if enviado_por else uuid.uuid4()),
        "situacao": "ARQUIVADO" if arquivado else "VIGENTE",
    }
    if ata:
        campos |= {"tipo": "ATA", "data_da_reuniao": date(2026, 11, 1)}
    else:
        campos |= {"tipo": "DOCUMENTO", "categoria": categoria(), "categoria_nome": "Institucional"}
    criado = Documento.objects.create(**campos)
    VersaoDeDocumento.objects.create(
        documento=criado,
        numero=1,
        chave=f"documentos/{uuid.uuid4()}.pdf",
        nome="arquivo.pdf",
        mime="application/pdf",
        tamanho=10,
        enviada_por_id=criado.enviado_por_id,
    )
    return criado


def recarregado(comunicado: Comunicado) -> Comunicado:
    return Comunicado.objects.get(pk=comunicado.pk)


@pytest.fixture(autouse=True)
def _executar_na_hora_o_que_roda_depois_do_commit(request: pytest.FixtureRequest) -> Iterator[None]:
    """Cada teste roda numa transação que nunca é confirmada; o que o código agenda para depois do commit
    roda aqui na hora. O teste marcado com `sem_atalho_de_commit` prova que o envio só é agendado no commit.
    """
    if request.node.get_closest_marker("sem_atalho_de_commit"):
        yield
        return
    with mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()):
        yield


@pytest.fixture
def papeis(db: None) -> dict[str, Usuario]:
    """Autor, gerente, dois leitores, alguém que envia documentos, quem registra atas e quem não tem cargo."""
    return {
        "autor": diretor("autora", PERM_PUBLICAR),
        "gerente": diretor("gerente", PERM_GERENCIAR),
        "leitor": diretor("leitor"),
        "outro": diretor("outro.leitor"),
        "envia": diretor("envia", PERM_ENVIAR_DOCUMENTOS),
        "atas": diretor("atas", PERM_REGISTRAR_ATAS),
        "sem_cargo": apoio.criar_diretor("sem.cargo"),
        "admin": apoio.criar_admin(),
    }
