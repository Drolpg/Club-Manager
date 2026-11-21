"""Regras puras dos dados, da realização e dos avisos de realização. O serviço converte o fuso antes: aqui só
chegam `date` e `datetime` já prontos (spec técnica do M8, "Fuso e datas").
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

LIMITE_DO_TITULO = 120
LIMITE_DO_LOCAL = 200
LIMITE_DA_DESCRICAO = 2000


class DadosInvalidos(Exception):
    """Os campos recusados, com as mensagens. Vira `VALIDATION_ERROR` na fronteira."""

    def __init__(self, erros: dict[str, list[str]]) -> None:
        super().__init__("Os dados do evento são inválidos.")
        self.erros = erros


class ErroDeRegra(Exception):
    """Uma regra de negócio violada. `campo` vem preenchido quando é `VALIDATION_ERROR`."""

    def __init__(self, codigo: str, mensagem: str, campo: str | None = None) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.campo = campo


@dataclass(frozen=True)
class DadosDoEvento:
    titulo: str
    descricao: str
    local: str
    inicio: datetime


def _texto(
    erros: dict[str, list[str]], campo: str, valor: str, limite: int, *, obrigatorio: bool = True
) -> str:
    limpo = valor.strip()
    if obrigatorio and not limpo:
        erros.setdefault(campo, []).append("Este campo é obrigatório.")
    elif len(limpo) > limite:
        erros.setdefault(campo, []).append(f"Use no máximo {limite} caracteres.")
    return limpo


def validar_proposta(
    *, titulo: str, descricao: str, local: str, inicio: datetime, agora: datetime
) -> DadosDoEvento:
    """Título e local obrigatórios, descrição opcional, início futuro (CA-03). Vale também na edição."""
    erros: dict[str, list[str]] = {}
    dados = DadosDoEvento(
        titulo=_texto(erros, "titulo", titulo, LIMITE_DO_TITULO),
        descricao=_texto(erros, "descricao", descricao, LIMITE_DA_DESCRICAO, obrigatorio=False),
        local=_texto(erros, "local", local, LIMITE_DO_LOCAL),
        inicio=inicio,
    )
    if inicio <= agora:
        erros.setdefault("inicio", []).append("A data e a hora do evento precisam estar no futuro.")
    if erros:
        raise DadosInvalidos(erros)
    return dados


def avaliar_realizacao(*, data_planejada: date, data_real: date, hoje: date, motivo: str) -> None:
    """INV-EVT-05 e regra 8: data real não futura; data diferente da planejada exige motivo."""
    if data_real > hoje:
        raise ErroDeRegra("DATA_FUTURA", "A data em que o evento aconteceu não pode estar no futuro.")
    if data_real != data_planejada and not motivo.strip():
        raise ErroDeRegra(
            "VALIDATION_ERROR",
            "Informe por que o evento aconteceu em outra data.",
            campo="motivo",
        )


class EtapaDeAviso(StrEnum):
    NA_DATA = "NA_DATA"
    UM_DIA = "UM_DIA"
    TRES_DIAS = "TRES_DIAS"


_DIAS_DEPOIS = {EtapaDeAviso.NA_DATA: 0, EtapaDeAviso.UM_DIA: 1, EtapaDeAviso.TRES_DIAS: 3}


def avisos_de_realizacao_devidos(
    *, data_do_evento: date, hoje: date, marcas: dict[EtapaDeAviso, date | None]
) -> tuple[EtapaDeAviso, ...]:
    """As etapas cuja data chegou e que ainda não têm marca (CA-18; P4), na ordem."""
    return tuple(
        etapa
        for etapa, dias in _DIAS_DEPOIS.items()
        if hoje >= data_do_evento + timedelta(days=dias) and marcas.get(etapa) is None
    )
