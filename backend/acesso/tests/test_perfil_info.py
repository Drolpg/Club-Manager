"""`acesso.public.dados_do_perfil`: os dados do perfil, sem vazar campo do modelo (D3)."""

import dataclasses
import uuid

import pytest

from acesso import public
from acesso.models import Situacao, Usuario
from tests import apoio

pytestmark = pytest.mark.django_db


def test_devolve_os_dados_do_perfil_de_um_ativo(diretor: Usuario) -> None:
    perfil = public.dados_do_perfil(diretor.id)

    assert perfil is not None
    assert perfil.id == diretor.id
    assert perfil.nome == diretor.nome
    assert perfil.nome_de_usuario == diretor.nome_de_usuario
    assert perfil.email == diretor.email
    assert perfil.telefone == "11988887777"
    assert perfil.admin is False
    assert perfil.ativo is True
    assert perfil.cadastrado_em == diretor.criado_em


def test_admin_e_desativado_tambem_tem_perfil(admin: Usuario) -> None:
    desativado = apoio.criar_diretor("saiu", situacao=Situacao.INATIVO)

    do_admin = public.dados_do_perfil(admin.id)
    do_desativado = public.dados_do_perfil(desativado.id)

    assert do_admin is not None
    assert do_admin.admin is True
    assert do_desativado is not None
    assert do_desativado.ativo is False


def test_id_inexistente_devolve_none(db: None) -> None:
    assert public.dados_do_perfil(uuid.uuid4()) is None


def test_so_devolve_dataclass_sem_campo_do_modelo(diretor: Usuario) -> None:
    perfil = public.dados_do_perfil(diretor.id)

    assert perfil is not None
    assert dataclasses.is_dataclass(perfil)
    nomes = {campo.name for campo in dataclasses.fields(perfil)}
    assert nomes == {"id", "nome", "nome_de_usuario", "email", "telefone", "admin", "ativo", "cadastrado_em"}
    assert "password" not in nomes
    assert "google_sub" not in nomes


def test_usuario_info_continua_sem_telefone(diretor: Usuario) -> None:
    info = public.usuario_por_id(diretor.id)

    assert info is not None
    assert not hasattr(info, "telefone")
    assert "telefone" not in {campo.name for campo in dataclasses.fields(info)}
