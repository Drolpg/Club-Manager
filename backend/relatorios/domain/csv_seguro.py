"""Formatação dos valores em pt-BR e o escape contra injeção de fórmula no CSV (P23, CA-23).

Uma planilha executa como fórmula a célula de texto que começa com `=`, `+`, `-`, `@`, tabulação ou retorno.
Só as células de texto são escapadas; as numéricas saem como número e nunca passam pelo escape.
"""

from datetime import date
from decimal import Decimal

from relatorios.domain.documento import TipoDeColuna, Valor

_INICIOS_PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")


def escapar_celula(texto: str) -> str:
    return f"'{texto}" if texto.startswith(_INICIOS_PERIGOSOS) else texto


def _decimal(valor: Valor) -> Decimal:
    # Dinheiro nunca passa por ponto flutuante (RNF-11): um float aqui é erro de quem montou o documento.
    if not isinstance(valor, Decimal):
        raise TypeError(f"Dinheiro precisa ser Decimal, e veio {type(valor).__name__}.")
    return valor.quantize(Decimal("0.01"))


def _data(valor: Valor) -> str:
    if not isinstance(valor, date):
        raise TypeError(f"Data precisa ser date, e veio {type(valor).__name__}.")
    return valor.strftime("%d/%m/%Y")


def formatar_para_csv(valor: Valor, tipo: TipoDeColuna) -> str:
    """Vírgula decimal sem milhar, data `dd/mm/aaaa`, sim ou não; texto escapado; vazio para nada."""
    if valor is None:
        return ""
    if tipo == TipoDeColuna.DINHEIRO:
        return str(_decimal(valor)).replace(".", ",")
    if tipo == TipoDeColuna.DATA:
        return _data(valor)
    if tipo == TipoDeColuna.SIM_NAO:
        return "sim" if valor else "não"
    if tipo == TipoDeColuna.INTEIRO:
        return str(valor)
    return escapar_celula(str(valor))


def _reais(valor: Decimal) -> str:
    sinal = "-" if valor < 0 else ""
    inteiro, centavos = f"{abs(valor):.2f}".split(".")
    com_milhar = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {com_milhar},{centavos}"


def formatar_para_leitura(valor: Valor, tipo: TipoDeColuna) -> str:
    """Para o PDF: dinheiro em reais com milhar e sinal na frente, data `dd/mm/aaaa`; texto como veio."""
    if valor is None:
        return "—"
    if tipo == TipoDeColuna.DINHEIRO:
        return _reais(_decimal(valor))
    if tipo == TipoDeColuna.DATA:
        return _data(valor)
    if tipo == TipoDeColuna.SIM_NAO:
        return "sim" if valor else "não"
    return str(valor)
