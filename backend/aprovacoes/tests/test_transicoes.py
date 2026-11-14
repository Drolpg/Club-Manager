"""A tabela de transições da solicitação, conferida contra uma tabela escrita aqui.

O teste não importa a tabela do código: as setas abaixo são copiadas do diagrama da spec funcional
(situações) e do adendo 1 do canvas. Todo par situação e comando que não está aqui tem de ser recusado.
"""

import itertools

import pytest

from aprovacoes.domain.transicoes import (
    ERRO_DE_SITUACAO,
    Comando,
    Situacao,
    situacao_apos,
    transicao_permitida,
)

SETAS = """
EM_ANALISE   APROVAR           APROVADA
EM_ANALISE   CONTESTAR         CONTESTADA
EM_ANALISE   RECUSAR           RECUSADA
EM_ANALISE   RETIRAR           RETIRADA
CONTESTADA   REENVIAR          EM_ANALISE
RETIRADA     REENVIAR          EM_ANALISE
RECUSADA     REABRIR           EM_ANALISE
APROVADA     EDITAR            EM_ANALISE
APROVADA     INICIAR_EXECUCAO  EM_EXECUCAO
APROVADA     ENCERRAR          ENCERRADA
EM_EXECUCAO  ENCERRAR          ENCERRADA
EM_ANALISE   CANCELAR          CANCELADA
CONTESTADA   CANCELAR          CANCELADA
RETIRADA     CANCELAR          CANCELADA
RECUSADA     CANCELAR          CANCELADA
APROVADA     CANCELAR          CANCELADA
"""

ESPERADAS = {
    (origem, comando): destino
    for origem, comando, destino in (linha.split() for linha in SETAS.strip().splitlines())
}

SITUACOES = (
    "EM_ANALISE",
    "RETIRADA",
    "CONTESTADA",
    "RECUSADA",
    "APROVADA",
    "EM_EXECUCAO",
    "ENCERRADA",
    "CANCELADA",
)
# `ENVIAR` não tem situação de origem: ele cria a solicitação já em análise.
COMANDOS_COM_ORIGEM = (
    "RETIRAR",
    "REENVIAR",
    "REABRIR",
    "EDITAR",
    "CANCELAR",
    "APROVAR",
    "CONTESTAR",
    "RECUSAR",
    "INICIAR_EXECUCAO",
    "ENCERRAR",
)
TODOS_OS_PARES = list(itertools.product(SITUACOES, COMANDOS_COM_ORIGEM))


def test_as_oito_situacoes_e_os_onze_comandos() -> None:
    assert {s.value for s in Situacao} == set(SITUACOES)
    assert {c.value for c in Comando} == {*COMANDOS_COM_ORIGEM, "ENVIAR"}


@pytest.mark.parametrize(("situacao", "comando"), TODOS_OS_PARES)
def test_cada_par_situacao_e_comando(situacao: str, comando: str) -> None:
    esperado = ESPERADAS.get((situacao, comando))

    assert transicao_permitida(Situacao(situacao), Comando(comando)) is (esperado is not None)
    if esperado is None:
        with pytest.raises(ValueError, match="não é permitid"):
            situacao_apos(Situacao(situacao), Comando(comando))
    else:
        assert situacao_apos(Situacao(situacao), Comando(comando)) == Situacao(esperado)


@pytest.mark.parametrize("comando", COMANDOS_COM_ORIGEM)
def test_inv_sol_08_encerrada_e_cancelada_nao_aceitam_nenhum_comando(comando: str) -> None:
    assert not transicao_permitida(Situacao.ENCERRADA, Comando(comando))
    assert not transicao_permitida(Situacao.CANCELADA, Comando(comando))


@pytest.mark.parametrize("comando", ["EDITAR", "CANCELAR", "RETIRAR"])
def test_inv_sol_09_em_execucao_nao_edita_nao_cancela_nem_retira(comando: str) -> None:
    assert not transicao_permitida(Situacao.EM_EXECUCAO, Comando(comando))


def test_enviar_nao_tem_origem() -> None:
    assert not any(transicao_permitida(Situacao(s), Comando.ENVIAR) for s in SITUACOES)


def test_codigo_de_erro_de_situacao_de_cada_comando() -> None:
    # Tabela de erros da technical-spec e o adendo 1 dela.
    assert ERRO_DE_SITUACAO == {
        Comando.RETIRAR: "NAO_ESTA_EM_ANALISE",
        Comando.APROVAR: "NAO_ESTA_EM_ANALISE",
        Comando.CONTESTAR: "NAO_ESTA_EM_ANALISE",
        Comando.RECUSAR: "NAO_ESTA_EM_ANALISE",
        Comando.REENVIAR: "NAO_ESTA_CONTESTADA_NEM_RETIRADA",
        Comando.REABRIR: "NAO_ESTA_RECUSADA",
        Comando.EDITAR: "NAO_PODE_EDITAR",
        Comando.CANCELAR: "NAO_PODE_CANCELAR",
        Comando.INICIAR_EXECUCAO: "NAO_ESTA_APROVADA",
        Comando.ENCERRAR: "NAO_PODE_ENCERRAR",
    }
