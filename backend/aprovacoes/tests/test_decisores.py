"""Quem pode fazer o quê numa solicitação: funções puras, sem banco.

Ordem das conferências (adendo 1 da technical-spec): leitura de gestão → quem pode → situação. A existência da
solicitação é conferida pelo serviço, entre a leitura e o "quem pode".
"""

import dataclasses
import uuid

import pytest

from aprovacoes.domain.decisores import (
    COMANDOS_DO_USUARIO,
    Avaliacao,
    Fatos,
    FatosDoEnvio,
    acoes_disponiveis,
    avaliar,
    avaliar_envio,
    pode_decidir,
    precisa_indicar_aprovador,
)
from aprovacoes.domain.transicoes import Comando, Situacao

SOLICITANTE = uuid.uuid7()
OUTRO = uuid.uuid7()
INDICADO = uuid.uuid7()

DECISOES = (Comando.APROVAR, Comando.CONTESTAR, Comando.RECUSAR)


def _fatos(**extra: object) -> Fatos:
    base: dict[str, object] = {
        "ator_id": OUTRO,
        "solicitante_id": SOLICITANTE,
        "aprovador_indicado_id": None,
        "situacao": Situacao.EM_ANALISE,
        "le_gestao": True,
        "pode_aprovar_o_tipo": False,
        "tem_auto_aprovacao": False,
        "pode_reabrir_de_outros": False,
        "pode_cancelar_de_outros": False,
    }
    base.update(extra)
    return Fatos(**base)  # type: ignore[arg-type]


def _envio(**extra: object) -> FatosDoEnvio:
    base: dict[str, object] = {
        "solicitante_id": SOLICITANTE,
        "aprovador_indicado_id": None,
        "le_gestao": True,
        "pode_enviar_o_tipo": True,
        "pode_aprovar_o_tipo": False,
        "tem_auto_aprovacao": False,
        "indicado_le_gestao": False,
    }
    base.update(extra)
    return FatosDoEnvio(**base)  # type: ignore[arg-type]


# --- precisa_indicar_aprovador (INV-SOL-10) ---


@pytest.mark.parametrize(
    ("tem_permissao", "tem_auto", "esperado"),
    [(False, False, False), (False, True, False), (True, True, False), (True, False, True)],
)
def test_inv_sol_10_precisa_indicar_so_quem_aprovaria_o_proprio_pedido_sem_auto_aprovacao(
    tem_permissao: bool, tem_auto: bool, esperado: bool
) -> None:
    assert precisa_indicar_aprovador(tem_permissao, tem_auto) is esperado


# --- pode_decidir (INV-SOL-02, INV-SOL-11) ---


def _decidir(ator: uuid.UUID, *, indicado: uuid.UUID | None = None, aprovar: bool, auto: bool) -> Avaliacao:
    return pode_decidir(
        ator_id=ator,
        solicitante_id=SOLICITANTE,
        aprovador_indicado_id=indicado,
        tem_permissao_de_aprovar=aprovar,
        tem_auto_aprovacao=auto,
    )


def test_inv_sol_02_quem_tem_a_permissao_decide_o_pedido_de_outro() -> None:
    assert _decidir(OUTRO, aprovar=True, auto=False) == Avaliacao(True)


def test_inv_sol_02_sem_a_permissao_nao_decide_o_de_outro() -> None:
    assert _decidir(OUTRO, aprovar=False, auto=False) == Avaliacao(False, "PERMISSION_DENIED")


def test_inv_sol_02_auto_aprovacao_sozinha_nao_decide_o_de_outro() -> None:
    assert _decidir(OUTRO, aprovar=False, auto=True) == Avaliacao(False, "PERMISSION_DENIED")


@pytest.mark.parametrize("aprovar", [False, True])
def test_inv_sol_02_solicitante_sem_auto_aprovacao_nao_decide_o_proprio(aprovar: bool) -> None:
    assert _decidir(SOLICITANTE, aprovar=aprovar, auto=False) == Avaliacao(False, "SOLICITANTE_NAO_DECIDE")


def test_inv_sol_02_solicitante_com_auto_aprovacao_decide_o_proprio_marcado_como_aprovacao_propria() -> None:
    assert _decidir(SOLICITANTE, aprovar=True, auto=True) == Avaliacao(True, aprovacao_propria=True)


def test_inv_sol_02_auto_aprovacao_sem_a_permissao_de_aprovar_o_tipo_nao_decide() -> None:
    # A auto-aprovação é exceção à regra do próprio pedido, não a permissão de decidir o tipo (adendo 1, A2).
    assert _decidir(SOLICITANTE, aprovar=False, auto=True) == Avaliacao(False, "PERMISSION_DENIED")


def test_inv_sol_11_o_indicado_decide_sem_a_permissao_do_tipo() -> None:
    assert _decidir(INDICADO, indicado=INDICADO, aprovar=False, auto=False) == Avaliacao(True)


def test_inv_sol_11_o_indicado_de_outro_pedido_nao_decide_este() -> None:
    assert _decidir(OUTRO, indicado=INDICADO, aprovar=False, auto=False) == Avaliacao(
        False, "PERMISSION_DENIED"
    )


def test_inv_sol_02_o_solicitante_indicado_por_engano_continua_sem_decidir() -> None:
    assert _decidir(SOLICITANTE, indicado=SOLICITANTE, aprovar=False, auto=False) == Avaliacao(
        False, "SOLICITANTE_NAO_DECIDE"
    )


# --- avaliar: leitura de gestão vem primeiro ---


@pytest.mark.parametrize("comando", COMANDOS_DO_USUARIO)
def test_sem_leitura_de_gestao_nenhum_comando_e_aceito(comando: Comando) -> None:
    fatos = _fatos(
        ator_id=SOLICITANTE,
        le_gestao=False,
        pode_aprovar_o_tipo=True,
        tem_auto_aprovacao=True,
        pode_reabrir_de_outros=True,
        pode_cancelar_de_outros=True,
    )

    assert avaliar(comando, fatos) == Avaliacao(False, "PERMISSION_DENIED")


@pytest.mark.parametrize("comando", [Comando.ENVIAR, Comando.INICIAR_EXECUCAO, Comando.ENCERRAR])
def test_comandos_que_nao_sao_do_usuario_nao_passam_por_avaliar(comando: Comando) -> None:
    with pytest.raises(ValueError, match="não é comando do usuário"):
        avaliar(comando, _fatos())


# --- avaliar: só o solicitante retira, reenvia e edita ---


@pytest.mark.parametrize(
    ("comando", "situacao"),
    [
        (Comando.RETIRAR, Situacao.EM_ANALISE),
        (Comando.REENVIAR, Situacao.CONTESTADA),
        (Comando.REENVIAR, Situacao.RETIRADA),
        (Comando.EDITAR, Situacao.APROVADA),
    ],
)
def test_so_o_solicitante_retira_reenvia_e_edita(comando: Comando, situacao: Situacao) -> None:
    poderoso = _fatos(
        situacao=situacao,
        pode_aprovar_o_tipo=True,
        tem_auto_aprovacao=True,
        pode_reabrir_de_outros=True,
        pode_cancelar_de_outros=True,
    )

    assert avaliar(comando, dataclasses.replace(poderoso, ator_id=SOLICITANTE)) == Avaliacao(True)
    assert avaliar(comando, poderoso) == Avaliacao(False, "SO_O_SOLICITANTE")


def test_inv_sol_12_retirar_so_em_analise() -> None:
    fatos = _fatos(ator_id=SOLICITANTE, situacao=Situacao.CONTESTADA)

    assert avaliar(Comando.RETIRAR, fatos) == Avaliacao(False, "NAO_ESTA_EM_ANALISE")


def test_inv_sol_13_reenviar_so_contestada_ou_retirada() -> None:
    fatos = _fatos(ator_id=SOLICITANTE, situacao=Situacao.RECUSADA)

    assert avaliar(Comando.REENVIAR, fatos) == Avaliacao(False, "NAO_ESTA_CONTESTADA_NEM_RETIRADA")


# --- avaliar: reabrir e cancelar também por quem tem a permissão ---


@pytest.mark.parametrize(
    ("comando", "situacao", "permissao"),
    [
        (Comando.REABRIR, Situacao.RECUSADA, "pode_reabrir_de_outros"),
        (Comando.CANCELAR, Situacao.CONTESTADA, "pode_cancelar_de_outros"),
    ],
)
def test_reabrir_e_cancelar_pelo_solicitante_ou_por_quem_tem_a_permissao(
    comando: Comando, situacao: Situacao, permissao: str
) -> None:
    fatos = _fatos(situacao=situacao)

    assert avaliar(comando, dataclasses.replace(fatos, ator_id=SOLICITANTE)) == Avaliacao(True)
    assert avaliar(comando, fatos) == Avaliacao(False, "PERMISSION_DENIED")
    com_permissao = _fatos(situacao=situacao, **{permissao: True})
    assert avaliar(comando, com_permissao) == Avaliacao(True)


def test_a_permissao_de_reabrir_nao_cancela_e_vice_versa() -> None:
    fatos = _fatos(situacao=Situacao.RECUSADA)

    assert not avaliar(Comando.CANCELAR, dataclasses.replace(fatos, pode_reabrir_de_outros=True)).pode
    assert not avaliar(Comando.REABRIR, dataclasses.replace(fatos, pode_cancelar_de_outros=True)).pode


# --- avaliar: decisões ---


@pytest.mark.parametrize("comando", DECISOES)
def test_inv_sol_01_so_se_decide_em_analise(comando: Comando) -> None:
    fatos = _fatos(pode_aprovar_o_tipo=True, situacao=Situacao.RETIRADA)

    assert avaliar(comando, fatos) == Avaliacao(False, "NAO_ESTA_EM_ANALISE")


@pytest.mark.parametrize("comando", DECISOES)
def test_quem_pode_vem_antes_da_situacao(comando: Comando) -> None:
    fatos = _fatos(ator_id=SOLICITANTE, pode_aprovar_o_tipo=True, situacao=Situacao.APROVADA)

    assert avaliar(comando, fatos) == Avaliacao(False, "SOLICITANTE_NAO_DECIDE")


@pytest.mark.parametrize("comando", DECISOES)
def test_decisao_propria_com_auto_aprovacao_sai_marcada(comando: Comando) -> None:
    fatos = _fatos(ator_id=SOLICITANTE, pode_aprovar_o_tipo=True, tem_auto_aprovacao=True)

    assert avaliar(comando, fatos) == Avaliacao(True, aprovacao_propria=True)


# --- acoes_disponiveis: a mesma função, para o campo `acoes` do detalhe ---


def test_acoes_do_solicitante_em_analise() -> None:
    assert acoes_disponiveis(_fatos(ator_id=SOLICITANTE)) == (Comando.RETIRAR, Comando.CANCELAR)


def test_acoes_do_aprovador_em_analise() -> None:
    assert acoes_disponiveis(_fatos(pode_aprovar_o_tipo=True)) == DECISOES


def test_acoes_do_leitor_sem_permissao() -> None:
    assert acoes_disponiveis(_fatos()) == ()


def test_acoes_coincidem_com_avaliar_em_todas_as_combinacoes() -> None:
    papeis = [
        _fatos(ator_id=SOLICITANTE),
        _fatos(ator_id=SOLICITANTE, pode_aprovar_o_tipo=True, tem_auto_aprovacao=True),
        _fatos(pode_aprovar_o_tipo=True),
        _fatos(ator_id=INDICADO, aprovador_indicado_id=INDICADO),
        _fatos(pode_reabrir_de_outros=True, pode_cancelar_de_outros=True),
        _fatos(le_gestao=False, pode_aprovar_o_tipo=True),
    ]
    for papel in papeis:
        for situacao in Situacao:
            fatos = dataclasses.replace(papel, situacao=situacao)
            esperadas = tuple(c for c in COMANDOS_DO_USUARIO if avaliar(c, fatos).pode)
            assert acoes_disponiveis(fatos) == esperadas


# --- avaliar_envio (INV-SOL-10, INV-SOL-15; adendo 1: A1 e A3) ---


def test_envio_de_quem_le_gestao_e_pode_enviar() -> None:
    assert avaliar_envio(_envio()) == Avaliacao(True)


@pytest.mark.parametrize(("le_gestao", "pode_enviar"), [(False, True), (True, False), (False, False)])
def test_envio_exige_leitura_de_gestao_e_a_permissao_de_enviar(le_gestao: bool, pode_enviar: bool) -> None:
    fatos = _envio(le_gestao=le_gestao, pode_enviar_o_tipo=pode_enviar)

    assert avaliar_envio(fatos) == Avaliacao(False, "PERMISSION_DENIED")


def test_inv_sol_10_quem_aprovaria_o_proprio_pedido_precisa_indicar() -> None:
    assert avaliar_envio(_envio(pode_aprovar_o_tipo=True)) == Avaliacao(False, "APROVADOR_NAO_INDICADO")


def test_inv_sol_10_com_indicacao_valida_envia() -> None:
    fatos = _envio(pode_aprovar_o_tipo=True, aprovador_indicado_id=INDICADO, indicado_le_gestao=True)

    assert avaliar_envio(fatos) == Avaliacao(True)


def test_inv_sol_15_nao_indica_a_si_mesmo() -> None:
    fatos = _envio(pode_aprovar_o_tipo=True, aprovador_indicado_id=SOLICITANTE, indicado_le_gestao=True)

    assert avaliar_envio(fatos) == Avaliacao(False, "APROVADOR_INVALIDO")


def test_inv_sol_15_o_indicado_precisa_ler_gestao() -> None:
    fatos = _envio(pode_aprovar_o_tipo=True, aprovador_indicado_id=INDICADO, indicado_le_gestao=False)

    assert avaliar_envio(fatos) == Avaliacao(False, "APROVADOR_INVALIDO")


@pytest.mark.parametrize(("aprovar", "auto"), [(False, False), (True, True), (False, True)])
def test_indicacao_de_quem_nao_precisa_indicar_e_recusada(aprovar: bool, auto: bool) -> None:
    fatos = _envio(
        pode_aprovar_o_tipo=aprovar,
        tem_auto_aprovacao=auto,
        aprovador_indicado_id=INDICADO,
        indicado_le_gestao=True,
    )

    assert avaliar_envio(fatos) == Avaliacao(False, "APROVADOR_INVALIDO")
