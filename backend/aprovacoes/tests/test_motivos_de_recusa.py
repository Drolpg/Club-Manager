"""O motivo da recusa, para o relatório de eventos (spec `relatorios/relatorios-pdf-e-csv`, adendo 1; P27).

Só leitura: o motivo do catálogo aplicado na decisão de recusa da versão vigente. Sem quem decidiu e sem o
texto livre da decisão.
"""

import pytest

from aprovacoes import public
from aprovacoes.tests.conftest import TipoDeTeste, enviada, levar_a
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def solicitante(tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario) -> Usuario:
    return diretor_com_cargo


def test_solicitacao_recusada_devolve_o_motivo_do_catalogo(
    tipo_de_teste: TipoDeTeste, solicitante: Usuario
) -> None:
    recusada = levar_a(enviada(solicitante), "RECUSADA")

    assert public.motivos_de_recusa([recusada.id]) == {recusada.id: "Motivo do cenário"}


@pytest.mark.parametrize("situacao", ["EM_ANALISE", "CONTESTADA", "APROVADA", "RETIRADA"])
def test_solicitacao_que_nao_esta_recusada_nao_tem_motivo(
    tipo_de_teste: TipoDeTeste, solicitante: Usuario, situacao: str
) -> None:
    solicitacao = levar_a(enviada(solicitante), situacao)

    assert public.motivos_de_recusa([solicitacao.id]) == {}


def test_varias_de_uma_vez_e_lista_vazia(tipo_de_teste: TipoDeTeste, solicitante: Usuario) -> None:
    recusada = levar_a(enviada(solicitante), "RECUSADA")
    aprovada = levar_a(enviada(solicitante), "APROVADA")

    assert public.motivos_de_recusa([recusada.id, aprovada.id]) == {recusada.id: "Motivo do cenário"}
    assert public.motivos_de_recusa([]) == {}
