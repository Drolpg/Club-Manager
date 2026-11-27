"""A inadimplência por devedor (RF-107, N12), sem contato nem texto livre."""

from collections import defaultdict
from decimal import Decimal
from typing import Any

from financeiro import public as financeiro
from relatorios.domain.documento import Coluna, Documento, ItemDoResumo, Tabela, TipoDeColuna
from relatorios.relatorios import comum
from relatorios.tipos import Contexto

T = TipoDeColuna
_ZERO = Decimal("0.00")


_COLUNAS_DA_INADIMPLENCIA = (
    Coluna("Devedor", T.TEXTO),
    Coluna("Descrição", T.TEXTO),
    Coluna("Categoria", T.TEXTO),
    Coluna("Vencimento", T.DATA),
    Coluna("Valor", T.DINHEIRO),
    Coluna("Dias de atraso", T.INTEIRO),
    Coluna("Convocado", T.SIM_NAO),
    Coluna("Justificou", T.SIM_NAO),
)


def inadimplencia(_parametros: dict[str, Any], contexto: Contexto) -> list[Documento]:
    """Por devedor (N12), sem e-mail, telefone nem texto livre (Q7-A)."""
    cobrancas = sorted(
        financeiro.inadimplencia_detalhada(contexto.hoje), key=lambda c: (c.devedor, c.vencimento)
    )
    por_devedor: dict[str, list[Decimal]] = defaultdict(list)
    for cobranca in cobrancas:
        por_devedor[cobranca.devedor].append(cobranca.valor)
    total = sum((c.valor for c in cobrancas), _ZERO)
    return [
        Documento(
            titulo="Inadimplência",
            parametros=f"Na data de {comum.data(contexto.hoje)}",
            resumo=(
                ItemDoResumo("Cobranças", len(cobrancas), T.INTEIRO),
                ItemDoResumo("Devedores", len(por_devedor), T.INTEIRO),
                ItemDoResumo("Total", total, T.DINHEIRO),
            ),
            tabelas=(
                Tabela(
                    "Cobranças inadimplentes",
                    _COLUNAS_DA_INADIMPLENCIA,
                    tuple(
                        (
                            c.devedor,
                            c.descricao,
                            c.categoria,
                            c.vencimento,
                            c.valor,
                            c.dias_de_atraso,
                            c.convocado,
                            c.justificou,
                        )
                        for c in cobrancas
                    ),
                ),
                Tabela(
                    "Total por devedor",
                    (Coluna("Devedor", T.TEXTO), Coluna("Cobranças", T.INTEIRO), Coluna("Total", T.DINHEIRO)),
                    tuple(
                        (devedor, len(valores), sum(valores, _ZERO))
                        for devedor, valores in por_devedor.items()
                    ),
                ),
            ),
        )
    ]
