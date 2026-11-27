"""O balancete simplificado por categoria e por setor (RF-106)."""

from decimal import Decimal
from typing import Any

from financeiro import public as financeiro
from relatorios.domain.documento import Coluna, Documento, Tabela, TipoDeColuna
from relatorios.relatorios import comum
from relatorios.tipos import Contexto

T = TipoDeColuna
_ZERO = Decimal("0.00")


def _por(nome: str, linhas: list[financeiro.LinhaDoBalancete]) -> Tabela:
    colunas = (
        Coluna(nome, T.TEXTO),
        Coluna("Realizado", T.DINHEIRO),
        Coluna("Estornos", T.DINHEIRO),
        Coluna("Líquido", T.DINHEIRO),
    )
    return Tabela("", colunas, tuple((li.nome, li.realizado, li.estornos, li.liquido) for li in linhas))


def balancete(parametros: dict[str, Any], _contexto: Contexto) -> list[Documento]:
    de, ate = comum.periodo(parametros)
    dados = financeiro.balancete(de, ate)
    entradas, saidas, setores = (
        _por("Categoria", dados.entradas),
        _por("Categoria", dados.saidas),
        _por("Setor", dados.saidas_por_setor),
    )
    return [
        Documento(
            titulo="Balancete",
            parametros=comum.texto_do_periodo(de, ate),
            resumo=comum.saldos(de, ate, dados.totais),
            tabelas=(
                Tabela("Entradas por categoria", entradas.colunas, entradas.linhas),
                Tabela("Saídas por categoria", saidas.colunas, saidas.linhas),
                Tabela("Saídas por setor", setores.colunas, setores.linhas),
            ),
        )
    ]
