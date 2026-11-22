"""Totais do realizado, só leitura, para o dashboard, os relatórios e a visão do caixa (N1 a N8).

Cada valor entra no período pela data em que se tornou realizado (RN-026): `paga_em` da cobrança,
`decidido_em` da entrada sem devedor validada, `liquidada_em` da saída. O estorno entra pela data dele, com
sinal contrário, no lado do original (RN-027); o de devolução não entra, porque a devolução nunca foi entrada
realizada (D3).

O período é de datas locais, filtrado por intervalo de instantes no fuso do clube (D1). O número de consultas
não depende da quantidade de lançamentos (CA-20).
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, Min, OuterRef, Q, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from financeiro.domain.saidas import PRAZO_VENCIMENTO_PRESTACAO_DIAS, calcular_valor_realizado_saida
from financeiro.domain.transicoes import SituacaoCobranca, SituacaoEntrada, SituacaoSaida
from financeiro.models import AlvoEstorno, Cobranca, Entrada, Envio, Estorno, Saida, TipoEntrada

_ZERO = Decimal("0.00")
_DINHEIRO = DecimalField(max_digits=14, decimal_places=2)
_ENTRADA_REALIZADA = (SituacaoEntrada.VALIDADA.value, SituacaoEntrada.ESTORNADA.value)


@dataclass(frozen=True)
class TotaisDoPeriodo:
    """N1, N2 e os estornos de cada lado; `entradas`, `saidas` e `resultado` são N5, N6 e N7."""

    entradas_realizadas: Decimal
    estornos_de_entrada: Decimal
    saidas_realizadas: Decimal
    estornos_de_saida: Decimal

    @property
    def entradas(self) -> Decimal:
        return self.entradas_realizadas - self.estornos_de_entrada

    @property
    def saidas(self) -> Decimal:
        return self.saidas_realizadas - self.estornos_de_saida

    @property
    def resultado(self) -> Decimal:
        return self.entradas - self.saidas


def _instante(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time.min))


def _no_intervalo(campo: str, de: date | None, ate: date) -> Q:
    """`[de 00h00, ate + 1 dia 00h00)`, no fuso do clube; sem `de`, desde o começo."""
    filtro = Q(**{f"{campo}__lt": _instante(ate + timedelta(days=1))})
    if de is not None:
        filtro &= Q(**{f"{campo}__gte": _instante(de)})
    return filtro


def _soma(qs: QuerySet[Any], campo: str = "valor") -> Decimal:
    total: Decimal | None = qs.aggregate(total=Sum(campo))["total"]
    return total if total is not None else _ZERO


def _entradas_realizadas(de: date | None, ate: date) -> Decimal:
    cobrancas = _soma(
        Cobranca.objects.filter(paga_em__isnull=False).filter(_no_intervalo("paga_em", de, ate))
    )
    sem_devedor = Entrada.objects.filter(
        tipo=TipoEntrada.SEM_DEVEDOR, situacao__in=_ENTRADA_REALIZADA
    ).filter(_no_intervalo("decidido_em", de, ate))
    return cobrancas + _soma(sem_devedor)


def _estornos(de: date | None, ate: date, lado: Q) -> Decimal:
    return _soma(Estorno.objects.filter(lado).filter(_no_intervalo("registrado_em", de, ate)))


_ESTORNO_DE_ENTRADA = Q(alvo_tipo=AlvoEstorno.COBRANCA) | Q(
    alvo_tipo=AlvoEstorno.ENTRADA, entrada__tipo=TipoEntrada.SEM_DEVEDOR
)
_ESTORNO_DE_SAIDA = Q(alvo_tipo=AlvoEstorno.SAIDA)


def _com_realizado(qs: QuerySet[Saida]) -> QuerySet[Any]:
    """Anota em cada saída o enviado e o devolvido que contam no realizado (N2, D4).

    As subconsultas aplicam a regra de `realizado_da_saida`: devolução validada, ou estornada depois da
    liquidação.
    """
    enviado = Envio.objects.filter(saida=OuterRef("pk")).values("saida").annotate(t=Sum("valor")).values("t")
    devolvido = (
        Entrada.objects.filter(saida=OuterRef("pk"), tipo=TipoEntrada.DEVOLUCAO)
        .filter(
            Q(situacao=SituacaoEntrada.VALIDADA)
            | Q(situacao=SituacaoEntrada.ESTORNADA, estorno__registrado_em__gt=OuterRef("liquidada_em"))
        )
        .values("saida")
        .annotate(t=Sum("valor"))
        .values("t")
    )
    return qs.annotate(
        r_enviado=Coalesce(Subquery(enviado, output_field=_DINHEIRO), Value(_ZERO)),
        r_devolvido=Coalesce(Subquery(devolvido, output_field=_DINHEIRO), Value(_ZERO)),
    )


def _saidas_realizadas(de: date | None, ate: date) -> Decimal:
    """Soma o realizado de cada saída liquidada no período, numa consulta, com o mínimo zero de N2."""
    linhas = _com_realizado(
        Saida.objects.filter(liquidada_em__isnull=False).filter(_no_intervalo("liquidada_em", de, ate))
    ).values_list("r_enviado", "r_devolvido")
    return sum((calcular_valor_realizado_saida(env, dev) for env, dev in linhas), _ZERO)


def realizado_por_saida(saida_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """O realizado de cada saída liquidada pedida, numa consulta (para a lista de lançamentos)."""
    if not saida_ids:
        return {}
    linhas = _com_realizado(Saida.objects.filter(pk__in=saida_ids, liquidada_em__isnull=False)).values_list(
        "pk", "r_enviado", "r_devolvido"
    )
    return {pk: calcular_valor_realizado_saida(env, dev) for pk, env, dev in linhas}


def totais_do_periodo(de: date | None, ate: date) -> TotaisDoPeriodo:
    """N1 a N7 do período `[de, ate]`, em datas locais; sem `de`, desde o primeiro lançamento."""
    return TotaisDoPeriodo(
        entradas_realizadas=_entradas_realizadas(de, ate),
        estornos_de_entrada=_estornos(de, ate, _ESTORNO_DE_ENTRADA),
        saidas_realizadas=_saidas_realizadas(de, ate),
        estornos_de_saida=_estornos(de, ate, _ESTORNO_DE_SAIDA),
    )


def saldo_acumulado(ate: date) -> Decimal:
    """N8: a soma dos resultados desde o primeiro lançamento até o fim do dia `ate`."""
    return totais_do_periodo(None, ate).resultado


def primeira_data_de_realizacao() -> date | None:
    """A data local do primeiro lançamento realizado, de qualquer tipo; `None` sem nenhum (H2)."""
    instantes = [
        Cobranca.objects.aggregate(m=Min("paga_em"))["m"],
        Entrada.objects.filter(tipo=TipoEntrada.SEM_DEVEDOR, situacao__in=_ENTRADA_REALIZADA).aggregate(
            m=Min("decidido_em")
        )["m"],
        Saida.objects.aggregate(m=Min("liquidada_em"))["m"],
        Estorno.objects.aggregate(m=Min("registrado_em"))["m"],
    ]
    presentes = [i for i in instantes if i is not None]
    return timezone.localdate(min(presentes)) if presentes else None


# Pendências e resumos de hoje (N11 a N13, N15 e "minhas cobranças") ------------------------------------


@dataclass(frozen=True)
class Resumo:
    quantidade: int
    total: Decimal


@dataclass(frozen=True)
class ResumoDaInadimplencia:
    cobrancas: int
    devedores: int
    total: Decimal


@dataclass(frozen=True)
class PendenciasDeValidacao:
    pagamentos: Resumo
    entradas: Resumo


@dataclass(frozen=True)
class PrestacoesPendentes:
    aguardando: int
    em_atraso: int
    em_conferencia: int


@dataclass(frozen=True)
class ProximaCobranca:
    id: uuid.UUID
    descricao: str
    valor: Decimal
    vencimento: date


@dataclass(frozen=True)
class ResumoDoDevedor:
    em_aberto: Resumo
    atrasadas: Resumo
    em_validacao: Resumo
    proxima: ProximaCobranca | None


def _resumo(qs: QuerySet[Any]) -> Resumo:
    agregado = qs.aggregate(quantidade=Count("id"), total=Sum("valor"))
    return Resumo(quantidade=agregado["quantidade"], total=agregado["total"] or _ZERO)


_A_RECEBER = (
    SituacaoCobranca.ABERTA.value,
    SituacaoCobranca.ATRASADA.value,
    SituacaoCobranca.EM_VALIDACAO.value,
)


def a_receber(de: date, ate: date) -> Resumo:
    """N11: cobranças com vencimento em `[de, ate]` ainda não pagas nem encerradas."""
    return _resumo(Cobranca.objects.filter(vencimento__gte=de, vencimento__lte=ate, situacao__in=_A_RECEBER))


def inadimplentes() -> QuerySet[Cobranca]:
    """N12: atrasadas sem questionamento aberto. A mesma regra de `consulta.listar(inadimplentes=True)`."""
    return Cobranca.objects.filter(situacao=SituacaoCobranca.ATRASADA.value).exclude(
        questionamentos__situacao="ABERTO"
    )


def resumo_da_inadimplencia() -> ResumoDaInadimplencia:
    agregado = inadimplentes().aggregate(
        cobrancas=Count("id", distinct=True), devedores=Count("devedor_id", distinct=True), total=Sum("valor")
    )
    return ResumoDaInadimplencia(
        cobrancas=agregado["cobrancas"], devedores=agregado["devedores"], total=agregado["total"] or _ZERO
    )


def pendencias_de_validacao() -> PendenciasDeValidacao:
    """N13: pagamentos de cobrança em validação, e entradas (sem devedor e devoluções) em validação."""
    return PendenciasDeValidacao(
        pagamentos=_resumo(Cobranca.objects.filter(situacao=SituacaoCobranca.EM_VALIDACAO.value)),
        entradas=_resumo(Entrada.objects.filter(situacao=SituacaoEntrada.EM_VALIDACAO.value)),
    )


def prestacoes_pendentes(hoje: date) -> PrestacoesPendentes:
    """N15: aguardando prestação, das quais em atraso (a regra de `prestacao_em_atraso`), e em conferência."""
    aguardando = Saida.objects.filter(situacao=SituacaoSaida.RECURSO_ENVIADO.value)
    limite = hoje - timedelta(days=PRAZO_VENCIMENTO_PRESTACAO_DIAS)
    return PrestacoesPendentes(
        aguardando=aguardando.count(),
        em_atraso=aguardando.filter(primeiro_envio_em__isnull=False)
        .filter(_no_intervalo("primeiro_envio_em", None, limite))
        .count(),
        em_conferencia=Saida.objects.filter(situacao=SituacaoSaida.EM_CONFERENCIA.value).count(),
    )


def resumo_do_devedor(usuario_id: uuid.UUID, hoje: date) -> ResumoDoDevedor:
    """As cobranças de um devedor: em aberto (a vencer), atrasadas, em validação e a próxima a vencer."""
    do_devedor = Cobranca.objects.filter(devedor_id=usuario_id)
    proxima = (
        do_devedor.filter(situacao=SituacaoCobranca.ABERTA.value, vencimento__gte=hoje)
        .order_by("vencimento", "id")
        .values("id", "descricao", "valor", "vencimento")
        .first()
    )
    return ResumoDoDevedor(
        em_aberto=_resumo(do_devedor.filter(situacao=SituacaoCobranca.ABERTA.value)),
        atrasadas=_resumo(do_devedor.filter(situacao=SituacaoCobranca.ATRASADA.value)),
        em_validacao=_resumo(do_devedor.filter(situacao=SituacaoCobranca.EM_VALIDACAO.value)),
        proxima=ProximaCobranca(**proxima) if proxima else None,
    )
