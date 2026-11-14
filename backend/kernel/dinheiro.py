"""O value object `Dinheiro`, usado por `aprovacoes`, `financeiro` e `eventos` (technical-spec do motor).

Decimal com duas casas, não negativo. Recusa ponto flutuante e não arredonda: um valor com mais de duas casas
é erro de quem o montou, e não algo a corrigir em silêncio. No banco, `DecimalField(max_digits=12,
decimal_places=2)`; na API, texto.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_CENTAVO = Decimal("0.01")


def _como_decimal(valor: object) -> Decimal:
    # `bool` é subclasse de `int` e `float` perde centavos: os dois são recusados antes de virar Decimal.
    if isinstance(valor, bool | float) or not isinstance(valor, Decimal | int | str):
        raise TypeError(f"Dinheiro aceita Decimal, int ou texto, não {type(valor).__name__}.")
    try:
        decimal = Decimal(valor)
    except InvalidOperation:
        raise ValueError(f"Valor em dinheiro inválido: {valor!r}.") from None
    if not decimal.is_finite():
        raise ValueError(f"Valor em dinheiro inválido: {valor!r}.")
    return decimal


@dataclass(frozen=True, order=True, init=False)
class Dinheiro:
    quantia: Decimal

    def __init__(self, valor: Decimal | int | str) -> None:
        decimal = _como_decimal(valor)
        if decimal < 0:
            raise ValueError("Valor em dinheiro não pode ser negativo.")
        com_centavos = decimal.quantize(_CENTAVO)
        if com_centavos != decimal:
            raise ValueError("Valor em dinheiro tem no máximo duas casas decimais.")
        object.__setattr__(self, "quantia", com_centavos)

    def __str__(self) -> str:
        return f"{self.quantia:.2f}"
