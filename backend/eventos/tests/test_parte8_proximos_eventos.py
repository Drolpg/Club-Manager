"""Parte 8: `eventos.public.proximos_eventos`, os próximos do dashboard (H3; CA-09).

Só leitura: não confere quem pergunta (é do serviço de `relatorios`). Os eventos são criados direto no modelo
do próprio módulo, em qualquer situação.
"""

from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from eventos import public
from eventos.models import Evento
from eventos.tests.conftest import categoria, diretor
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db


def _evento(prop: Usuario, titulo: str, inicio: datetime, situacao: str = "PUBLICADO") -> Evento:
    encerramento: dict[str, object] = {}
    if situacao == "CANCELADO":
        encerramento = {"cancelado_em": timezone.now(), "cancelamento_motivo": "Chuva"}
    if situacao == "REALIZADO":
        encerramento = {"realizado_em_data": timezone.localdate(), "realizado_em": timezone.now()}
    return Evento.objects.create(
        **encerramento,
        titulo=titulo,
        inicio=inicio,
        local="Campo",
        categoria=categoria(),
        categoria_nome="Jogo",
        proponente_id=prop.id,
        envolve_custo=False,
        situacao=situacao,
    )


def _hoje_as(hora: int) -> datetime:
    return timezone.make_aware(datetime.combine(timezone.localdate(), time(hora, 0)))


def test_publicados_a_partir_do_comeco_de_hoje_em_ordem_de_inicio() -> None:
    prop = diretor("prop")
    hoje_cedo = _evento(prop, "Hoje cedo", _hoje_as(0))
    depois = _evento(prop, "Depois", _hoje_as(10) + timedelta(days=3))
    amanha = _evento(prop, "Amanhã", _hoje_as(9) + timedelta(days=1))
    _evento(prop, "Ontem", _hoje_as(20) - timedelta(days=1))
    _evento(prop, "Em aprovação", _hoje_as(10) + timedelta(days=2), "EM_APROVACAO")
    _evento(prop, "Cancelado", _hoje_as(10) + timedelta(days=2), "CANCELADO")
    _evento(prop, "Recusado", _hoje_as(10) + timedelta(days=2), "RECUSADO")
    _evento(prop, "Realizado", _hoje_as(23), "REALIZADO")

    proximos = public.proximos_eventos(timezone.localdate())

    assert [e.id for e in proximos] == [hoje_cedo.id, amanha.id, depois.id]
    assert (proximos[1].titulo, proximos[1].categoria_nome) == ("Amanhã", "Jogo")
    assert proximos[1].inicio == amanha.inicio


def test_limite_de_cinco_por_padrao() -> None:
    prop = diretor("prop")
    for dia in range(1, 8):
        _evento(prop, f"Jogo {dia}", _hoje_as(10) + timedelta(days=dia))

    assert len(public.proximos_eventos(timezone.localdate())) == 5
    assert len(public.proximos_eventos(timezone.localdate(), limite=2)) == 2
