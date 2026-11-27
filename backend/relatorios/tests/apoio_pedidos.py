"""Apoio dos testes de pedido, geração e expiração: tipos de relatório registrados só no teste (CA-27)."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest import mock

from django.utils import timezone
from rest_framework.test import APIClient

from permissoes import public as permissoes
from relatorios import tipos
from relatorios.domain import parametros
from relatorios.domain.documento import Coluna, Documento, ItemDoResumo, Tabela, TipoDeColuna
from relatorios.domain.pedido import Formato
from relatorios.models import PedidoDeRelatorio
from relatorios.services import pedidos
from tests.apoio import Usuario

TIPO = "TESTE_DA_GERACAO"
ZIP = "TESTE_DO_ZIP"
FALHA = "TESTE_DA_FALHA"
MES = {"mes": "2026-10"}

DOCUMENTO = Documento(
    titulo="Relatório de teste",
    parametros="De 01/10/2026 a 31/10/2026",
    resumo=(ItemDoResumo("Total", Decimal("10.00"), TipoDeColuna.DINHEIRO),),
    tabelas=(
        Tabela(
            "Linhas",
            (Coluna("Descrição", TipoDeColuna.TEXTO), Coluna("Valor", TipoDeColuna.DINHEIRO)),
            (("Mensalidade", Decimal("10.00")),),
        ),
    ),
)


def _um(_parametros: dict[str, Any], _contexto: tipos.Contexto) -> list[Documento]:
    return [DOCUMENTO]


def _dois(_parametros: dict[str, Any], _contexto: tipos.Contexto) -> list[Documento]:
    return [DOCUMENTO, DOCUMENTO]


def _falha(_parametros: dict[str, Any], _contexto: tipos.Contexto) -> list[Documento]:
    raise RuntimeError("detalhe interno com o nome Fulano de Tal")


def _tipo(
    codigo: str, montar: Callable[[dict[str, Any], tipos.Contexto], list[Documento]], *formatos: Formato
) -> tipos.TipoDeRelatorio:
    return tipos.TipoDeRelatorio(
        codigo=codigo,
        nome=f"Relatório {codigo.lower()}",
        formatos=formatos,
        pode_gerar=permissoes.le_gestao,
        validar_parametros=parametros.periodo,
        montar=montar,
    )


@contextmanager
def tipos_de_teste() -> Iterator[None]:
    for tipo in (
        _tipo(TIPO, _um, Formato.PDF, Formato.CSV),
        _tipo(ZIP, _dois, Formato.CSV),
        _tipo(FALHA, _falha, Formato.PDF),
    ):
        tipos.registrar_tipo_de_relatorio(tipo)
    try:
        yield
    finally:
        for codigo in (TIPO, ZIP, FALHA):
            tipos.remover_tipo_de_relatorio(codigo)


@contextmanager
def em(instante: datetime) -> Iterator[None]:
    with mock.patch("django.utils.timezone.now", return_value=instante):
        yield


def local(*partes: int) -> datetime:
    return timezone.make_aware(datetime(*partes))  # type: ignore[arg-type]


def na_fila(usuario: Usuario, tipo: str = TIPO, formato: str = "PDF") -> PedidoDeRelatorio:
    """O pedido entra na fila sem disparar a geração: o teste a chama quando quiser."""
    with (
        mock.patch("relatorios.tasks.gerar_relatorio.delay"),
        mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()),
    ):
        return pedidos.pedir(usuario.id, tipo=tipo, formato=formato, parametros=dict(MES))


def caixa(usuario: Usuario, tipo: str) -> list[dict[str, Any]]:
    """A caixa de entrada pela API, com sessão forçada: os testes mexem no relógio."""
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    resposta = cliente.get("/api/v1/notificacoes/", {"limite": 50})
    assert resposta.status_code == 200, resposta.content
    return [n for n in resposta.json()["itens"] if n["tipo"] == tipo]
