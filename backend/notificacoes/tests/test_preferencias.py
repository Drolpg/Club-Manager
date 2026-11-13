"""Preferências de alerta: padrões ligados, linha criada só ao alterar, uma por usuário (CA-16, CA-17)."""

import uuid

import pytest

from notificacoes.models import PreferenciaDeAlerta
from notificacoes.services import preferencias
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db


def test_ca16_usuario_novo_tem_as_duas_preferencias_ligadas(diretor: Usuario) -> None:
    atual = preferencias.obter(diretor.id)

    assert (atual.aviso_na_tela, atual.email_informativos) == (True, True)
    assert not PreferenciaDeAlerta.objects.exists()


def test_alterar_cria_a_linha_e_a_mudanca_vale(diretor: Usuario) -> None:
    alterada = preferencias.alterar(diretor.id, aviso_na_tela=False)

    assert (alterada.aviso_na_tela, alterada.email_informativos) == (False, True)
    assert preferencias.obter(diretor.id) == alterada
    assert PreferenciaDeAlerta.objects.count() == 1


def test_alterar_so_o_que_foi_informado(diretor: Usuario) -> None:
    preferencias.alterar(diretor.id, aviso_na_tela=False)

    preferencias.alterar(diretor.id, email_informativos=False)

    atual = preferencias.obter(diretor.id)
    assert (atual.aviso_na_tela, atual.email_informativos) == (False, False)
    assert PreferenciaDeAlerta.objects.count() == 1


def test_alterar_de_volta_para_ligado(diretor: Usuario) -> None:
    preferencias.alterar(diretor.id, aviso_na_tela=False, email_informativos=False)

    preferencias.alterar(diretor.id, aviso_na_tela=True, email_informativos=True)

    atual = preferencias.obter(diretor.id)
    assert (atual.aviso_na_tela, atual.email_informativos) == (True, True)


def test_alterar_sem_nada_a_mudar_nao_cria_linha(diretor: Usuario) -> None:
    resultado = preferencias.alterar(diretor.id)

    assert (resultado.aviso_na_tela, resultado.email_informativos) == (True, True)
    assert not PreferenciaDeAlerta.objects.exists()


def test_ca17_a_mudanca_de_um_usuario_nao_toca_a_do_outro(admin: Usuario, diretor: Usuario) -> None:
    preferencias.alterar(diretor.id, aviso_na_tela=False, email_informativos=False)

    do_admin = preferencias.obter(admin.id)

    assert (do_admin.aviso_na_tela, do_admin.email_informativos) == (True, True)


def test_preferencias_de_quem_nao_existe_devolvem_os_padroes() -> None:
    atual = preferencias.obter(uuid.uuid4())

    assert (atual.aviso_na_tela, atual.email_informativos) == (True, True)
