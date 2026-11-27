"""O extrato (RF-105): cada lançamento realizado no período, com os saldos (N1 a N8)."""

from decimal import Decimal
from typing import Any

from financeiro import public as financeiro
from relatorios.domain.documento import Coluna, Documento, Tabela, TipoDeColuna
from relatorios.relatorios import comum
from relatorios.tipos import Contexto

T = TipoDeColuna
_ZERO = Decimal("0.00")
_TIPOS_DE_LANCAMENTO = {"COBRANCA": "Cobrança", "ENTRADA": "Entrada", "SAIDA": "Saída", "ESTORNO": "Estorno"}


_COLUNAS_DO_EXTRATO = (
    Coluna("Realizado em", T.DATA),
    Coluna("Data do fato", T.DATA),
    Coluna("Tipo", T.TEXTO),
    Coluna("Categoria", T.TEXTO),
    Coluna("Descrição", T.TEXTO),
    Coluna("Contraparte", T.TEXTO),
    Coluna("Valor", T.DINHEIRO),
)


def _efeito_no_saldo(linha: financeiro.LancamentoRealizado) -> Decimal:
    """Entrada soma e saída subtrai; o estorno já vem com o sinal contrário no lado do original."""
    return linha.valor if linha.lado == "ENTRADA" else -linha.valor


def extrato(parametros: dict[str, Any], _contexto: Contexto) -> list[Documento]:
    de, ate = comum.periodo(parametros)
    linhas = tuple(
        (
            linha.realizado_em,
            linha.data_do_fato,
            _TIPOS_DE_LANCAMENTO.get(linha.tipo, linha.tipo),
            linha.categoria,
            linha.descricao,
            linha.contraparte,
            _efeito_no_saldo(linha),
        )
        for linha in financeiro.lancamentos_realizados(de, ate)
    )
    return [
        Documento(
            titulo="Extrato",
            parametros=comum.texto_do_periodo(de, ate),
            resumo=comum.saldos(de, ate, financeiro.totais_do_periodo(de, ate)),
            tabelas=(Tabela("Lançamentos", _COLUNAS_DO_EXTRATO, linhas),),
        )
    ]
