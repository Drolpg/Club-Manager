"""Registro dos tipos de notificação: mesmo padrão do catálogo de permissões (AD-014)."""

import pytest

from notificacoes import public, tipos

CODIGO = "teste.registro"


@pytest.fixture(autouse=True)
def _limpar() -> None:
    tipos.remover_para_testes(CODIGO)


@pytest.mark.parametrize("invalido", ["semponto", "Maiusculo.fato", "modulo.", ".fato", "modulo.fato-x", ""])
def test_codigo_fora_do_formato_modulo_ponto_fato_e_recusado(invalido: str) -> None:
    with pytest.raises(ValueError, match="inválido"):
        tipos.registrar_tipo(invalido, pede_acao=False, descricao="x")


def test_registrar_e_consultar() -> None:
    tipos.registrar_tipo(CODIGO, pede_acao=True, descricao="Descrição")
    try:
        tipo = tipos.obter(CODIGO)

        assert (tipo.codigo, tipo.pede_acao, tipo.descricao) == (CODIGO, True, "Descrição")
        assert tipos.conhecido(CODIGO)
    finally:
        tipos.remover_para_testes(CODIGO)


def test_repetir_a_mesma_definicao_nao_duplica() -> None:
    tipos.registrar_tipo(CODIGO, pede_acao=False, descricao="Igual")
    tipos.registrar_tipo(CODIGO, pede_acao=False, descricao="Igual")
    try:
        assert [t.codigo for t in tipos.listar()].count(CODIGO) == 1
    finally:
        tipos.remover_para_testes(CODIGO)


def test_redefinir_com_outra_definicao_e_erro() -> None:
    tipos.registrar_tipo(CODIGO, pede_acao=False, descricao="Original")
    try:
        with pytest.raises(ValueError, match="já registrado"):
            tipos.registrar_tipo(CODIGO, pede_acao=True, descricao="Original")
        assert tipos.obter(CODIGO).pede_acao is False
    finally:
        tipos.remover_para_testes(CODIGO)


def test_tipo_desconhecido_e_erro_de_programacao() -> None:
    assert not tipos.conhecido("nao.existe")
    with pytest.raises(ValueError, match="desconhecido"):
        tipos.obter("nao.existe")


def test_a_api_publica_expoe_registrar_tipo() -> None:
    public.registrar_tipo(CODIGO, pede_acao=False, descricao="Pela API pública")
    try:
        assert tipos.obter(CODIGO).descricao == "Pela API pública"
    finally:
        tipos.remover_para_testes(CODIGO)
