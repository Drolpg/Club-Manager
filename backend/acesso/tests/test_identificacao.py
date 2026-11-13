import pytest

from acesso.domain.identificacao import (
    nome_de_usuario_valido,
    normalizar_email,
    normalizar_telefone,
    telefone_valido,
)


@pytest.mark.parametrize("nome", ["ana", "Joao.Silva", "j_p-2", "a" * 30])
def test_nome_de_usuario_valido(nome: str) -> None:
    assert nome_de_usuario_valido(nome)


@pytest.mark.parametrize("nome", ["", "ab", "a" * 31, "joão", "ana maria", "ana@clube", "ana/..", "ana\n"])
def test_nome_de_usuario_invalido(nome: str) -> None:
    assert not nome_de_usuario_valido(nome)


def test_normalizar_email_tira_espacos_e_maiusculas() -> None:
    assert normalizar_email("  Ana.Silva@Exemplo.COM ") == "ana.silva@exemplo.com"


def test_normalizar_telefone_mantem_so_digitos_e_o_mais_inicial() -> None:
    assert normalizar_telefone("+55 (11) 98765-4321") == "+5511987654321"
    assert normalizar_telefone("(11) 98765-4321") == "11987654321"


@pytest.mark.parametrize("telefone", ["11987654321", "+5511987654321", "12345678"])
def test_telefone_valido(telefone: str) -> None:
    assert telefone_valido(telefone)


@pytest.mark.parametrize("telefone", ["", "1234567", "1" * 16, "11-9876", "abc12345678", "55+11987654321"])
def test_telefone_invalido(telefone: str) -> None:
    assert not telefone_valido(telefone)
