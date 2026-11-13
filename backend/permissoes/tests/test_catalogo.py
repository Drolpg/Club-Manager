import pytest

from permissoes import catalogo
from permissoes.domain.resolucao import ACESSO_TOTAL


def test_catalogo_ja_traz_convites_e_acesso_total_com_descricao() -> None:
    por_codigo = {p.codigo: p for p in catalogo.listar()}

    assert {"convites.gerenciar", ACESSO_TOTAL} <= set(por_codigo)
    assert all(p.nome and p.descricao for p in por_codigo.values())


def test_registrar_acrescenta_uma_permissao_e_repetir_nao_duplica() -> None:
    try:
        catalogo.registrar_permissao(
            "teste.fazer", "Fazer teste", "Só para o teste.", fora_do_acesso_total=True
        )
        catalogo.registrar_permissao(
            "teste.fazer", "Fazer teste", "Só para o teste.", fora_do_acesso_total=True
        )

        encontrados = [p for p in catalogo.listar() if p.codigo == "teste.fazer"]
        assert len(encontrados) == 1
        assert catalogo.conhecida("teste.fazer")
        assert catalogo.mapa_para_resolucao()["teste.fazer"] is True
    finally:
        catalogo.remover_para_testes("teste.fazer")

    assert not catalogo.conhecida("teste.fazer")


@pytest.mark.parametrize("codigo", ["", "semponto", "Com.Maiuscula", "com espaco.x", "a.b.c.d e"])
def test_codigo_fora_do_formato_e_recusado(codigo: str) -> None:
    with pytest.raises(ValueError, match="recurso"):
        catalogo.registrar_permissao(codigo, "Nome", "Descrição.")


def test_registrar_o_mesmo_codigo_com_outra_definicao_e_erro_de_programacao() -> None:
    with pytest.raises(ValueError, match="já registrada"):
        catalogo.registrar_permissao("convites.gerenciar", "Outro nome", "Outra descrição.")
