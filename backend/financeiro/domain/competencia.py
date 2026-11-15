"""Cálculo puro de competências, datas de vencimento e janelas de geração e suspensão."""

import calendar
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class Periodicidade(StrEnum):
    MENSAL = "MENSAL"
    SEMANAL = "SEMANAL"
    ANUAL = "ANUAL"


@dataclass(frozen=True)
class Periodo:
    """Intervalo de datas fechado no início e opcionalmente aberto no fim (INV-SUS-01)."""

    inicio: date
    fim: date | None = None

    def __post_init__(self) -> None:
        if self.fim is not None and self.fim < self.inicio:
            raise ValueError("A data de fim da suspensão não pode ser anterior ao início.")

    def contem(self, data: date) -> bool:
        return self.inicio <= data and (self.fim is None or data <= self.fim)


@dataclass(frozen=True)
class RecorrenciaParaGeracao:
    id: uuid.UUID
    periodicidade: Periodicidade
    dia_vencimento: int
    mes_vencimento: int | None
    antecedencia_dias: int
    a_partir_de: date


@dataclass(frozen=True)
class CompetenciaElegivel:
    codigo: str
    vencimento: date


@dataclass(frozen=True)
class SuspensaoParaVerificacao:
    recorrencia_id: uuid.UUID | None
    inicio: date
    fim: date | None
    vigente: bool


def competencia_da_data(periodicidade: Periodicidade, referencia: date) -> str:
    """Representação textual canônica do período de uma data."""
    if periodicidade == Periodicidade.MENSAL:
        return f"{referencia.year:04d}-{referencia.month:02d}"
    if periodicidade == Periodicidade.SEMANAL:
        iso = referencia.isocalendar()
        return f"{iso.year:04d}-W{iso.week:02d}"
    return f"{referencia.year:04d}"


def _proxima_competencia(periodicidade: Periodicidade, competencia: str) -> str:
    if periodicidade == Periodicidade.MENSAL:
        ano, mes = (int(parte) for parte in competencia.split("-"))
        if mes == 12:
            return f"{ano + 1:04d}-01"
        return f"{ano:04d}-{mes + 1:02d}"
    if periodicidade == Periodicidade.SEMANAL:
        ano_str, semana_str = competencia.split("-W")
        segunda = date.fromisocalendar(int(ano_str), int(semana_str), 1)
        proxima = segunda + timedelta(days=7)
        iso = proxima.isocalendar()
        return f"{iso.year:04d}-W{iso.week:02d}"
    ano = int(competencia)
    return f"{ano + 1:04d}"


def data_vencimento_da_competencia(
    periodicidade: Periodicidade,
    competencia: str,
    *,
    dia_vencimento: int,
    mes_vencimento: int | None = None,
) -> date:
    """Resolve a data exata de vencimento, ajustando dias 29..31 para meses mais curtos."""
    if periodicidade == Periodicidade.MENSAL:
        ano, mes = (int(parte) for parte in competencia.split("-"))
        ultimo = calendar.monthrange(ano, mes)[1]
        return date(ano, mes, min(dia_vencimento, ultimo))
    if periodicidade == Periodicidade.SEMANAL:
        ano_str, semana_str = competencia.split("-W")
        return date.fromisocalendar(int(ano_str), int(semana_str), dia_vencimento)
    if mes_vencimento is None:
        raise ValueError("Recorrência anual exige mes_vencimento.")
    ano = int(competencia)
    ultimo = calendar.monthrange(ano, mes_vencimento)[1]
    return date(ano, mes_vencimento, min(dia_vencimento, ultimo))


def competencias_a_gerar(rec: RecorrenciaParaGeracao, hoje: date) -> list[CompetenciaElegivel]:
    """Calcula competências elegíveis para geração na data `hoje` (INV-REC-04)."""
    if rec.antecedencia_dias < 0:
        raise ValueError("A antecedência em dias não pode ser negativa.")
    horizonte = hoje + timedelta(days=rec.antecedencia_dias)
    atual = competencia_da_data(rec.periodicidade, max(rec.a_partir_de, hoje))
    limite = competencia_da_data(rec.periodicidade, horizonte)

    resultado: list[CompetenciaElegivel] = []
    while True:
        vencimento = data_vencimento_da_competencia(
            rec.periodicidade,
            atual,
            dia_vencimento=rec.dia_vencimento,
            mes_vencimento=rec.mes_vencimento,
        )
        aviso_em = vencimento - timedelta(days=rec.antecedencia_dias)
        if vencimento >= rec.a_partir_de and vencimento >= hoje and aviso_em <= hoje:
            resultado.append(CompetenciaElegivel(codigo=atual, vencimento=vencimento))
        if atual == limite or vencimento > horizonte:
            break
        atual = _proxima_competencia(rec.periodicidade, atual)
    return resultado


def suspensa_na_data(
    suspensoes: Iterable[SuspensaoParaVerificacao],
    recorrencia_id: uuid.UUID,
    data_vencimento: date,
) -> bool:
    """Verdadeiro se alguma suspensão vigente do escopo cobre `data_vencimento` (INV-SUS-03)."""
    for item in suspensoes:
        if not item.vigente:
            continue
        if item.recorrencia_id is not None and item.recorrencia_id != recorrencia_id:
            continue
        if Periodo(inicio=item.inicio, fim=item.fim).contem(data_vencimento):
            return True
    return False
