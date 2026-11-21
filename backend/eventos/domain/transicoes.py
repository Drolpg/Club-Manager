"""Os comandos do evento e em que situação cada um vale (INV-EVT-04, INV-EVT-05). Todo método do aggregate e a
função `avaliar` consultam esta tabela antes de mudar o estado.
"""

from enum import StrEnum

from eventos.domain.situacao import ENCERRADAS, SituacaoDoEvento

S = SituacaoDoEvento


class ComandoDoEvento(StrEnum):
    PROPOR = "PROPOR"
    EDITAR = "EDITAR"
    REABRIR = "REABRIR"
    VINCULAR_ORCAMENTO = "VINCULAR_ORCAMENTO"
    CONFIRMAR_REALIZACAO = "CONFIRMAR_REALIZACAO"
    CANCELAR = "CANCELAR"
    RESPONDER_PRESENCA = "RESPONDER_PRESENCA"


C = ComandoDoEvento

_ABERTAS = frozenset({S.EM_APROVACAO, S.PUBLICADO, S.RECUSADO})

# Em que situações o comando vale. `PROPOR` cria o evento e não parte de situação nenhuma.
_VALE_EM: dict[ComandoDoEvento, frozenset[SituacaoDoEvento]] = {
    C.EDITAR: _ABERTAS,
    C.VINCULAR_ORCAMENTO: _ABERTAS,
    C.CANCELAR: _ABERTAS,
    C.REABRIR: frozenset({S.RECUSADO}),
    C.CONFIRMAR_REALIZACAO: frozenset({S.PUBLICADO}),
    C.RESPONDER_PRESENCA: frozenset({S.PUBLICADO}),
}

_ERRO_FORA_DA_SITUACAO = {
    C.REABRIR: "NAO_ESTA_RECUSADO",
    C.CONFIRMAR_REALIZACAO: "NAO_ESTA_PUBLICADO",
    C.RESPONDER_PRESENCA: "NAO_ESTA_PUBLICADO",
}


def transicao_permitida(situacao: SituacaoDoEvento, comando: ComandoDoEvento) -> bool:
    return situacao in _VALE_EM.get(comando, frozenset())


def erro_de_situacao(situacao: SituacaoDoEvento, comando: ComandoDoEvento) -> str:
    """O código do erro quando o comando chega na situação errada. Evento encerrado não aceita nenhum."""
    if situacao in ENCERRADAS:
        return "EVENTO_ENCERRADO"
    return _ERRO_FORA_DA_SITUACAO.get(comando, "EVENTO_ENCERRADO")
