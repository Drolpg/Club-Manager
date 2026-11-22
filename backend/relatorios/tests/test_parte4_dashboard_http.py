"""A rota do dashboard (CA-09 a CA-12, CA-18, CA-21), com `APIClient`.

Os lançamentos vêm das rotas do `financeiro` (`apoio_dashboard.py`). A rota exige só a sessão ativa; a escolha
entre o completo e o básico é do serviço.
"""

import json
from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from relatorios.tests.apoio_dashboard import Clube, cliente, diretor
from tests import apoio
from tests.apoio import Situacao

pytestmark = pytest.mark.django_db

ROTA = "/api/v1/relatorios/dashboard/"
_CHAVES_DO_COMPLETO = {
    "tipo",
    "mes",
    "meses",
    "do_mes",
    "hoje",
    "proximos_eventos",
    "ultimos_comunicados",
    "minhas_cobrancas",
}
_CHAVES_DO_BASICO = {"tipo", "classificacao_pendente", "minhas_cobrancas", "notificacoes_nao_lidas"}


@pytest.fixture
def clube(db: None) -> Clube:
    return Clube()


def _erro(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def test_ca12_sem_sessao_e_401() -> None:
    assert _erro(APIClient().get(ROTA)) == (401, "NOT_AUTHENTICATED")


def test_ca12_usuario_desativado_e_negado(clube: Clube) -> None:
    desativado = apoio.criar_diretor("desat.dash", Situacao.INATIVO)

    assert cliente(desativado).get(ROTA).status_code == 403


def test_ca09_e_ca21_completo_com_os_campos_declarados_e_valores_em_texto(clube: Clube) -> None:
    clube.cobranca_paga("100.00")
    clube.saida_liquidada("40.00")

    corpo = cliente(clube.fin).get(ROTA).json()

    assert set(corpo) == _CHAVES_DO_COMPLETO
    assert corpo["tipo"] == "COMPLETO"
    assert corpo["mes"] == timezone.localdate().strftime("%Y-%m")
    assert set(corpo["meses"]) == {"de", "ate"}
    assert corpo["do_mes"] == {
        "entradas": "100.00",
        "saidas": "40.00",
        "resultado": "60.00",
        "saldo_acumulado": "60.00",
        "a_receber": {"quantidade": 0, "total": "0.00"},
    }
    hoje = corpo["hoje"]
    assert set(hoje) == {
        "data",
        "comprometido",
        "saldo_livre",
        "pendencias_de_validacao",
        "pendencias_de_aprovacao",
        "prestacoes_pendentes",
        "inadimplencia",
    }
    assert hoje["saldo_livre"] == "60.00"
    assert set(hoje["pendencias_de_aprovacao"]) == {"minha_fila", "por_tipo"}
    assert set(corpo["minhas_cobrancas"]) == {"em_aberto", "atrasadas", "em_validacao", "proxima"}


def test_ca09_o_mes_pedido_muda_o_mes(clube: Clube) -> None:
    corpo = cliente(clube.fin).get(ROTA, {"mes": "2020-01"}).json()

    assert corpo["mes"] == "2020-01"
    assert corpo["do_mes"]["entradas"] == "0.00"


def test_ca09_admin_ve_o_completo(clube: Clube) -> None:
    assert cliente(clube.admin).get(ROTA).json()["tipo"] == "COMPLETO"


def test_ca11_basico_tem_so_as_quatro_chaves(clube: Clube) -> None:
    sem_cargo = apoio.criar_diretor("semcargo.dash")
    clube.cobranca("20.00", devedor=sem_cargo)

    corpo = cliente(sem_cargo).get(ROTA, {"mes": "2020-01"}).json()

    assert set(corpo) == _CHAVES_DO_BASICO
    assert corpo["tipo"] == "BASICO"
    assert corpo["classificacao_pendente"] is True
    assert corpo["minhas_cobrancas"]["em_aberto"] == {"quantidade": 1, "total": "20.00"}
    assert corpo["notificacoes_nao_lidas"] >= 1


@pytest.mark.parametrize("mes", ["2026-13", "novembro", "2026-1"])
def test_ca10_mes_invalido_e_400_no_campo(clube: Clube, mes: str) -> None:
    resposta = cliente(clube.fin).get(ROTA, {"mes": mes})

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "mes" in resposta.json()["error"]["details"]


def test_ca10_mes_futuro_e_400(clube: Clube) -> None:
    seguinte = (timezone.localdate().replace(day=28) + timedelta(days=5)).strftime("%Y-%m")

    assert _erro(cliente(clube.fin).get(ROTA, {"mes": seguinte})) == (400, "VALIDATION_ERROR")


def test_ca18_sem_comprovante_email_nem_telefone(clube: Clube) -> None:
    clube.cobranca_paga("100.00")
    clube.registrar_pagamento(clube.cobranca("30.00"))

    texto = json.dumps(cliente(clube.fin).get(ROTA).json())

    for proibido in ("comprovante", "email", "telefone", clube.devedor.email, "11988887777"):
        assert proibido not in texto


def test_nao_aceita_escrita(clube: Clube) -> None:
    leitor = diretor("leitor.http")

    assert cliente(leitor).post(ROTA, {}, format="json").status_code == 405


def test_o_esquema_openapi_traz_a_rota(clube: Clube) -> None:
    cabecalho = {"Accept": "application/vnd.oai.openapi+json"}

    caminhos = apoio.cliente_de(clube.admin).get("/api/v1/schema/", headers=cabecalho).json()["paths"]

    assert ROTA in caminhos
