"""O relatório de eventos (RF-108): os eventos com data no período, com o orçamento aprovado, o realizado da
saída ligada (N2), as presenças e o motivo de recusa ou de cancelamento (P27).

`relatorios` junta as duas consultas, de `eventos` e do `financeiro`; nenhum dos dois chama o outro (D7).
"""

from decimal import Decimal
from typing import Any

from django.utils import timezone

from eventos import public as eventos
from financeiro import public as financeiro
from relatorios.domain.documento import Coluna, Documento, ItemDoResumo, Tabela, TipoDeColuna
from relatorios.relatorios import comum
from relatorios.tipos import Contexto

T = TipoDeColuna
_ZERO = Decimal("0.00")
_COLUNAS = (
    Coluna("Título", T.TEXTO),
    Coluna("Categoria", T.TEXTO),
    Coluna("Data", T.DATA),
    Coluna("Local", T.TEXTO),
    Coluna("Situação", T.TEXTO),
    Coluna("Proponente", T.TEXTO),
    Coluna("Envolve custo", T.SIM_NAO),
    Coluna("Orçamento aprovado", T.DINHEIRO),
    Coluna("Realizado", T.DINHEIRO),
    Coluna("Vou", T.INTEIRO),
    Coluna("Não vou", T.INTEIRO),
    Coluna("Motivo", T.TEXTO),
)


def eventos_do_periodo(parametros: dict[str, Any], _contexto: Contexto) -> list[Documento]:
    de, ate = comum.periodo(parametros)
    itens = eventos.eventos_do_periodo(de, ate)
    orcamentos = financeiro.orcamentos_de_eventos([item.id for item in itens])
    linhas = []
    for item in itens:
        orcamento = orcamentos.get(item.id)
        linhas.append(
            (
                item.titulo,
                item.categoria,
                timezone.localdate(item.inicio),
                item.local,
                comum.legivel(item.situacao, comum.SITUACOES_DE_EVENTO),
                item.proponente,
                item.envolve_custo,
                orcamento.aprovado if orcamento else None,
                orcamento.realizado if orcamento else None,
                item.vou,
                item.nao_vou,
                item.motivo,
            )
        )
    aprovado = sum((o.aprovado for o in orcamentos.values()), _ZERO)
    realizado = sum((o.realizado for o in orcamentos.values() if o.realizado is not None), _ZERO)
    return [
        Documento(
            titulo="Eventos",
            parametros=comum.texto_do_periodo(de, ate),
            resumo=(
                ItemDoResumo("Eventos", len(itens), T.INTEIRO),
                ItemDoResumo("Orçamento aprovado", aprovado, T.DINHEIRO),
                ItemDoResumo("Realizado", realizado, T.DINHEIRO),
            ),
            tabelas=(Tabela("Eventos", _COLUNAS, tuple(linhas)),),
        )
    ]
