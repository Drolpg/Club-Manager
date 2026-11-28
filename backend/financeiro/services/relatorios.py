"""Consultas para os relatórios (spec `relatorios/relatorios-pdf-e-csv`, "Fontes de cada relatório").

Só leitura, com as mesmas regras dos totais (N1 a N15): cada valor entra no período pela data em que se tornou
realizado, o estorno entra na data dele, com sinal negativo, no lado do original, e o estorno de devolução não
entra. Nenhuma confere quem pergunta (é do catálogo de `relatorios`), e nenhuma devolve texto livre de pessoa
além do que a tela de lançamentos já mostra.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Exists, OuterRef, Subquery, Sum
from django.utils import timezone

from acesso import public as acesso
from financeiro.domain.saidas import prestacao_em_atraso
from financeiro.domain.transicoes import SituacaoCobranca, SituacaoEntrada, SituacaoSaida
from financeiro.models import (
    Cobranca,
    Complemento,
    Convocacao,
    Entrada,
    Envio,
    Estorno,
    Pagamento,
    PrestacaoDeContas,
    Questionamento,
    Saida,
    SituacaoComplemento,
    SituacaoPagamento,
    SituacaoPrestacao,
    TipoEntrada,
)
from financeiro.services.totais import (
    _ENTRADA_REALIZADA,
    _ESTORNO_DE_ENTRADA,
    _ESTORNO_DE_SAIDA,
    TotaisDoPeriodo,
    _no_intervalo,
    inadimplentes,
    realizado_por_saida,
    totais_do_periodo,
)

_ZERO = Decimal("0.00")
ENTRADA = "ENTRADA"
SAIDA = "SAIDA"


class _Nomes:
    """Os nomes das pessoas, um por consulta ao `acesso`."""

    def __init__(self) -> None:
        self._cache: dict[uuid.UUID, str] = {}

    def de(self, pessoa_id: uuid.UUID | None) -> str:
        if pessoa_id is None:
            return ""
        if pessoa_id not in self._cache:
            usuario = acesso.usuario_por_id(pessoa_id)
            self._cache[pessoa_id] = usuario.nome if usuario is not None else ""
        return self._cache[pessoa_id]


# Extrato -----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LancamentoRealizado:
    """Uma linha do extrato. `valor` é positivo no realizado e negativo no estorno, no `lado` do original."""

    realizado_em: date
    data_do_fato: date
    tipo: str
    lado: str
    categoria: str
    setor: str | None
    descricao: str
    contraparte: str
    valor: Decimal


def _cobrancas_pagas(
    de: date, ate: date, nomes: _Nomes
) -> list[tuple[datetime, uuid.UUID, LancamentoRealizado]]:
    data_informada = (
        Pagamento.objects.filter(cobranca=OuterRef("pk"), situacao=SituacaoPagamento.VALIDADO)
        .order_by("-decidido_em")
        .values("data_pagamento")[:1]
    )
    cobrancas = (
        Cobranca.objects.filter(paga_em__isnull=False)
        .filter(_no_intervalo("paga_em", de, ate))
        .annotate(data_informada=Subquery(data_informada))
    )
    return [
        (
            c.paga_em,
            c.id,
            LancamentoRealizado(
                realizado_em=timezone.localdate(c.paga_em),
                data_do_fato=c.data_informada or timezone.localdate(c.paga_em),
                tipo="COBRANCA",
                lado=ENTRADA,
                categoria=c.categoria_nome,
                setor=None,
                descricao=c.descricao,
                contraparte=nomes.de(c.devedor_id),
                valor=c.valor,
            ),
        )
        for c in cobrancas
        if c.paga_em is not None
    ]


def _entradas_validadas(de: date, ate: date) -> list[tuple[datetime, uuid.UUID, LancamentoRealizado]]:
    entradas = Entrada.objects.filter(tipo=TipoEntrada.SEM_DEVEDOR, situacao__in=_ENTRADA_REALIZADA).filter(
        _no_intervalo("decidido_em", de, ate)
    )
    return [
        (
            e.decidido_em,
            e.id,
            LancamentoRealizado(
                realizado_em=timezone.localdate(e.decidido_em),
                data_do_fato=e.data,
                tipo="ENTRADA",
                lado=ENTRADA,
                categoria=e.categoria_nome,
                setor=None,
                descricao=e.origem,
                contraparte=e.origem,
                valor=e.valor,
            ),
        )
        for e in entradas
        if e.decidido_em is not None
    ]


def _contraparte_da_saida(saida: Saida, nomes: _Nomes) -> str:
    return f"{nomes.de(saida.solicitante_id)} — {saida.setor_nome}"


def _saidas_liquidadas(
    de: date, ate: date, nomes: _Nomes
) -> list[tuple[datetime, uuid.UUID, LancamentoRealizado]]:
    saidas = list(
        Saida.objects.filter(liquidada_em__isnull=False).filter(_no_intervalo("liquidada_em", de, ate))
    )
    realizados = realizado_por_saida([s.id for s in saidas])
    linhas = []
    for s in saidas:
        if s.liquidada_em is None:
            continue
        fato = s.primeiro_envio_em or s.liquidada_em
        linhas.append(
            (
                s.liquidada_em,
                s.id,
                LancamentoRealizado(
                    realizado_em=timezone.localdate(s.liquidada_em),
                    data_do_fato=timezone.localdate(fato),
                    tipo="SAIDA",
                    lado=SAIDA,
                    categoria=s.categoria_nome,
                    setor=s.setor_nome,
                    descricao=s.descricao,
                    contraparte=_contraparte_da_saida(s, nomes),
                    valor=realizados[s.id],
                ),
            )
        )
    return linhas


def _estorno(e: Estorno, nomes: _Nomes) -> LancamentoRealizado:
    if e.saida is not None:
        lado, categoria, setor = SAIDA, e.saida.categoria_nome, e.saida.setor_nome
        descricao, contraparte = e.saida.descricao, _contraparte_da_saida(e.saida, nomes)
    elif e.cobranca is not None:
        lado, categoria, setor = ENTRADA, e.cobranca.categoria_nome, None
        descricao, contraparte = e.cobranca.descricao, nomes.de(e.cobranca.devedor_id)
    else:
        # A consulta só traz estornos de cobrança, de entrada sem devedor e de saída.
        entrada = e.entrada
        lado, categoria, setor = ENTRADA, entrada.categoria_nome if entrada else "", None
        descricao = contraparte = entrada.origem if entrada else ""
    dia = timezone.localdate(e.registrado_em)
    return LancamentoRealizado(
        realizado_em=dia,
        data_do_fato=dia,
        tipo="ESTORNO",
        lado=lado,
        categoria=categoria,
        setor=setor,
        descricao=f"Estorno de: {descricao}",
        contraparte=contraparte,
        valor=-e.valor,
    )


def _estornos(de: date, ate: date, nomes: _Nomes) -> list[tuple[datetime, uuid.UUID, LancamentoRealizado]]:
    estornos = (
        Estorno.objects.filter(_ESTORNO_DE_ENTRADA | _ESTORNO_DE_SAIDA)
        .filter(_no_intervalo("registrado_em", de, ate))
        .select_related("saida", "cobranca", "entrada")
    )
    return [(e.registrado_em, e.id, _estorno(e, nomes)) for e in estornos]


def lancamentos_realizados(de: date, ate: date) -> list[LancamentoRealizado]:
    """Os lançamentos realizados em `[de, ate]`, pela data de realização: somam N5 e N6 do período (CA-16)."""
    nomes = _Nomes()
    todas = [
        *_cobrancas_pagas(de, ate, nomes),
        *_entradas_validadas(de, ate),
        *_saidas_liquidadas(de, ate, nomes),
        *_estornos(de, ate, nomes),
    ]
    return [linha for _instante, _id, linha in sorted(todas, key=lambda item: (item[0], item[1]))]


# Balancete ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LinhaDoBalancete:
    nome: str
    realizado: Decimal
    estornos: Decimal

    @property
    def liquido(self) -> Decimal:
        return self.realizado - self.estornos


@dataclass(frozen=True)
class Balancete:
    entradas: list[LinhaDoBalancete]
    saidas: list[LinhaDoBalancete]
    saidas_por_setor: list[LinhaDoBalancete]
    totais: TotaisDoPeriodo


def _agrupar(linhas: Iterable[tuple[str, Decimal]]) -> list[LinhaDoBalancete]:
    realizado: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    estornos: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for nome, valor in linhas:
        if valor < 0:
            estornos[nome] += -valor
        else:
            realizado[nome] += valor
    nomes = sorted(set(realizado) | set(estornos))
    return [LinhaDoBalancete(nome, realizado[nome], estornos[nome]) for nome in nomes]


def balancete(de: date, ate: date) -> Balancete:
    """Por categoria e, nas saídas, por setor, com o estorno na categoria do original (CA-17)."""
    linhas = lancamentos_realizados(de, ate)
    entradas = [(linha.categoria, linha.valor) for linha in linhas if linha.lado == ENTRADA]
    saidas = [linha for linha in linhas if linha.lado == SAIDA]
    return Balancete(
        entradas=_agrupar(entradas),
        saidas=_agrupar((linha.categoria, linha.valor) for linha in saidas),
        saidas_por_setor=_agrupar((linha.setor or "", linha.valor) for linha in saidas),
        totais=totais_do_periodo(de, ate),
    )


# Inadimplência -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CobrancaInadimplente:
    """Sem o texto da justificativa nem o do questionamento, e sem e-mail ou telefone (Q7-A)."""

    devedor: str
    descricao: str
    categoria: str
    valor: Decimal
    vencimento: date
    dias_de_atraso: int
    convocado: bool
    justificou: bool


def inadimplencia_detalhada(hoje: date) -> list[CobrancaInadimplente]:
    """As cobranças de N12, por vencimento, com "convocado" e "justificou" (CA-18)."""
    convocacao = Convocacao.objects.filter(cobranca=OuterRef("pk"))
    cobrancas = (
        inadimplentes()
        .annotate(
            convocado=Exists(convocacao),
            justificou=Exists(convocacao.filter(justificada_em__isnull=False)),
        )
        .order_by("vencimento", "id")
    )
    nomes = _Nomes()
    return [
        CobrancaInadimplente(
            devedor=nomes.de(c.devedor_id),
            descricao=c.descricao,
            categoria=c.categoria_nome,
            valor=c.valor,
            vencimento=c.vencimento,
            dias_de_atraso=(hoje - c.vencimento).days,
            convocado=c.convocado,
            justificou=c.justificou,
        )
        for c in cobrancas
    ]


# Prestação de contas -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class PrestacaoDaSaida:
    solicitante: str
    setor: str
    categoria: str
    descricao: str
    aprovado: Decimal
    enviado: Decimal
    gasto_informado: Decimal
    devolvido_validado: Decimal
    nao_reembolsado: Decimal
    situacao: str
    primeiro_envio: date
    dias_desde_o_envio: int
    em_atraso: bool
    tem_comprovante: bool


_PENDENTES = (SituacaoSaida.RECURSO_ENVIADO.value, SituacaoSaida.EM_CONFERENCIA.value)


def _soma(qs: Any) -> Any:
    return Subquery(qs.values("saida").annotate(t=Sum("valor")).values("t"))


def prestacoes_de_contas(de: date, ate: date, *, so_pendentes: bool, hoje: date) -> list[PrestacaoDaSaida]:
    """As saídas com recurso enviado, pelo primeiro envio no período; o comprovante só como "tem" (CA-20)."""
    saidas = Saida.objects.filter(primeiro_envio_em__isnull=False).filter(
        _no_intervalo("primeiro_envio_em", de, ate)
    )
    if so_pendentes:
        saidas = saidas.filter(situacao__in=_PENDENTES)
    vigentes = PrestacaoDeContas.objects.filter(saida=OuterRef("pk"), situacao=SituacaoPrestacao.VIGENTE)
    saidas = saidas.annotate(
        r_enviado=_soma(Envio.objects.filter(saida=OuterRef("pk"))),
        r_gasto=_soma(vigentes),
        r_devolvido=_soma(
            Entrada.objects.filter(
                saida=OuterRef("pk"), tipo=TipoEntrada.DEVOLUCAO, situacao=SituacaoEntrada.VALIDADA
            )
        ),
        r_complementos=_soma(
            Complemento.objects.filter(saida=OuterRef("pk"), situacao=SituacaoComplemento.APROVADO)
        ),
        r_comprovante=Exists(vigentes.exclude(comprovante_chave="")),
    ).order_by("primeiro_envio_em", "id")
    nomes = _Nomes()
    linhas = []
    for s in saidas:
        if s.primeiro_envio_em is None:
            continue
        envio = timezone.localdate(s.primeiro_envio_em)
        linhas.append(
            PrestacaoDaSaida(
                solicitante=nomes.de(s.solicitante_id),
                setor=s.setor_nome,
                categoria=s.categoria_nome,
                descricao=s.descricao,
                aprovado=s.valor_aprovado + (s.r_complementos or _ZERO),
                enviado=s.r_enviado or _ZERO,
                gasto_informado=s.r_gasto or _ZERO,
                devolvido_validado=s.r_devolvido or _ZERO,
                nao_reembolsado=s.valor_nao_reembolsado,
                situacao=s.situacao,
                primeiro_envio=envio,
                dias_desde_o_envio=(hoje - envio).days,
                em_atraso=prestacao_em_atraso(
                    situacao=SituacaoSaida(s.situacao), primeiro_envio_em=envio, hoje=hoje
                ),
                tem_comprovante=s.r_comprovante,
            )
        )
    return linhas


# Fluxo de caixa: o previsto ----------------------------------------------------------------------------


@dataclass(frozen=True)
class PrevistoDoMes:
    """Pelo vencimento; só as cobranças já geradas (P28)."""

    mes: date
    previsto: Decimal
    recebido: Decimal
    em_aberto: Decimal
    questionadas: Decimal
    inadimplentes: Decimal


_SEM_VALOR = (
    SituacaoCobranca.ISENTA.value,
    SituacaoCobranca.CANCELADA.value,
    SituacaoCobranca.PERDOADA.value,
    SituacaoCobranca.RENEGOCIADA.value,
)
_EM_ABERTO = (
    SituacaoCobranca.ABERTA.value,
    SituacaoCobranca.ATRASADA.value,
    SituacaoCobranca.EM_VALIDACAO.value,
)


def _meses(de: date, ate: date) -> list[date]:
    meses, atual = [], de.replace(day=1)
    while atual <= ate:
        meses.append(atual)
        atual = (atual + timedelta(days=32)).replace(day=1)
    return meses


def _total(qs: Any) -> Decimal:
    total: Decimal | None = qs.aggregate(t=Sum("valor"))["t"]
    return total if total is not None else _ZERO


def fluxo_previsto(de: date, ate: date, *, hoje: date) -> list[PrevistoDoMes]:
    """Por mês de vencimento em `[de, ate]`: previsto, recebido até hoje, em aberto, questionadas e N12
    (CA-21).
    """
    questionada = Exists(Questionamento.objects.filter(cobranca=OuterRef("pk"), situacao="ABERTO"))
    resultado = []
    for inicio in _meses(de, ate):
        fim = (inicio + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        do_mes = Cobranca.objects.filter(
            vencimento__gte=max(inicio, de), vencimento__lte=min(fim, ate)
        ).exclude(situacao__in=_SEM_VALOR)
        resultado.append(
            PrevistoDoMes(
                mes=inicio,
                previsto=_total(do_mes),
                recebido=_total(
                    do_mes.filter(situacao=SituacaoCobranca.PAGA.value).filter(
                        _no_intervalo("paga_em", None, hoje)
                    )
                ),
                em_aberto=_total(do_mes.filter(situacao__in=_EM_ABERTO)),
                questionadas=_total(do_mes.filter(questionada)),
                inadimplentes=_total(do_mes.filter(pk__in=inadimplentes().values("pk"))),
            )
        )
    return resultado


# Orçamentos de eventos ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class OrcamentoDoEvento:
    """O aprovado das saídas ligadas ao evento e o realizado delas (N2); `None` sem nenhuma liquidada."""

    aprovado: Decimal
    realizado: Decimal | None


def orcamentos_de_eventos(evento_ids: list[uuid.UUID]) -> dict[uuid.UUID, OrcamentoDoEvento]:
    """Por evento, das saídas não canceladas ligadas a ele; o evento sem saída não aparece (CA-19)."""
    saidas = list(
        Saida.objects.filter(evento_id__in=evento_ids)
        .exclude(situacao=SituacaoSaida.CANCELADA.value)
        .prefetch_related("complementos")
    )
    realizados = realizado_por_saida([s.id for s in saidas if s.situacao == SituacaoSaida.LIQUIDADA.value])
    aprovado: dict[uuid.UUID, Decimal] = defaultdict(lambda: _ZERO)
    realizado: dict[uuid.UUID, Decimal] = {}
    for s in saidas:
        if s.evento_id is None:
            continue
        aprovado[s.evento_id] += s.valor_aprovado_total()
        if s.id in realizados:
            realizado[s.evento_id] = realizado.get(s.evento_id, _ZERO) + realizados[s.id]
    return {
        evento_id: OrcamentoDoEvento(aprovado=valor, realizado=realizado.get(evento_id))
        for evento_id, valor in aprovado.items()
    }
