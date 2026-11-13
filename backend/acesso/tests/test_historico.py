"""Histórico de usuário e de convite, com o nome de quem agiu (CA-30, CA-31)."""

import uuid
from typing import Any

import pytest
from rest_framework.test import APIClient

from acesso import public
from acesso.models import Usuario
from acesso.tests.conftest import criar_diretor
from auditoria import public as auditoria

pytestmark = pytest.mark.django_db

USUARIOS = "/api/v1/acesso/usuarios/"
CONVITES = "/api/v1/acesso/convites/"


def _erro(resposta: Any) -> tuple[int, str]:
    return int(resposta.status_code), str(resposta.json()["error"]["code"])


def test_ca30_historico_do_usuario_vem_do_mais_recente_com_o_nome_do_ator(
    client_admin: APIClient, admin: Usuario, diretor: Usuario
) -> None:
    client_admin.post(f"{USUARIOS}{diretor.id}/desativar/")
    client_admin.post(f"{USUARIOS}{diretor.id}/reativar/")

    resposta = client_admin.get(f"{USUARIOS}{diretor.id}/historico/")

    assert resposta.status_code == 200
    itens = resposta.json()
    assert [i["acao"] for i in itens] == ["USUARIO_REATIVADO", "USUARIO_DESATIVADO"]
    assert itens[0]["ator"] == {"id": str(admin.id), "nome": "Ana Admin"}
    assert set(itens[0]) == {"acao", "ator", "justificativa", "criado_em"}
    assert itens[0]["criado_em"] >= itens[1]["criado_em"]


def test_ca30_acao_do_sistema_tem_ator_nulo_e_o_historico_nao_traz_dados(
    client_admin: APIClient, admin: Usuario
) -> None:
    # O admin foi criado por comando no servidor: a auditoria dele não tem ator.
    resposta = client_admin.get(f"{USUARIOS}{admin.id}/historico/")

    (item,) = resposta.json()
    assert item["acao"] == "ADMIN_CRIADO_POR_COMANDO"
    assert item["ator"] is None
    assert "dados" not in item


def test_historico_de_usuario_inexistente_e_404(client_admin: APIClient) -> None:
    assert _erro(client_admin.get(f"{USUARIOS}{uuid.uuid4()}/historico/")) == (404, "NOT_FOUND")


def test_ca31_quem_nao_e_admin_nao_ve_o_historico_do_usuario(
    client_diretor: APIClient, client: APIClient, diretor: Usuario
) -> None:
    assert _erro(client_diretor.get(f"{USUARIOS}{diretor.id}/historico/")) == (403, "PERMISSION_DENIED")
    assert _erro(client.get(f"{USUARIOS}{diretor.id}/historico/")) == (401, "NOT_AUTHENTICATED")


def test_ca30_historico_do_convite_mostra_gerado_e_revogado_com_o_nome_de_quem_agiu(
    client_admin: APIClient,
) -> None:
    convite_id = client_admin.post(CONVITES).json()["id"]
    client_admin.post(f"{CONVITES}{convite_id}/revogar/")

    resposta = client_admin.get(f"{CONVITES}{convite_id}/historico/")

    assert resposta.status_code == 200
    assert [i["acao"] for i in resposta.json()] == ["CONVITE_REVOGADO", "CONVITE_GERADO"]
    assert {i["ator"]["nome"] for i in resposta.json()} == {"Ana Admin"}


def test_historico_de_convite_inexistente_e_404(client_admin: APIClient) -> None:
    assert _erro(client_admin.get(f"{CONVITES}{uuid.uuid4()}/historico/")) == (404, "NOT_FOUND")


def test_ca31_quem_nao_gerencia_convites_nao_ve_o_historico_do_convite(
    client_admin: APIClient, client_diretor: APIClient, client: APIClient
) -> None:
    convite_id = client_admin.post(CONVITES).json()["id"]

    assert _erro(client_diretor.get(f"{CONVITES}{convite_id}/historico/")) == (403, "PERMISSION_DENIED")
    assert _erro(client.get(f"{CONVITES}{convite_id}/historico/")) == (401, "NOT_AUTHENTICATED")


def test_historico_com_nomes_da_api_publica_devolve_dataclasses_sem_dados(
    admin: Usuario,
) -> None:
    bia = criar_diretor("bia")
    item = uuid.uuid4()
    auditoria.registrar(ator_id=admin.id, acao="PRIMEIRA", item_tipo="coisa", item_id=item, dados={"x": 1})
    auditoria.registrar(ator_id=bia.id, acao="SEGUNDA", item_tipo="coisa", item_id=item)
    auditoria.registrar(ator_id=None, acao="TERCEIRA", item_tipo="coisa", item_id=item)

    historico = public.historico_com_nomes("coisa", item)

    assert [r.acao for r in historico] == ["TERCEIRA", "SEGUNDA", "PRIMEIRA"]
    assert historico[0].ator is None
    ator = historico[1].ator
    assert ator is not None
    assert (ator.id, ator.nome) == (bia.id, "Diretor bia")
    assert not hasattr(historico[2], "dados")
