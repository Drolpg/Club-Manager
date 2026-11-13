"""`permissoes` preenche as portas de `acesso` (adendo 1 da ADR-003): convites e `tem_cargo` (CA-27)."""

from collections.abc import Iterator
from typing import Any

import pytest
from django.apps import apps
from rest_framework.test import APIClient

from acesso import public
from permissoes.catalogo import CONVITES_GERENCIAR
from permissoes.models import Cargo, Setor
from permissoes.services import classificacao, concessoes
from tests.apoio import Usuario, criar_diretor

pytestmark = pytest.mark.django_db

CONVITES = "/api/v1/acesso/convites/"
USUARIOS = "/api/v1/acesso/usuarios/"
SESSAO = "/api/v1/acesso/sessao/"
PERMISSOES = "/api/v1/permissoes/"


@pytest.fixture
def portas_padrao() -> Iterator[None]:
    """Devolve as portas ao padrão e, no fim, as registra de novo, como o `ready` faz ao iniciar."""
    public.restaurar_portas()
    try:
        yield
    finally:
        apps.get_app_config("permissoes").ready()


def _conceder(admin: Usuario, alvo_tipo: str, alvo_id: Any) -> Any:
    return concessoes.conceder(admin.id, CONVITES_GERENCIAR, alvo_tipo, alvo_id)[0]


def _classificar(admin: Usuario, usuario: Usuario, cargo: str, setor: str | None = None) -> None:
    setores = [Setor.objects.get(nome=setor).id] if setor else []
    classificacao.classificar(admin.id, usuario.id, Cargo.objects.get(nome=cargo).id, setores)


def _status(resposta: Any) -> int:
    return int(resposta.status_code)


@pytest.mark.parametrize("origem", ["USUARIO", "CARGO", "SETOR"])
def test_ca27_diretor_com_a_permissao_gera_lista_regenera_e_revoga_convites(
    admin: Usuario, diretor: Usuario, client_diretor: APIClient, origem: str
) -> None:
    _classificar(admin, diretor, "Tesoureiro", "Financeiro")
    alvo = {
        "USUARIO": diretor.id,
        "CARGO": Cargo.objects.get(nome="Tesoureiro").id,
        "SETOR": Setor.objects.get(nome="Financeiro").id,
    }[origem]
    _conceder(admin, origem, alvo)

    gerado = client_diretor.post(CONVITES)
    listado = client_diretor.get(CONVITES)
    regenerado = client_diretor.post(f"{CONVITES}{gerado.json()['id']}/regenerar/")
    revogado = client_diretor.post(f"{CONVITES}{regenerado.json()['id']}/revogar/")

    assert [_status(r) for r in (gerado, listado, regenerado, revogado)] == [201, 200, 201, 200]
    assert {c["gerado_por"]["id"] for c in listado.json()} == {str(diretor.id)}


def test_ca27_sem_a_permissao_o_sistema_nega_as_quatro_rotas(
    admin: Usuario, client_admin: APIClient, client_diretor: APIClient
) -> None:
    convite_id = client_admin.post(CONVITES).json()["id"]

    respostas = [
        client_diretor.post(CONVITES),
        client_diretor.get(CONVITES),
        client_diretor.post(f"{CONVITES}{convite_id}/regenerar/"),
        client_diretor.post(f"{CONVITES}{convite_id}/revogar/"),
    ]

    assert [_status(r) for r in respostas] == [403] * 4


def test_ca27_perder_a_permissao_vale_na_requisicao_seguinte(
    admin: Usuario, diretor: Usuario, client_diretor: APIClient
) -> None:
    concessao = _conceder(admin, "USUARIO", diretor.id)
    com = _status(client_diretor.post(CONVITES))

    concessoes.revogar(admin.id, concessao.id)

    assert (com, _status(client_diretor.post(CONVITES))) == (201, 403)


def test_ca27_a_permissao_de_convites_nao_abre_a_lista_de_usuarios(
    admin: Usuario, diretor: Usuario, client_diretor: APIClient
) -> None:
    _conceder(admin, "USUARIO", diretor.id)

    assert _status(client_diretor.get(USUARIOS)) == 403
    assert _status(client_diretor.post(f"{USUARIOS}{admin.id}/remover-admin/")) == 403


def test_o_admin_continua_gerenciando_convites_sem_concessao(client_admin: APIClient) -> None:
    assert _status(client_admin.post(CONVITES)) == 201


def test_ca07_lista_e_sessao_mostram_com_cargo_depois_de_classificar(
    admin: Usuario, diretor: Usuario, client_admin: APIClient, client_diretor: APIClient
) -> None:
    criar_diretor("outro")

    def tem_cargo() -> dict[str, bool]:
        return {u["nome_de_usuario"]: u["tem_cargo"] for u in client_admin.get(USUARIOS).json()}

    antes = tem_cargo()
    _classificar(admin, diretor, "Tesoureiro", "Financeiro")
    depois = tem_cargo()
    na_sessao = client_diretor.get(SESSAO).json()["usuario"]["tem_cargo"]
    classificacao.classificar(admin.id, diretor.id, None, [])

    assert antes == {"ana.admin": False, "bia": False, "outro": False}
    assert depois == {"ana.admin": False, "bia": True, "outro": False}
    assert na_sessao is True
    assert tem_cargo()["bia"] is False


def test_ca07_a_resposta_do_login_tambem_traz_tem_cargo(admin: Usuario, diretor: Usuario) -> None:
    _classificar(admin, diretor, "Diretor")
    client = APIClient()

    resposta = client.post(
        SESSAO, {"identificador": diretor.nome_de_usuario, "senha": "correta-bateria-grampo"}
    )

    assert resposta.json()["usuario"]["tem_cargo"] is True


def test_o_ready_de_permissoes_registra_as_portas(
    portas_padrao: None, admin: Usuario, diretor: Usuario
) -> None:
    _conceder(admin, "USUARIO", diretor.id)
    _classificar(admin, diretor, "Diretor")
    assert public.pode_gerenciar_convites(diretor.id) is False
    assert public.usuarios_com_cargo([diretor.id]) == set()

    apps.get_app_config("permissoes").ready()

    assert public.pode_gerenciar_convites(diretor.id) is True
    assert public.pode_gerenciar_convites(admin.id) is True
    assert public.usuarios_com_cargo([diretor.id, admin.id]) == {diretor.id}
