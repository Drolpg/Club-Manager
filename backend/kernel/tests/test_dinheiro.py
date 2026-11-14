"""O value object `Dinheiro`: decimal com duas casas, não negativo, nunca ponto flutuante."""

from decimal import Decimal

import pytest

from kernel.dinheiro import Dinheiro


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (Decimal("10.5"), Decimal("10.50")),
        (Decimal("0"), Decimal("0.00")),
        (7, Decimal("7.00")),
        ("1234.56", Decimal("1234.56")),
        ("3.100", Decimal("3.10")),
    ],
)
def test_aceita_decimal_inteiro_e_texto_com_ate_duas_casas(
    entrada: Decimal | int | str, esperado: Decimal
) -> None:
    assert Dinheiro(entrada).quantia == esperado


@pytest.mark.parametrize("entrada", [10.5, 0.0, True])
def test_recusa_ponto_flutuante_e_booleano(entrada: object) -> None:
    with pytest.raises(TypeError):
        Dinheiro(entrada)  # type: ignore[arg-type]


@pytest.mark.parametrize("entrada", ["-0.01", -1, Decimal("-5")])
def test_recusa_negativo(entrada: Decimal | int | str) -> None:
    with pytest.raises(ValueError, match="negativo"):
        Dinheiro(entrada)


@pytest.mark.parametrize("entrada", ["1.005", Decimal("0.001")])
def test_recusa_mais_de_duas_casas_sem_arredondar(entrada: Decimal | str) -> None:
    with pytest.raises(ValueError, match="duas casas"):
        Dinheiro(entrada)


@pytest.mark.parametrize("entrada", ["abc", "", "NaN", "Infinity", Decimal("NaN")])
def test_recusa_texto_que_nao_e_numero_e_valores_nao_finitos(entrada: Decimal | str) -> None:
    with pytest.raises(ValueError, match="inválido"):
        Dinheiro(entrada)


def test_texto_sempre_com_duas_casas() -> None:
    assert str(Dinheiro(5)) == "5.00"
    assert str(Dinheiro("0.1")) == "0.10"


def test_compara_pelo_valor() -> None:
    assert Dinheiro("1.0") == Dinheiro(1)
    assert hash(Dinheiro("1.0")) == hash(Dinheiro(1))
    assert Dinheiro(1) < Dinheiro("1.01")
    assert Dinheiro("2") > Dinheiro("1.99")


def test_e_imutavel() -> None:
    dinheiro = Dinheiro(1)

    with pytest.raises(AttributeError):
        dinheiro.quantia = Decimal(2)  # type: ignore[misc]
