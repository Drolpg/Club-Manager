"""Situações e comandos da solicitação, e a tabela de transições (diagrama da spec funcional e adendo 1 do
canvas). É o único lugar que diz de onde para onde a solicitação vai; todo método do aggregate a consulta
antes de mudar o estado.
"""

from enum import StrEnum


class Situacao(StrEnum):
    EM_ANALISE = "EM_ANALISE"
    RETIRADA = "RETIRADA"
    CONTESTADA = "CONTESTADA"
    RECUSADA = "RECUSADA"
    APROVADA = "APROVADA"
    EM_EXECUCAO = "EM_EXECUCAO"
    ENCERRADA = "ENCERRADA"
    CANCELADA = "CANCELADA"


class Comando(StrEnum):
    ENVIAR = "ENVIAR"
    RETIRAR = "RETIRAR"
    REENVIAR = "REENVIAR"
    REABRIR = "REABRIR"
    EDITAR = "EDITAR"
    CANCELAR = "CANCELAR"
    APROVAR = "APROVAR"
    CONTESTAR = "CONTESTAR"
    RECUSAR = "RECUSAR"
    INICIAR_EXECUCAO = "INICIAR_EXECUCAO"
    ENCERRAR = "ENCERRAR"


_S = Situacao
_C = Comando

# `ENVIAR` não está aqui: ele cria a solicitação, já em análise, e não parte de situação nenhuma.
_TRANSICOES: dict[tuple[Situacao, Comando], Situacao] = {
    (_S.EM_ANALISE, _C.APROVAR): _S.APROVADA,
    (_S.EM_ANALISE, _C.CONTESTAR): _S.CONTESTADA,
    (_S.EM_ANALISE, _C.RECUSAR): _S.RECUSADA,
    (_S.EM_ANALISE, _C.RETIRAR): _S.RETIRADA,
    (_S.CONTESTADA, _C.REENVIAR): _S.EM_ANALISE,
    (_S.RETIRADA, _C.REENVIAR): _S.EM_ANALISE,
    (_S.RECUSADA, _C.REABRIR): _S.EM_ANALISE,
    (_S.APROVADA, _C.EDITAR): _S.EM_ANALISE,
    (_S.APROVADA, _C.INICIAR_EXECUCAO): _S.EM_EXECUCAO,
    (_S.APROVADA, _C.ENCERRAR): _S.ENCERRADA,
    (_S.EM_EXECUCAO, _C.ENCERRAR): _S.ENCERRADA,
    (_S.EM_ANALISE, _C.CANCELAR): _S.CANCELADA,
    (_S.CONTESTADA, _C.CANCELAR): _S.CANCELADA,
    (_S.RETIRADA, _C.CANCELAR): _S.CANCELADA,
    (_S.RECUSADA, _C.CANCELAR): _S.CANCELADA,
    (_S.APROVADA, _C.CANCELAR): _S.CANCELADA,
}

# O código de erro quando o comando chega na situação errada (technical-spec e o adendo 1 dela).
ERRO_DE_SITUACAO: dict[Comando, str] = {
    _C.RETIRAR: "NAO_ESTA_EM_ANALISE",
    _C.APROVAR: "NAO_ESTA_EM_ANALISE",
    _C.CONTESTAR: "NAO_ESTA_EM_ANALISE",
    _C.RECUSAR: "NAO_ESTA_EM_ANALISE",
    _C.REENVIAR: "NAO_ESTA_CONTESTADA_NEM_RETIRADA",
    _C.REABRIR: "NAO_ESTA_RECUSADA",
    _C.EDITAR: "NAO_PODE_EDITAR",
    _C.CANCELAR: "NAO_PODE_CANCELAR",
    _C.INICIAR_EXECUCAO: "NAO_ESTA_APROVADA",
    _C.ENCERRAR: "NAO_PODE_ENCERRAR",
}


def transicao_permitida(situacao: Situacao, comando: Comando) -> bool:
    return (situacao, comando) in _TRANSICOES


def situacao_apos(situacao: Situacao, comando: Comando) -> Situacao:
    """A situação depois do comando. Levanta `ValueError` se a transição não é permitida."""
    try:
        return _TRANSICOES[(situacao, comando)]
    except KeyError:
        raise ValueError(f"{comando} não é permitido em {situacao}.") from None
