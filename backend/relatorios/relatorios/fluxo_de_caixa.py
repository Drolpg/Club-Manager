"""O fluxo de caixa: previsto pelo vencimento e realizado mês a mês (RF-110)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from financeiro import public as financeiro
from relatorios.domain.documento import Coluna, Documento, ItemDoResumo, Tabela, TipoDeColuna
from relatorios.relatorios import comum
from relatorios.tipos import Contexto

T = TipoDeColuna
_ZERO = Decimal("0.00")


def _fim_do_mes(inicio: date) -> date:
    return (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def fluxo_de_caixa(parametros: dict[str, Any], contexto: Contexto) -> list[Documento]:
    """O previsto pelo vencimento (só as cobranças já geradas, P28) e o realizado mês a mês (N5 a N8)."""
    de, ate = comum.periodo(parametros)
    previstos = financeiro.fluxo_previsto(de, ate, hoje=contexto.hoje)
    realizados = []
    for mes in previstos:
        fim = min(_fim_do_mes(mes.mes), ate)
        totais = financeiro.totais_do_periodo(max(mes.mes, de), fim)
        realizados.append((mes.mes, totais, financeiro.saldo_acumulado(fim)))
    rotulo = "%m/%Y"
    return [
        Documento(
            titulo="Fluxo de caixa",
            parametros=f"De {de.strftime(rotulo)} a {ate.strftime(rotulo)}",
            resumo=(
                ItemDoResumo("Previsto", sum((m.previsto for m in previstos), _ZERO), T.DINHEIRO),
                ItemDoResumo("Recebido", sum((m.recebido for m in previstos), _ZERO), T.DINHEIRO),
                ItemDoResumo("Entradas", sum((t.entradas for _, t, _ in realizados), _ZERO), T.DINHEIRO),
                ItemDoResumo("Saídas", sum((t.saidas for _, t, _ in realizados), _ZERO), T.DINHEIRO),
                ItemDoResumo("Resultado", sum((t.resultado for _, t, _ in realizados), _ZERO), T.DINHEIRO),
                ItemDoResumo("Comprometido hoje", financeiro.visao_do_caixa().total_comprometido, T.DINHEIRO),
            ),
            tabelas=(
                Tabela(
                    "Previsto pelo vencimento",
                    (
                        Coluna("Mês", T.TEXTO),
                        Coluna("Previsto", T.DINHEIRO),
                        Coluna("Recebido", T.DINHEIRO),
                        Coluna("Em aberto ou em validação", T.DINHEIRO),
                        Coluna("Questionadas", T.DINHEIRO),
                        Coluna("Inadimplentes", T.DINHEIRO),
                    ),
                    tuple(
                        (
                            m.mes.strftime(rotulo),
                            m.previsto,
                            m.recebido,
                            m.em_aberto,
                            m.questionadas,
                            m.inadimplentes,
                        )
                        for m in previstos
                    ),
                ),
                Tabela(
                    "Realizado",
                    (
                        Coluna("Mês", T.TEXTO),
                        Coluna("Entradas", T.DINHEIRO),
                        Coluna("Saídas", T.DINHEIRO),
                        Coluna("Resultado", T.DINHEIRO),
                        Coluna("Saldo no fim do mês", T.DINHEIRO),
                    ),
                    tuple(
                        (inicio.strftime(rotulo), t.entradas, t.saidas, t.resultado, saldo)
                        for inicio, t, saldo in realizados
                    ),
                ),
            ),
        )
    ]
