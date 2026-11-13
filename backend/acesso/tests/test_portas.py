"""As portas de `acesso` (adendo 1 da ADR-003): padrão seguro, substituição e restauração.

Os testes de comportamento padrão chamam `restaurar_portas()`. A fixture guarda o estado registrado por
`permissoes` (no `ready`) e o devolve no fim, para os testes seguintes não dependerem da ordem.
"""

import dataclasses
import uuid
from collections.abc import Collection

import pytest
from rest_framework.test import APIClient

from acesso import portas, public
from acesso.models import Usuario
from acesso.tests.conftest import criar_diretor

pytestmark = pytest.mark.django_db

CONVITES = "/api/v1/acesso/convites/"
USUARIOS = "/api/v1/acesso/usuarios/"


@pytest.fixture
def portas_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    # O monkeypatch troca o estado por uma cópia e o desfaz no fim, devolvendo as portas de `permissoes`.
    monkeypatch.setattr(portas, "_estado", dataclasses.replace(portas._estado))
    public.restaurar_portas()


def test_padrao_convites_sao_so_do_admin(
    portas_padrao: None, client_admin: APIClient, client_diretor: APIClient
) -> None:
    assert client_admin.post(CONVITES).status_code == 201
    assert client_admin.get(CONVITES).status_code == 200
    assert client_diretor.post(CONVITES).status_code == 403
    assert client_diretor.get(CONVITES).status_code == 403


def test_padrao_a_porta_de_convites_so_aceita_admin_ativo(
    portas_padrao: None, admin: Usuario, diretor: Usuario
) -> None:
    assert public.pode_gerenciar_convites(admin.id) is True
    assert public.pode_gerenciar_convites(diretor.id) is False
    assert public.pode_gerenciar_convites(uuid.uuid4()) is False


def test_padrao_ninguem_tem_cargo(portas_padrao: None, client_admin: APIClient, diretor: Usuario) -> None:
    lista = client_admin.get(USUARIOS).json()

    assert [u["tem_cargo"] for u in lista] == [False] * len(lista)
    assert public.usuarios_com_cargo([diretor.id]) == set()


def test_registrar_portas_substitui_so_a_informada_e_restaurar_volta_ao_padrao(
    portas_padrao: None, client_diretor: APIClient, diretor: Usuario
) -> None:
    public.registrar_portas(pode_gerenciar_convites=lambda usuario_id: usuario_id == diretor.id)

    liberado = client_diretor.post(CONVITES).status_code
    ainda_sem_cargo = public.usuarios_com_cargo([diretor.id])
    public.restaurar_portas()

    assert (liberado, ainda_sem_cargo) == (201, set())
    assert client_diretor.post(CONVITES).status_code == 403


def test_a_lista_consulta_a_porta_uma_vez_para_todos_os_usuarios(
    portas_padrao: None, client_admin: APIClient
) -> None:
    for nome in ("carla", "davi", "elisa"):
        criar_diretor(nome)
    davi = Usuario.objects.get(nome_de_usuario="davi").id
    chamadas: list[list[uuid.UUID]] = []

    def com_cargo(usuario_ids: Collection[uuid.UUID]) -> set[uuid.UUID]:
        chamadas.append(list(usuario_ids))
        return {uid for uid in usuario_ids if uid == davi}

    public.registrar_portas(usuarios_com_cargo=com_cargo)
    lista = client_admin.get(USUARIOS).json()

    assert len(chamadas) == 1
    assert len(chamadas[0]) == len(lista) == 4
    assert {u["nome_de_usuario"]: u["tem_cargo"] for u in lista} == {
        "ana.admin": False,
        "carla": False,
        "davi": True,
        "elisa": False,
    }
