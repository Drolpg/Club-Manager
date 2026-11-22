"""Totais do realizado, só leitura, para o dashboard, os relatórios e a visão do caixa (N1 a N8).

Cada valor entra no período pela data em que se tornou realizado (RN-026): `paga_em` da cobrança,
`decidido_em` da entrada sem devedor validada, `liquidada_em` da saída. O estorno entra pela data dele, com
sinal contrário, no lado do original (RN-027); o de devolução não entra, porque a devolução nunca foi entrada
realizada (D3).

O período é de datas locais, filtrado por intervalo de instantes no fuso do clube (D1). O número de consultas
não depende da quantidade de lançamentos (CA-20).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import DecimalField, Min, OuterRef, Q, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from financeiro.domain.saidas import calcular_valor_realizado_saida
from financeiro.domain.transicoes import SituacaoEntrada
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


def _saidas_realizadas(de: date | None, ate: date) -> Decimal:
    """Soma o realizado de cada saída liquidada no período, numa consulta (N2, D4)."""
    enviado = Envio.objects.filter(saida=OuterRef("pk")).values("saida").annotate(t=Sum("valor")).values("t")
    devolvido_ate_hoje = (
        Entrada.objects.filter(
            saida=OuterRef("pk"), tipo=TipoEntrada.DEVOLUCAO, situacao=SituacaoEntrada.VALIDADA
        )
        .values("saida")
        .annotate(t=Sum("valor"))
        .values("t")
    )
    estornada_depois = (
        Entrada.objects.filter(
            saida=OuterRef("pk"),
            tipo=TipoEntrada.DEVOLUCAO,
            situacao=SituacaoEntrada.ESTORNADA,
            estorno__registrado_em__gt=OuterRef("liquidada_em"),
        )
        .values("saida")
        .annotate(t=Sum("valor"))
        .values("t")
    )
    linhas = (
        Saida.objects.filter(liquidada_em__isnull=False)
        .filter(_no_intervalo("liquidada_em", de, ate))
        .annotate(
            enviado=Coalesce(Subquery(enviado, output_field=_DINHEIRO), Value(_ZERO)),
            devolvido=Coalesce(Subquery(devolvido_ate_hoje, output_field=_DINHEIRO), Value(_ZERO)),
            estornado_depois=Coalesce(Subquery(estornada_depois, output_field=_DINHEIRO), Value(_ZERO)),
        )
        .values_list("enviado", "devolvido", "estornado_depois")
    )
    # As subconsultas já aplicam a regra de `realizado_da_saida`: devolução validada, ou estornada depois da
    # liquidação. Aqui só se soma, com o mínimo zero da mesma função.
    return sum((calcular_valor_realizado_saida(env, dev + est) for env, dev, est in linhas), _ZERO)


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
