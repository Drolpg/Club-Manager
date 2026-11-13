"""`permissoes` publica eventos de integração (ADR-003): classificação e concessão individual alteradas."""

import uuid
from typing import Any

import pytest

from kernel import events
from kernel.errors import BusinessError
from permissoes import public
from permissoes.catalogo import CONVITES_GERENCIAR
from permissoes.domain.resolucao import ACESSO_TOTAL
from permissoes.models import Cargo, Classificacao, Setor
from permissoes.services import classificacao, concessoes
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db


@pytest.fixture
def recebidos(tratadores_de_eventos: None) -> list[Any]:
    events.unsubscribe_all_for_tests()
    lista: list[Any] = []
    events.subscribe(public.ClassificacaoAlterada, lista.append)
    events.subscribe(public.ConcessaoIndividualAlterada, lista.append)
    return lista


def _cargo(nome: str = "Tesoureiro") -> uuid.UUID:
    return Cargo.objects.get(nome=nome).id


def _setor(nome: str = "Financeiro") -> uuid.UUID:
    return Setor.objects.get(nome=nome).id


def test_classificar_publica_classificacao_alterada(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    classificacao.classificar(admin.id, diretor.id, _cargo(), [_setor()])

    assert recebidos == [public.ClassificacaoAlterada(usuario_id=diretor.id)]


def test_reclassificar_publica_de_novo(recebidos: list[Any], admin: Usuario, diretor: Usuario) -> None:
    classificacao.classificar(admin.id, diretor.id, _cargo(), [_setor()])
    classificacao.classificar(admin.id, diretor.id, _cargo("Diretor"), [])

    assert recebidos == [public.ClassificacaoAlterada(usuario_id=diretor.id)] * 2


def test_tirar_o_cargo_de_quem_tinha_publica(recebidos: list[Any], admin: Usuario, diretor: Usuario) -> None:
    classificacao.classificar(admin.id, diretor.id, _cargo(), [])
    recebidos.clear()

    classificacao.classificar(admin.id, diretor.id, None, [])

    assert recebidos == [public.ClassificacaoAlterada(usuario_id=diretor.id)]


def test_tirar_o_cargo_de_quem_nao_tinha_nao_publica(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    classificacao.classificar(admin.id, diretor.id, None, [])

    assert recebidos == []


def test_classificacao_recusada_nao_publica(recebidos: list[Any], admin: Usuario, diretor: Usuario) -> None:
    with pytest.raises(BusinessError):
        classificacao.classificar(admin.id, diretor.id, None, [_setor()])

    assert recebidos == []


def test_o_erro_do_tratador_desfaz_a_classificacao(
    admin: Usuario, diretor: Usuario, tratadores_de_eventos: None
) -> None:
    def quebra(evento: Any) -> None:
        raise RuntimeError("falhou")

    events.subscribe(public.ClassificacaoAlterada, quebra)

    with pytest.raises(RuntimeError):
        classificacao.classificar(admin.id, diretor.id, _cargo(), [])

    assert not Classificacao.objects.filter(usuario_id=diretor.id).exists()


def test_conceder_a_um_usuario_publica_concessao_individual_alterada(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert recebidos == [
        public.ConcessaoIndividualAlterada(
            usuario_id=diretor.id, permissao=CONVITES_GERENCIAR, concedida=True
        )
    ]


def test_conceder_o_que_o_usuario_ja_tem_nao_publica(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    recebidos.clear()

    _, criada = concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert criada is False
    assert recebidos == []


def test_revogar_de_um_usuario_publica_com_concedida_falso(
    recebidos: list[Any], admin: Usuario, diretor: Usuario
) -> None:
    concessao, _ = concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    recebidos.clear()

    concessoes.revogar(admin.id, concessao.id)

    assert recebidos == [
        public.ConcessaoIndividualAlterada(
            usuario_id=diretor.id, permissao=CONVITES_GERENCIAR, concedida=False
        )
    ]


@pytest.mark.parametrize("alvo", ["CARGO", "SETOR"])
def test_conceder_e_revogar_para_cargo_ou_setor_nao_publica(
    recebidos: list[Any], admin: Usuario, alvo: str
) -> None:
    alvo_id = _cargo() if alvo == "CARGO" else _setor()

    concessao, _ = concessoes.conceder(admin.id, CONVITES_GERENCIAR, alvo, alvo_id)
    concessoes.revogar(admin.id, concessao.id)

    assert recebidos == []


def test_o_acesso_total_tambem_publica(recebidos: list[Any], admin: Usuario, diretor: Usuario) -> None:
    concessoes.conceder(admin.id, ACESSO_TOTAL, "USUARIO", diretor.id)

    assert recebidos == [
        public.ConcessaoIndividualAlterada(usuario_id=diretor.id, permissao=ACESSO_TOTAL, concedida=True)
    ]
