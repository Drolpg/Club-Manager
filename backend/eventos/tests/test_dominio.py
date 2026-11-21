"""Domínio puro de `eventos`, sem banco: precedência da situação, transições, regras e quem pode o quê.

Os casos seguem a spec técnica do M8 ("Funções puras" e "Quem pode, em `avaliar`") e a regra de precedência de
`domain-events.md`.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from itertools import product

import pytest

from eventos.domain.autorizacao import FatosDoEvento, acoes_disponiveis, avaliar
from eventos.domain.regras import (
    DadosInvalidos,
    ErroDeRegra,
    EtapaDeAviso,
    avaliar_realizacao,
    avisos_de_realizacao_devidos,
    validar_proposta,
)
from eventos.domain.situacao import SituacaoDoEvento, situacao_do_evento
from eventos.domain.transicoes import ComandoDoEvento, erro_de_situacao, transicao_permitida

S = SituacaoDoEvento
C = ComandoDoEvento
SOLICITACAO = (
    "EM_ANALISE",
    "RETIRADA",
    "CONTESTADA",
    "RECUSADA",
    "APROVADA",
    "EM_EXECUCAO",
    "ENCERRADA",
    "CANCELADA",
)
APROVADAS = {"APROVADA", "EM_EXECUCAO", "ENCERRADA"}

# --- situacao_do_evento ---


@pytest.mark.parametrize(
    ("do_evento", "envolve_custo", "orcamento"),
    list(product(SOLICITACAO, (False, True), (None, *SOLICITACAO))),
)
def test_precedencia_sem_comando(do_evento: str, envolve_custo: bool, orcamento: str | None) -> None:
    situacao = situacao_do_evento(
        cancelado=False,
        realizado=False,
        situacao_da_solicitacao_do_evento=do_evento,
        envolve_custo=envolve_custo,
        situacao_do_orcamento=orcamento,
    )

    if do_evento == "RECUSADA":
        assert situacao == S.RECUSADO
    elif do_evento in APROVADAS and (not envolve_custo or orcamento in APROVADAS):
        assert situacao == S.PUBLICADO
    else:
        assert situacao == S.EM_APROVACAO


@pytest.mark.parametrize(("do_evento", "orcamento"), list(product(SOLICITACAO, (None, *SOLICITACAO))))
def test_cancelado_vence_realizado_e_realizado_vence_o_resto(do_evento: str, orcamento: str | None) -> None:
    def calcular(*, cancelado: bool, realizado: bool) -> SituacaoDoEvento:
        return situacao_do_evento(
            cancelado=cancelado,
            realizado=realizado,
            situacao_da_solicitacao_do_evento=do_evento,
            envolve_custo=True,
            situacao_do_orcamento=orcamento,
        )

    assert calcular(cancelado=True, realizado=True) == S.CANCELADO
    assert calcular(cancelado=True, realizado=False) == S.CANCELADO
    assert calcular(cancelado=False, realizado=True) == S.REALIZADO


def test_evento_com_custo_sem_orcamento_nunca_publica() -> None:
    for do_evento in APROVADAS:
        assert (
            situacao_do_evento(
                cancelado=False,
                realizado=False,
                situacao_da_solicitacao_do_evento=do_evento,
                envolve_custo=True,
                situacao_do_orcamento=None,
            )
            == S.EM_APROVACAO
        )


# --- transições ---

ABERTAS = (S.EM_APROVACAO, S.PUBLICADO, S.RECUSADO)
ENCERRADAS = (S.REALIZADO, S.CANCELADO)


@pytest.mark.parametrize(("situacao", "comando"), list(product(SituacaoDoEvento, ComandoDoEvento)))
def test_tabela_de_transicoes(situacao: SituacaoDoEvento, comando: ComandoDoEvento) -> None:
    if comando == C.PROPOR or situacao in ENCERRADAS:
        esperado = False
    elif comando in (C.EDITAR, C.VINCULAR_ORCAMENTO, C.CANCELAR):
        esperado = True
    elif comando == C.REABRIR:
        esperado = situacao == S.RECUSADO
    else:
        esperado = situacao == S.PUBLICADO

    assert transicao_permitida(situacao, comando) is esperado


def test_codigos_de_erro_de_situacao() -> None:
    for comando in (C.EDITAR, C.REABRIR, C.VINCULAR_ORCAMENTO, C.CANCELAR, C.CONFIRMAR_REALIZACAO):
        for situacao in ENCERRADAS:
            assert erro_de_situacao(situacao, comando) == "EVENTO_ENCERRADO"
    assert erro_de_situacao(S.EM_APROVACAO, C.REABRIR) == "NAO_ESTA_RECUSADO"
    assert erro_de_situacao(S.PUBLICADO, C.REABRIR) == "NAO_ESTA_RECUSADO"
    assert erro_de_situacao(S.EM_APROVACAO, C.CONFIRMAR_REALIZACAO) == "NAO_ESTA_PUBLICADO"
    assert erro_de_situacao(S.RECUSADO, C.RESPONDER_PRESENCA) == "NAO_ESTA_PUBLICADO"


# --- validar_proposta ---

AGORA = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)


def _dados(**mudar: object) -> dict[str, object]:
    dados: dict[str, object] = {
        "titulo": "  Amistoso  ",
        "descricao": "Contra o vizinho",
        "local": "Campo do bairro",
        "inicio": AGORA + timedelta(days=3),
    }
    dados.update(mudar)
    return dados


def test_dados_validos_sao_normalizados() -> None:
    validos = validar_proposta(**_dados(), agora=AGORA)  # type: ignore[arg-type]

    assert (validos.titulo, validos.local, validos.descricao) == (
        "Amistoso",
        "Campo do bairro",
        "Contra o vizinho",
    )


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("titulo", "   "),
        ("titulo", "x" * 121),
        ("local", ""),
        ("local", "x" * 201),
        ("descricao", "x" * 2001),
        ("inicio", AGORA),
        ("inicio", AGORA - timedelta(minutes=1)),
    ],
)
def test_dados_invalidos_apontam_o_campo(campo: str, valor: object) -> None:
    with pytest.raises(DadosInvalidos) as recusa:
        validar_proposta(**_dados(**{campo: valor}), agora=AGORA)  # type: ignore[arg-type]

    assert list(recusa.value.erros) == [campo]


def test_descricao_vazia_e_aceita() -> None:
    assert validar_proposta(**_dados(descricao=""), agora=AGORA).descricao == ""  # type: ignore[arg-type]


# --- avaliar_realizacao ---

PLANEJADA = date(2026, 12, 10)


def test_realizacao_na_data_planejada_dispensa_motivo() -> None:
    avaliar_realizacao(data_planejada=PLANEJADA, data_real=PLANEJADA, hoje=PLANEJADA, motivo="")


def test_realizacao_em_outra_data_exige_motivo() -> None:
    antes = PLANEJADA - timedelta(days=2)
    with pytest.raises(ErroDeRegra) as sem_motivo:
        avaliar_realizacao(data_planejada=PLANEJADA, data_real=antes, hoje=PLANEJADA, motivo="  ")
    assert (sem_motivo.value.codigo, sem_motivo.value.campo) == ("VALIDATION_ERROR", "motivo")

    avaliar_realizacao(data_planejada=PLANEJADA, data_real=antes, hoje=PLANEJADA, motivo="Adiantado")


def test_realizacao_com_data_futura_e_recusada() -> None:
    with pytest.raises(ErroDeRegra) as futura:
        avaliar_realizacao(
            data_planejada=PLANEJADA, data_real=PLANEJADA + timedelta(days=1), hoje=PLANEJADA, motivo="x"
        )
    assert futura.value.codigo == "DATA_FUTURA"


# --- avisos_de_realizacao_devidos ---

SEM_MARCAS: dict[EtapaDeAviso, date | None] = dict.fromkeys(EtapaDeAviso)


@pytest.mark.parametrize(
    ("dias_depois", "esperadas"),
    [
        (-1, ()),
        (0, (EtapaDeAviso.NA_DATA,)),
        (1, (EtapaDeAviso.NA_DATA, EtapaDeAviso.UM_DIA)),
        (2, (EtapaDeAviso.NA_DATA, EtapaDeAviso.UM_DIA)),
        (3, (EtapaDeAviso.NA_DATA, EtapaDeAviso.UM_DIA, EtapaDeAviso.TRES_DIAS)),
        (10, (EtapaDeAviso.NA_DATA, EtapaDeAviso.UM_DIA, EtapaDeAviso.TRES_DIAS)),
    ],
)
def test_etapas_devidas_sem_marcas(dias_depois: int, esperadas: tuple[EtapaDeAviso, ...]) -> None:
    hoje = PLANEJADA + timedelta(days=dias_depois)

    assert avisos_de_realizacao_devidos(data_do_evento=PLANEJADA, hoje=hoje, marcas=SEM_MARCAS) == esperadas


def test_etapa_ja_marcada_nao_se_repete() -> None:
    marcas = {**SEM_MARCAS, EtapaDeAviso.NA_DATA: PLANEJADA}

    devidas = avisos_de_realizacao_devidos(
        data_do_evento=PLANEJADA, hoje=PLANEJADA + timedelta(days=1), marcas=marcas
    )

    assert devidas == (EtapaDeAviso.UM_DIA,)


# --- avaliar e acoes_disponiveis ---

PROPONENTE = uuid.uuid7()
OUTRO = uuid.uuid7()


def _fatos(
    ator: uuid.UUID = OUTRO,
    situacao: SituacaoDoEvento | None = S.EM_APROVACAO,
    *,
    le_gestao: bool = True,
    tem_cargo: bool = True,
    propor: bool = False,
    aprovar: bool = False,
    cancelar: bool = False,
    admin: bool = False,
    envolve_custo: bool = True,
    tem_orcamento: bool = False,
) -> FatosDoEvento:
    return FatosDoEvento(
        ator_id=ator,
        le_gestao=le_gestao,
        tem_cargo_ativo=tem_cargo,
        e_admin=admin,
        pode_propor=propor,
        pode_aprovar=aprovar,
        pode_cancelar=cancelar,
        proponente_id=PROPONENTE if situacao is not None else None,
        situacao=situacao,
        envolve_custo=envolve_custo,
        tem_orcamento=tem_orcamento,
    )


def test_propor_exige_leitura_de_gestao_e_a_permissao() -> None:
    assert avaliar(C.PROPOR, _fatos(situacao=None, propor=True)).pode
    assert avaliar(C.PROPOR, _fatos(situacao=None)).erro == "PERMISSION_DENIED"
    assert avaliar(C.PROPOR, _fatos(situacao=None, propor=True, le_gestao=False)).erro == "PERMISSION_DENIED"


@pytest.mark.parametrize("comando", [C.EDITAR, C.CONFIRMAR_REALIZACAO])
def test_proponente_ou_aprovador_de_eventos(comando: ComandoDoEvento) -> None:
    situacao = S.PUBLICADO
    assert avaliar(comando, _fatos(PROPONENTE, situacao)).pode
    assert avaliar(comando, _fatos(OUTRO, situacao, aprovar=True)).pode
    assert avaliar(comando, _fatos(OUTRO, situacao, cancelar=True)).erro == "PERMISSION_DENIED"
    assert avaliar(comando, _fatos(OUTRO, situacao)).erro == "PERMISSION_DENIED"


def test_reabrir_e_do_proponente_ou_do_aprovador_e_so_em_recusado() -> None:
    assert avaliar(C.REABRIR, _fatos(PROPONENTE, S.RECUSADO)).pode
    assert avaliar(C.REABRIR, _fatos(OUTRO, S.RECUSADO, aprovar=True)).pode
    assert avaliar(C.REABRIR, _fatos(OUTRO, S.RECUSADO)).erro == "PERMISSION_DENIED"
    assert avaliar(C.REABRIR, _fatos(PROPONENTE, S.EM_APROVACAO)).erro == "NAO_ESTA_RECUSADO"


def test_admin_realiza_e_cancela_evento_de_outra_pessoa() -> None:
    assert avaliar(C.CONFIRMAR_REALIZACAO, _fatos(OUTRO, S.PUBLICADO, admin=True)).pode
    assert avaliar(C.CANCELAR, _fatos(OUTRO, S.PUBLICADO, admin=True)).pode


def test_cancelar_e_do_proponente_ou_de_quem_tem_a_permissao() -> None:
    assert avaliar(C.CANCELAR, _fatos(PROPONENTE)).pode
    assert avaliar(C.CANCELAR, _fatos(OUTRO, cancelar=True)).pode
    assert avaliar(C.CANCELAR, _fatos(OUTRO, aprovar=True)).erro == "PERMISSION_DENIED"


def test_orcamento_so_por_quem_aprova_eventos_com_custo_e_sem_outro() -> None:
    assert avaliar(C.VINCULAR_ORCAMENTO, _fatos(OUTRO, aprovar=True)).pode
    assert avaliar(C.VINCULAR_ORCAMENTO, _fatos(PROPONENTE)).erro == "PERMISSION_DENIED"
    sem_custo = _fatos(OUTRO, aprovar=True, envolve_custo=False)
    assert avaliar(C.VINCULAR_ORCAMENTO, sem_custo).erro == "EVENTO_SEM_CUSTO"
    com_orcamento = _fatos(OUTRO, aprovar=True, tem_orcamento=True)
    assert avaliar(C.VINCULAR_ORCAMENTO, com_orcamento).erro == "ORCAMENTO_JA_VINCULADO"


def test_presenca_so_de_diretor_com_cargo_e_em_publicado() -> None:
    assert avaliar(C.RESPONDER_PRESENCA, _fatos(OUTRO, S.PUBLICADO)).pode
    assert avaliar(C.RESPONDER_PRESENCA, _fatos(OUTRO, S.PUBLICADO, tem_cargo=False, admin=True)).erro == (
        "PERMISSION_DENIED"
    )
    assert avaliar(C.RESPONDER_PRESENCA, _fatos(OUTRO, S.EM_APROVACAO)).erro == "NAO_ESTA_PUBLICADO"


def test_sem_leitura_de_gestao_ninguem_age() -> None:
    for comando in ComandoDoEvento:
        fatos = _fatos(PROPONENTE, S.PUBLICADO, le_gestao=False, propor=True, aprovar=True, cancelar=True)
        assert avaliar(comando, fatos).erro == "PERMISSION_DENIED"


def test_evento_encerrado_nao_aceita_comando() -> None:
    for situacao in ENCERRADAS:
        fatos = _fatos(PROPONENTE, situacao, aprovar=True, cancelar=True, admin=True)
        assert acoes_disponiveis(fatos) == ()
        assert avaliar(C.EDITAR, fatos).erro == "EVENTO_ENCERRADO"


def test_acoes_disponiveis_por_papel() -> None:
    publicado_sem_orcamento = _fatos(PROPONENTE, S.PUBLICADO, envolve_custo=False)
    assert acoes_disponiveis(publicado_sem_orcamento) == (
        C.EDITAR,
        C.CONFIRMAR_REALIZACAO,
        C.CANCELAR,
        C.RESPONDER_PRESENCA,
    )
    aprovador_em_aprovacao = _fatos(OUTRO, S.EM_APROVACAO, aprovar=True)
    assert acoes_disponiveis(aprovador_em_aprovacao) == (C.EDITAR, C.VINCULAR_ORCAMENTO)
