"""Parte 9: os eventos de um período, para o relatório de eventos (spec `relatorios/relatorios-pdf-e-csv`,
"Fontes de cada relatório"; CA-19).

Só leitura: a consulta não confere quem pergunta (é do catálogo de `relatorios`). As respostas de presença
são dadas com o evento no futuro e a data é movida depois, como em `test_parte6_http.py`.
"""

from datetime import date, datetime
from typing import Any

import pytest
from django.utils import timezone

from eventos import public
from eventos.models import Evento
from eventos.services import eventos, presencas
from eventos.tests.conftest import aprovar, proposta, recarregado
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

OUT = (date(2026, 10, 1), date(2026, 10, 31))


def _local(*partes: int) -> datetime:
    return timezone.make_aware(datetime(*partes))  # type: ignore[arg-type]


def _publicado(papeis: dict[str, Usuario], **mudar: Any) -> Evento:
    evento = eventos.propor(papeis["proponente"].id, **proposta(**mudar))
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    return recarregado(evento)


def _em(evento: Evento, inicio: datetime) -> Evento:
    Evento.objects.filter(pk=evento.pk).update(inicio=inicio)
    return recarregado(evento)


def test_ca19_eventos_com_data_no_periodo_com_situacao_e_presencas(papeis: dict[str, Usuario]) -> None:
    jogo = _publicado(papeis, titulo="Amistoso")
    presencas.responder(papeis["comum"].id, jogo.id, "VOU")
    presencas.responder(papeis["gastos"].id, jogo.id, "VOU")
    presencas.responder(papeis["aprovador"].id, jogo.id, "NAO_VOU")
    _em(jogo, _local(2026, 10, 10, 15))
    # O banco não deixa mudar a data de um evento cancelado: a data vem antes do cancelamento.
    festa = _em(_publicado(papeis, titulo="Festa", local="Sede"), _local(2026, 10, 20, 20))
    eventos.cancelar(papeis["proponente"].id, festa.id, motivo="Chuva forte")
    em_aprovacao = eventos.propor(papeis["proponente"].id, **proposta(titulo="Reunião"))
    _em(em_aprovacao, _local(2026, 10, 1, 0, 0))
    _em(_publicado(papeis, titulo="Fora"), _local(2026, 11, 1, 0, 0))
    _em(_publicado(papeis, titulo="Antes"), _local(2026, 9, 30, 23, 59))

    itens = public.eventos_do_periodo(*OUT)

    assert [item.titulo for item in itens] == ["Reunião", "Amistoso", "Festa"]
    reuniao, amistoso, cancelada = itens
    assert reuniao.situacao == "EM_APROVACAO"
    assert (amistoso.situacao, amistoso.vou, amistoso.nao_vou) == ("PUBLICADO", 2, 1)
    assert (amistoso.categoria, amistoso.local, amistoso.envolve_custo) == ("Jogo", "Campo do bairro", False)
    assert amistoso.proponente == papeis["proponente"].nome
    assert amistoso.inicio == _local(2026, 10, 10, 15)
    assert amistoso.id == jogo.id
    assert (cancelada.situacao, cancelada.motivo) == ("CANCELADO", "Chuva forte")
    assert amistoso.motivo == ""


def test_ca19_so_conta_as_presencas_do_ciclo_atual(papeis: dict[str, Usuario]) -> None:
    jogo = _publicado(papeis)
    presencas.responder(papeis["comum"].id, jogo.id, "VOU")
    Evento.objects.filter(pk=jogo.pk).update(ciclo_de_presenca=2)
    presencas.responder(papeis["gastos"].id, jogo.id, "NAO_VOU")
    _em(jogo, _local(2026, 10, 10, 15))

    [item] = public.eventos_do_periodo(*OUT)

    assert (item.vou, item.nao_vou) == (0, 1)


def test_periodo_sem_eventos_e_vazio(papeis: dict[str, Usuario]) -> None:
    _em(_publicado(papeis), _local(2026, 12, 5, 10))

    assert public.eventos_do_periodo(*OUT) == []
