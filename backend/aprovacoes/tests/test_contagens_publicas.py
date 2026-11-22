"""Contagens públicas para o dashboard (N14 da spec `relatorios/dashboard-e-lancamentos`; CA-08).

`quantidade_na_fila` conta a mesma consulta da fila de pendências, sem conferir quem pergunta (é de quem
chama); `em_analise_por_tipo` agrupa as solicitações em análise do clube.
"""

import pytest

from aprovacoes import demonstracao, public
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


def test_tipo_de_demonstracao_fora_do_registro_aparece_pelo_nome_legivel(tipo_de_teste: TipoDeTeste) -> None:
    """No desenvolvimento, o tipo de demonstração pode ter solicitações no banco sem estar registrado (a
    variável de demonstração desligada). O nome continua legível no dashboard e nas listas."""
    solicitante = com_cargo("sol")
    apoio.registrar_permissao_de_teste(demonstracao.PERMISSAO)
    try:
        public.registrar_tipo(
            codigo=demonstracao.TIPO,
            nome=demonstracao.NOME,
            permissao_de_aprovar=demonstracao.PERMISSAO,
            tem_valor=True,
            preparar=demonstracao.preparar,
            ao_mudar=demonstracao.ao_mudar,
        )
        enviada(solicitante, tipo=demonstracao.TIPO)
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste(demonstracao.TIPO)
        apoio.remover_permissao_de_teste(demonstracao.PERMISSAO)
    enviada(solicitante)

    nomes = {c.tipo: c.nome for c in public.em_analise_por_tipo()}

    assert nomes == {demonstracao.TIPO: "Pedido de demonstração", tipo_de_teste.codigo: "Pedido de teste"}
    admin = apoio.criar_admin("adm.nomes")
    assert {i.tipo_nome for i in consulta.listar(admin.id).itens} >= {"Pedido de demonstração"}
