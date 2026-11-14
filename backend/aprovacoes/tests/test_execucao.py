"""Execução, encerramento e isolamento entre tipos (CA-15, CA-18, CA-34; INV-SOL-08, INV-SOL-09).

Só o módulo dono põe a solicitação em execução e a encerra, pela API pública; não há rota para isso.
"""

import uuid
from typing import Any

import grimp
import pytest
from django.urls import get_resolver
from rest_framework.test import APIClient

from aprovacoes import public
from aprovacoes.tests.conftest import (
    APROVAR_TESTE,
    SOLICITACOES,
    TIPO,
    TipoDeTeste,
    com_cargo,
    enviada,
    levar_a,
    pedido,
    preparar_pedido,
)
from auditoria import public as auditoria
from kernel.errors import BusinessError
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def solicitante(tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario) -> Usuario:
    return diretor_com_cargo


def _codigo(funcao: Any, *args: Any, **kwargs: Any) -> tuple[int, str]:
    with pytest.raises(BusinessError) as erro:
        funcao(*args, **kwargs)
    return erro.value.status, erro.value.code


def _acoes(solicitacao_id: uuid.UUID) -> list[tuple[str, uuid.UUID | None]]:
    return [(r.acao, r.ator_id) for r in auditoria.historico_do_item("solicitacao", solicitacao_id)]


# --- iniciar a execução ---


def test_o_modulo_dono_poe_a_aprovada_em_execucao(solicitante: Usuario, tipo_de_teste: TipoDeTeste) -> None:
    solicitacao = levar_a(enviada(solicitante), "APROVADA", avisos=tipo_de_teste.recebidas)
    quem_enviou_o_recurso = com_cargo("tesoureiro")

    public.iniciar_execucao(solicitacao.id, ator_id=quem_enviou_o_recurso.id)

    assert public.situacao_de(solicitacao.id) == public.Situacao.EM_EXECUCAO
    assert _acoes(solicitacao.id)[-1] == ("SOLICITACAO_EM_EXECUCAO", quem_enviou_o_recurso.id)
    # Quem pediu a mudança foi o próprio módulo dono: ele não é avisado de volta.
    assert tipo_de_teste.recebidas == []


def test_sem_ator_a_execucao_fica_registrada_como_do_sistema(solicitante: Usuario) -> None:
    solicitacao = levar_a(enviada(solicitante), "APROVADA")

    public.iniciar_execucao(solicitacao.id)

    assert _acoes(solicitacao.id)[-1] == ("SOLICITACAO_EM_EXECUCAO", None)


@pytest.mark.parametrize(
    "situacao", ["EM_ANALISE", "RETIRADA", "CONTESTADA", "RECUSADA", "EM_EXECUCAO", "ENCERRADA", "CANCELADA"]
)
def test_so_a_aprovada_entra_em_execucao(solicitante: Usuario, situacao: str) -> None:
    solicitacao = levar_a(enviada(solicitante), situacao)

    assert _codigo(public.iniciar_execucao, solicitacao.id) == (422, "NAO_ESTA_APROVADA")
    assert public.situacao_de(solicitacao.id) == situacao


# --- encerrar ---


@pytest.mark.parametrize("situacao", ["APROVADA", "EM_EXECUCAO"])
def test_o_modulo_dono_encerra_a_aprovada_ou_em_execucao(solicitante: Usuario, situacao: str) -> None:
    solicitacao = levar_a(enviada(solicitante), situacao)

    public.encerrar(solicitacao.id, ator_id=solicitante.id)

    assert public.situacao_de(solicitacao.id) == public.Situacao.ENCERRADA
    assert _acoes(solicitacao.id)[-1] == ("SOLICITACAO_ENCERRADA", solicitante.id)


@pytest.mark.parametrize(
    "situacao", ["EM_ANALISE", "RETIRADA", "CONTESTADA", "RECUSADA", "ENCERRADA", "CANCELADA"]
)
def test_inv_sol_08_so_aprovada_ou_em_execucao_encerra(solicitante: Usuario, situacao: str) -> None:
    solicitacao = levar_a(enviada(solicitante), situacao)

    assert _codigo(public.encerrar, solicitacao.id) == (422, "NAO_PODE_ENCERRAR")


# --- CA-15 pelo caminho real ---


@pytest.mark.parametrize(
    ("acao", "corpo", "codigo"),
    [
        ("editar", {"conteudo": pedido()}, "NAO_PODE_EDITAR"),
        ("retirar", {}, "NAO_ESTA_EM_ANALISE"),
        ("cancelar", {"motivo": "Desisti"}, "NAO_PODE_CANCELAR"),
    ],
)
def test_ca15_inv_sol_09_depois_de_iniciada_a_execucao_nao_edita_nao_retira_nem_cancela(
    solicitante: Usuario, acao: str, corpo: dict[str, Any], codigo: str
) -> None:
    solicitacao = levar_a(enviada(solicitante), "APROVADA")
    public.iniciar_execucao(solicitacao.id)

    resposta = apoio.cliente_de(solicitante).post(
        f"{SOLICITACOES}{solicitacao.id}/{acao}/", corpo, format="json"
    )

    assert (resposta.status_code, resposta.json()["error"]["code"]) == (422, codigo)
    assert public.situacao_de(solicitacao.id) == public.Situacao.EM_EXECUCAO


# --- CA-18: não há rota ---


@pytest.mark.parametrize(
    "rota", ["iniciar_execucao", "iniciar-execucao", "executar", "execucao", "encerrar", "encerramento"]
)
def test_ca18_nenhuma_rota_poe_em_execucao_ou_encerra(
    solicitante: Usuario, client_admin: APIClient, rota: str
) -> None:
    solicitacao = levar_a(enviada(solicitante), "APROVADA")

    resposta = client_admin.post(f"{SOLICITACOES}{solicitacao.id}/{rota}/")

    assert resposta.status_code in (404, 405)
    assert public.situacao_de(solicitacao.id) == public.Situacao.APROVADA


def test_ca18_nenhum_nome_de_rota_fala_de_execucao_ou_encerramento() -> None:
    nomes = [nome for nome in get_resolver().reverse_dict if isinstance(nome, str)]

    assert not [nome for nome in nomes if "aprovacoes" in nome and ("execu" in nome or "encerr" in nome)]


# --- situacao_de ---


def test_situacao_de_solicitacao_inexistente() -> None:
    assert _codigo(public.situacao_de, uuid.uuid7()) == (404, "NOT_FOUND")
    assert _codigo(public.iniciar_execucao, uuid.uuid7()) == (404, "NOT_FOUND")
    assert _codigo(public.encerrar, uuid.uuid7()) == (404, "NOT_FOUND")


# --- CA-34: cada módulo recebe só os avisos do próprio tipo ---


def test_ca34_com_dois_tipos_cada_modulo_recebe_so_os_avisos_do_seu(
    solicitante: Usuario, tipo_de_teste: TipoDeTeste
) -> None:
    do_outro_modulo: list[public.MudancaDeSolicitacao] = []
    public.registrar_tipo(
        codigo="outro.pedido",
        nome="Pedido de outro módulo",
        permissao_de_aprovar=APROVAR_TESTE,
        tem_valor=True,
        preparar=preparar_pedido,
        ao_mudar=do_outro_modulo.append,
    )
    try:
        deste = enviada(solicitante, TIPO)
        do_outro = enviada(solicitante, "outro.pedido")
        levar_a(deste, "APROVADA")
        levar_a(do_outro, "RECUSADA")
        apoio.cliente_de(solicitante).post(
            f"{SOLICITACOES}{do_outro.id}/cancelar/", {"motivo": "Não precisa"}
        )
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("outro.pedido")

    assert {(m.solicitacao_id, m.acontecimento) for m in tipo_de_teste.recebidas} == {
        (deste.id, public.Acontecimento.APROVADA)
    }
    assert [(m.solicitacao_id, m.acontecimento) for m in do_outro_modulo] == [
        (do_outro.id, public.Acontecimento.RECUSADA),
        (do_outro.id, public.Acontecimento.CANCELADA),
    ]
    assert {m.tipo for m in do_outro_modulo} == {"outro.pedido"}


def test_ca34_o_motor_nao_importa_financeiro_nem_eventos() -> None:
    grafo = grimp.build_graph("aprovacoes", "financeiro", "eventos")

    importados = {
        importado
        for modulo in grafo.find_descendants("aprovacoes") | {"aprovacoes"}
        for importado in grafo.find_modules_directly_imported_by(modulo)
    }

    assert not [m for m in importados if m.split(".")[0] in ("financeiro", "eventos")]
