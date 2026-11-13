"""Despachante de eventos em processo (ADR-003): entrega síncrona, na ordem, na transação de quem publica."""

import dataclasses

import pytest
from django.db import transaction

from kernel import events
from tests.apoio import Usuario, criar_diretor

pytestmark = pytest.mark.django_db


@dataclasses.dataclass(frozen=True)
class EventoA:
    valor: int


@dataclasses.dataclass(frozen=True)
class EventoB:
    valor: int


class EventoFilho(EventoA):
    pass


@pytest.fixture(autouse=True)
def _tratadores_isolados(tratadores_de_eventos: None) -> None:
    events.unsubscribe_all_for_tests()


def test_o_tratador_recebe_o_evento_na_hora() -> None:
    recebidos: list[EventoA] = []
    events.subscribe(EventoA, recebidos.append)

    events.publish(EventoA(1))

    assert recebidos == [EventoA(1)]


def test_os_tratadores_rodam_na_ordem_do_registro() -> None:
    ordem: list[str] = []
    events.subscribe(EventoA, lambda e: ordem.append("primeiro"))
    events.subscribe(EventoA, lambda e: ordem.append("segundo"))

    events.publish(EventoA(1))

    assert ordem == ["primeiro", "segundo"]


def test_registrar_o_mesmo_tratador_duas_vezes_nao_duplica() -> None:
    recebidos: list[EventoA] = []
    events.subscribe(EventoA, recebidos.append)
    events.subscribe(EventoA, recebidos.append)

    events.publish(EventoA(1))

    assert recebidos == [EventoA(1)]


def test_tipos_diferentes_nao_se_misturam() -> None:
    de_a: list[object] = []
    de_b: list[object] = []
    events.subscribe(EventoA, de_a.append)
    events.subscribe(EventoB, de_b.append)

    events.publish(EventoB(2))

    assert (de_a, de_b) == ([], [EventoB(2)])


def test_so_o_tipo_exato_recebe_nao_a_subclasse() -> None:
    do_pai: list[object] = []
    events.subscribe(EventoA, do_pai.append)

    events.publish(EventoFilho(3))

    assert do_pai == []


def test_publicar_sem_tratador_nao_faz_nada() -> None:
    events.publish(EventoA(1))


def test_a_excecao_de_um_tratador_propaga_e_interrompe_os_seguintes() -> None:
    chamados: list[str] = []

    def quebra(evento: EventoA) -> None:
        raise RuntimeError("falhou")

    events.subscribe(EventoA, quebra)
    events.subscribe(EventoA, lambda e: chamados.append("seguinte"))

    with pytest.raises(RuntimeError, match="falhou"):
        events.publish(EventoA(1))

    assert chamados == []


def test_a_transacao_de_quem_publicou_e_desfeita_quando_o_tratador_falha() -> None:
    def quebra(evento: EventoA) -> None:
        raise RuntimeError("falhou")

    events.subscribe(EventoA, quebra)

    def publicar_depois_de_criar() -> None:
        with transaction.atomic():
            criar_diretor("luiz")
            events.publish(EventoA(1))

    with pytest.raises(RuntimeError):
        publicar_depois_de_criar()

    assert not Usuario.objects.filter(nome_de_usuario="luiz").exists()


def test_o_tratador_roda_dentro_da_transacao_de_quem_publicou() -> None:
    dentro: list[bool] = []
    events.subscribe(EventoA, lambda e: dentro.append(transaction.get_connection().in_atomic_block))

    events.publish(EventoA(1))

    assert dentro == [True]


def test_unsubscribe_all_for_tests_remove_todos_os_tratadores() -> None:
    recebidos: list[object] = []
    events.subscribe(EventoA, recebidos.append)

    events.unsubscribe_all_for_tests()
    events.publish(EventoA(1))

    assert recebidos == []


def test_a_copia_do_registro_nao_acompanha_mudancas_posteriores() -> None:
    recebidos: list[object] = []
    events.subscribe(EventoA, recebidos.append)
    guardado = events.copiar_registro()

    events.unsubscribe_all_for_tests()
    events.restaurar_registro(guardado)
    events.publish(EventoA(1))

    assert recebidos == [EventoA(1)]
