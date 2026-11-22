"""Contagens públicas para o dashboard (N14 da spec `relatorios/dashboard-e-lancamentos`; CA-08).

`quantidade_na_fila` conta a mesma consulta da fila de pendências, sem conferir quem pergunta (é de quem
chama); `em_analise_por_tipo` agrupa as solicitações em análise do clube.
"""

import pytest

from aprovacoes import public
from aprovacoes.services import consulta
from aprovacoes.tests.conftest import (
    APROVAR_TESTE,
    AUTO_APROVAR,
    TipoDeTeste,
    com_cargo,
    enviada,
    levar_a,
)
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db


def _iguais(usuario: Usuario) -> int:
    quantidade = public.quantidade_na_fila(usuario.id)
    assert quantidade == len(consulta.fila(usuario.id))
    return quantidade


def test_quantidade_na_fila_e_a_mesma_da_fila_para_cada_papel(tipo_de_teste: TipoDeTeste) -> None:
    solicitante = com_cargo("sol")
    aprovador = com_cargo("apr", APROVAR_TESTE)
    indicado = com_cargo("ind")
    auto = com_cargo("auto", APROVAR_TESTE, AUTO_APROVAR)
    admin = apoio.criar_admin("adm")
    enviada(solicitante)
    enviada(solicitante)
    enviada(aprovador, indicado=indicado)
    enviada(auto)
    levar_a(enviada(solicitante), "CONTESTADA")
    levar_a(enviada(solicitante), "APROVADA")

    assert _iguais(aprovador) == 3
    assert _iguais(indicado) == 1
    assert _iguais(auto) == 4
    assert _iguais(solicitante) == 0
    _iguais(admin)


def test_em_analise_por_tipo_conta_so_as_em_analise_com_o_nome_do_tipo(tipo_de_teste: TipoDeTeste) -> None:
    solicitante = com_cargo("sol")
    enviada(solicitante)
    enviada(solicitante)
    levar_a(enviada(solicitante), "RECUSADA")

    contagens = public.em_analise_por_tipo()

    assert [(c.tipo, c.nome, c.quantidade) for c in contagens] == [
        (tipo_de_teste.codigo, "Pedido de teste", 2)
    ]


def test_sem_solicitacao_em_analise_a_lista_e_vazia(tipo_de_teste: TipoDeTeste) -> None:
    assert public.em_analise_por_tipo() == []
    assert public.quantidade_na_fila(com_cargo("ninguem", APROVAR_TESTE).id) == 0
