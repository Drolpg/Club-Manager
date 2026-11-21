"""`pode_ver_perfil` (P21, CA-04): só o dono e o admin. Nenhuma permissão do catálogo conta."""

import uuid

import pytest

from relatorios.domain.acesso_ao_perfil import pode_ver_perfil

ANA, BIA = uuid.uuid4(), uuid.uuid4()


def test_o_dono_ve_o_proprio_perfil() -> None:
    assert pode_ver_perfil(ator_id=ANA, alvo_id=ANA, ator_e_admin=False) is True


def test_o_admin_ve_o_de_outro() -> None:
    assert pode_ver_perfil(ator_id=ANA, alvo_id=BIA, ator_e_admin=True) is True


def test_o_admin_ve_o_proprio() -> None:
    assert pode_ver_perfil(ator_id=ANA, alvo_id=ANA, ator_e_admin=True) is True


def test_quem_nao_e_dono_nem_admin_nao_ve() -> None:
    assert pode_ver_perfil(ator_id=ANA, alvo_id=BIA, ator_e_admin=False) is False


@pytest.mark.parametrize("quem", ["leitura de gestão", "acesso total", "sem cargo", "inativo"])
def test_nada_alem_de_dono_ou_admin_conta(quem: str) -> None:
    """A função nem recebe cargo, permissão ou situação: o que não é dono nem admin é negado."""
    assert pode_ver_perfil(ator_id=ANA, alvo_id=BIA, ator_e_admin=False) is False, quem
