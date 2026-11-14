"""Lembretes da solicitação parada (CA-32; adendo 1, A10): 3 e 7 dias corridos desde a versão atual.

O relógio é fixado na criação da versão (`timezone.now` substituído) e o serviço recebe `agora`. A versão é
imutável no banco, então o teste não a "envelhece" depois: ela já nasce no passado.
"""

from datetime import datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone

from aprovacoes import tasks
from aprovacoes.services import lembretes
from aprovacoes.tests.conftest import TipoDeTeste, enviada, levar_a, pedido
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

AGORA = timezone.now()
CAIXA = "/api/v1/notificacoes/"


def _do_tipo(usuario: Usuario, tipo: str) -> list[dict[str, Any]]:
    itens = apoio.cliente_de(usuario).get(CAIXA, {"limite": 50}).json()["itens"]
    return [n for n in itens if n["tipo"] == tipo]


def _no_passado(momento: datetime) -> Any:
    return mock.patch("django.utils.timezone.now", return_value=momento)


def _enviada_ha(solicitante: Usuario, **tempo: float) -> Any:
    with _no_passado(AGORA - timedelta(**tempo)):
        return enviada(solicitante)


@pytest.fixture
def solicitante(tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario) -> Usuario:
    return diretor_com_cargo


def test_ca32_antes_de_3_dias_ninguem_e_lembrado(solicitante: Usuario, aprovador: Usuario) -> None:
    _enviada_ha(solicitante, days=2, hours=23)

    lembretes.lembrar_paradas(AGORA)

    assert _do_tipo(aprovador, "aprovacoes.lembrete") == []


def test_ca32_aos_3_dias_corridos_quem_pode_decidir_e_lembrado(
    solicitante: Usuario, aprovador: Usuario, admin: Usuario
) -> None:
    solicitacao = _enviada_ha(solicitante, days=3)

    lembretes.lembrar_paradas(AGORA)

    (lembrete,) = _do_tipo(aprovador, "aprovacoes.lembrete")
    assert lembrete["pede_acao"] is True
    assert lembrete["caminho"] == f"/solicitacoes/{solicitacao.id}"
    assert _do_tipo(admin, "aprovacoes.parada") == []
    assert solicitacao.versao_atual.lembrete_em == AGORA
    assert solicitacao.versao_atual.aviso_ao_admin_em is None


def test_ca32_aos_7_dias_o_admin_e_avisado(solicitante: Usuario, admin: Usuario) -> None:
    solicitacao = _enviada_ha(solicitante, days=7)

    lembretes.lembrar_paradas(AGORA)

    (aviso,) = _do_tipo(admin, "aprovacoes.parada")
    assert aviso["pede_acao"] is False
    assert solicitacao.versao_atual.aviso_ao_admin_em == AGORA


def test_ca32_rodar_de_novo_nao_repete_nenhum_dos_dois(
    solicitante: Usuario, aprovador: Usuario, admin: Usuario
) -> None:
    _enviada_ha(solicitante, days=8)

    lembretes.lembrar_paradas(AGORA)
    lembretes.lembrar_paradas(AGORA)
    lembretes.lembrar_paradas(AGORA + timedelta(days=1))

    assert len(_do_tipo(aprovador, "aprovacoes.lembrete")) == 1
    assert len(_do_tipo(admin, "aprovacoes.parada")) == 1


def test_ca32_a_versao_nova_zera_a_contagem(solicitante: Usuario, aprovador: Usuario) -> None:
    solicitacao = _enviada_ha(solicitante, days=4)
    lembretes.lembrar_paradas(AGORA)
    cliente = apoio.cliente_de(solicitante)
    # A versão 2 nasce em AGORA, e não no relógio real, que anda enquanto a suíte roda.
    with _no_passado(AGORA):
        levar_a(solicitacao, "CONTESTADA")
        cliente.post(
            f"/api/v1/aprovacoes/solicitacoes/{solicitacao.id}/reenviar/",
            {"conteudo": pedido()},
            format="json",
        )

    lembretes.lembrar_paradas(AGORA + timedelta(days=2))
    assert len(_do_tipo(aprovador, "aprovacoes.lembrete")) == 1

    lembretes.lembrar_paradas(AGORA + timedelta(days=3, minutes=1))
    assert len(_do_tipo(aprovador, "aprovacoes.lembrete")) == 2


@pytest.mark.parametrize("situacao", ["CONTESTADA", "RETIRADA", "RECUSADA", "APROVADA", "CANCELADA"])
def test_so_a_solicitacao_em_analise_e_lembrada(
    solicitante: Usuario, aprovador: Usuario, situacao: str
) -> None:
    solicitacao = _enviada_ha(solicitante, days=10)
    with _no_passado(AGORA - timedelta(days=9)):
        levar_a(solicitacao, situacao)

    lembretes.lembrar_paradas(AGORA)

    assert _do_tipo(aprovador, "aprovacoes.lembrete") == []


def test_a_tarefa_so_chama_o_servico_com_o_relogio(solicitante: Usuario, aprovador: Usuario) -> None:
    _enviada_ha(solicitante, days=3, minutes=1)

    with _no_passado(AGORA):
        tasks.lembrar_solicitacoes_paradas()

    assert len(_do_tipo(aprovador, "aprovacoes.lembrete")) == 1


def test_a10_a_tarefa_roda_uma_vez_por_dia_de_manha() -> None:
    # O Celery lê a agenda da configuração do Django (config/celery.py).
    agenda = settings.CELERY_BEAT_SCHEDULE["aprovacoes.lembrar_solicitacoes_paradas"]

    assert agenda["task"] == "aprovacoes.lembrar_solicitacoes_paradas"
    assert agenda["schedule"] == crontab(minute=0, hour=8)
