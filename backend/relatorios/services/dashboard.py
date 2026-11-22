"""O dashboard (RF-102, RF-103): só leitura, composto das consultas públicas dos módulos donos.

Quem lê os dados de gestão vê o completo; o diretor sem cargo, o básico, montado sem chamar nenhuma consulta
do clube (D8). Os números seguem as definições N1 a N15 da spec `relatorios/dashboard-e-lancamentos` e são
calculados pelos módulos donos; aqui só se compõe. Nada é guardado.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.utils import timezone

from acesso import public as acesso
from aprovacoes import public as aprovacoes
from comunicacao import public as comunicacao
from eventos import public as eventos
from financeiro import public as financeiro
from notificacoes import public as notificacoes
from permissoes import public as permissoes
from relatorios.erros import erro, mes_invalido

_FORMATO_DO_MES = re.compile(r"(\d{4})-(\d{2})")


@dataclass(frozen=True)
class DoMes:
    entradas: Decimal
    saidas: Decimal
    resultado: Decimal
    saldo_acumulado: Decimal
    a_receber: financeiro.Resumo


@dataclass(frozen=True)
class PendenciasDeAprovacao:
    minha_fila: int
    por_tipo: list[aprovacoes.EmAnalisePorTipo]


@dataclass(frozen=True)
class Hoje:
    data: date
    comprometido: Decimal
    saldo_livre: Decimal
    pendencias_de_validacao: financeiro.PendenciasDeValidacao
    pendencias_de_aprovacao: PendenciasDeAprovacao
    prestacoes_pendentes: financeiro.PrestacoesPendentes
    inadimplencia: financeiro.ResumoDaInadimplencia


@dataclass(frozen=True)
class DashboardCompleto:
    mes: date
    primeiro_mes: date
    ultimo_mes: date
    do_mes: DoMes
    hoje: Hoje
    proximos_eventos: list[eventos.ProximoEvento]
    ultimos_comunicados: list[comunicacao.ComunicadoRecente]
    minhas_cobrancas: financeiro.ResumoDoDevedor


@dataclass(frozen=True)
class DashboardBasico:
    minhas_cobrancas: financeiro.ResumoDoDevedor
    notificacoes_nao_lidas: int


def _primeiro_dia(dia: date) -> date:
    return dia.replace(day=1)


def mes_pedido(texto: str | None, hoje: date) -> date:
    """O primeiro dia do mês pedido (`AAAA-MM`); sem texto, o corrente. Mês futuro ou inválido: 400."""
    if not texto:
        return _primeiro_dia(hoje)
    encontrado = _FORMATO_DO_MES.fullmatch(texto)
    if encontrado is None:
        raise mes_invalido("Use o formato AAAA-MM.")
    ano, mes = int(encontrado.group(1)), int(encontrado.group(2))
    try:
        inicio, _ = financeiro.limites_do_mes(ano, mes)
    except ValueError:
        raise mes_invalido("Use um mês de 01 a 12.") from None
    if inicio > _primeiro_dia(hoje):
        raise mes_invalido("Escolha o mês corrente ou um anterior.")
    return inicio


def _do_mes(inicio: date, hoje: date) -> DoMes:
    _, fim = financeiro.limites_do_mes(inicio.year, inicio.month)
    totais = financeiro.totais_do_periodo(inicio, fim)
    return DoMes(
        entradas=totais.entradas,
        saidas=totais.saidas,
        resultado=totais.resultado,
        saldo_acumulado=financeiro.saldo_acumulado(min(fim, hoje)),
        a_receber=financeiro.a_receber(inicio, fim),
    )


def _hoje(ator_id: uuid.UUID, hoje: date) -> Hoje:
    caixa = financeiro.visao_do_caixa()
    saldo = financeiro.saldo_acumulado(hoje)
    return Hoje(
        data=hoje,
        comprometido=caixa.total_comprometido,
        saldo_livre=saldo - caixa.total_comprometido,
        pendencias_de_validacao=financeiro.pendencias_de_validacao(),
        pendencias_de_aprovacao=PendenciasDeAprovacao(
            minha_fila=aprovacoes.quantidade_na_fila(ator_id), por_tipo=aprovacoes.em_analise_por_tipo()
        ),
        prestacoes_pendentes=financeiro.prestacoes_pendentes(hoje),
        inadimplencia=financeiro.resumo_da_inadimplencia(),
    )


def dashboard(ator_id: uuid.UUID, mes: str | None = None) -> DashboardCompleto | DashboardBasico:
    """O completo para quem lê os dados de gestão; o básico para o ativo sem cargo; 403 para os demais."""
    ator = acesso.usuario_por_id(ator_id)
    if ator is None or not ator.ativo:
        raise erro("PERMISSION_DENIED")
    hoje = timezone.localdate()
    minhas = financeiro.resumo_do_devedor(ator_id, hoje)
    if not permissoes.le_gestao(ator_id):
        return DashboardBasico(
            minhas_cobrancas=minhas, notificacoes_nao_lidas=notificacoes.resumo_da_caixa(ator_id).nao_lidas
        )
    inicio = mes_pedido(mes, hoje)
    primeira = financeiro.primeira_data_de_realizacao()
    return DashboardCompleto(
        mes=inicio,
        primeiro_mes=_primeiro_dia(min(primeira, hoje)) if primeira else _primeiro_dia(hoje),
        ultimo_mes=_primeiro_dia(hoje),
        do_mes=_do_mes(inicio, hoje),
        hoje=_hoje(ator_id, hoje),
        proximos_eventos=eventos.proximos_eventos(hoje),
        ultimos_comunicados=comunicacao.ultimos_comunicados(),
        minhas_cobrancas=minhas,
    )
