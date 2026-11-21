"""Parte 7: `eventos.public.eventos_do_usuario`, a leitura que alimenta o perfil (CA-03).

Só leitura: não confere quem pergunta (é do serviço de `relatorios`). Os eventos são criados direto no
modelo do próprio módulo, em qualquer situação.
"""

import dataclasses
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from eventos import public
from eventos.models import Evento, Presenca
from eventos.tests.conftest import categoria, diretor
from kernel.errors import BusinessError
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db


def _evento(
    proponente: Usuario, titulo: str = "Amistoso", dias: int = 7, situacao: str = "PUBLICADO"
) -> Evento:
    encerramento: dict[str, object] = {}
    if situacao == "CANCELADO":
        encerramento = {"cancelado_em": timezone.now(), "cancelamento_motivo": "Chuva"}
    if situacao == "REALIZADO":
        encerramento = {"realizado_em_data": timezone.localdate(), "realizado_em": timezone.now()}
    return Evento.objects.create(
        **encerramento,
        titulo=titulo,
        inicio=timezone.now() + timedelta(days=dias),
        local="Campo",
        categoria=categoria(),
        categoria_nome="Jogo",
        proponente_id=proponente.id,
        envolve_custo=False,
        situacao=situacao,
    )


def _responder(evento: Evento, diretor_id: uuid.UUID, resposta: str = "VOU") -> None:
    Presenca.responder(Evento.objects.get(pk=evento.pk), diretor_id=diretor_id, resposta=resposta)


def test_eventos_propostos_pelo_usuario() -> None:
    ana, bia = diretor("ana"), diretor("bia")
    meu = _evento(ana, "Meu")
    _evento(bia, "Do outro")

    pagina = public.eventos_do_usuario(ana.id)

    assert [e.id for e in pagina.itens] == [meu.id]
    assert pagina.itens[0].papel == "PROPONENTE"
    assert pagina.itens[0].resposta is None
    assert pagina.tem_mais is False


def test_eventos_com_presenca_do_ciclo_atual() -> None:
    ana, bia = diretor("ana"), diretor("bia")
    evento = _evento(bia, "Do outro")
    _responder(evento, ana.id, "NAO_VOU")

    (item,) = public.eventos_do_usuario(ana.id).itens

    assert item.id == evento.id
    assert item.papel == "PRESENCA"
    assert item.resposta == "NAO_VOU"


def test_presenca_de_ciclo_antigo_nao_conta() -> None:
    ana, bia = diretor("ana"), diretor("bia")
    evento = _evento(bia)
    _responder(evento, ana.id)
    Evento.objects.get(pk=evento.pk).zerar_presencas()

    assert public.eventos_do_usuario(ana.id).itens == []


def test_papel_duplo_quando_propoe_e_responde() -> None:
    ana = diretor("ana")
    evento = _evento(ana)
    _responder(evento, ana.id, "VOU")

    (item,) = public.eventos_do_usuario(ana.id).itens

    assert item.papel == "PROPONENTE_E_PRESENCA"
    assert item.resposta == "VOU"


def test_a_presenca_de_outro_nao_aparece() -> None:
    ana, bia, caio = diretor("ana"), diretor("bia"), diretor("caio")
    evento = _evento(caio)
    _responder(evento, bia.id)

    assert public.eventos_do_usuario(ana.id).itens == []


def test_traz_titulo_data_local_categoria_e_qualquer_situacao() -> None:
    ana = diretor("ana")
    for situacao in ("EM_APROVACAO", "RECUSADO", "CANCELADO", "REALIZADO"):
        _evento(ana, situacao, situacao=situacao)

    itens = public.eventos_do_usuario(ana.id).itens

    assert {e.situacao for e in itens} == {"EM_APROVACAO", "RECUSADO", "CANCELADO", "REALIZADO"}
    assert {e.local for e in itens} == {"Campo"}
    assert {e.categoria_nome for e in itens} == {"Jogo"}
    assert all(e.inicio is not None and e.titulo for e in itens)


def test_ordem_por_data_do_mais_novo_ao_mais_antigo_e_paginacao() -> None:
    ana = diretor("ana")
    criados = [_evento(ana, f"E{n}", dias=n) for n in range(5)]
    esperado = [e.id for e in reversed(criados)]

    primeira = public.eventos_do_usuario(ana.id, limite=2)
    segunda = public.eventos_do_usuario(ana.id, antes=primeira.itens[-1].id, limite=2)
    terceira = public.eventos_do_usuario(ana.id, antes=segunda.itens[-1].id, limite=2)

    assert [e.id for e in primeira.itens] == esperado[:2]
    assert primeira.tem_mais is True
    assert [e.id for e in segunda.itens] == esperado[2:4]
    assert [e.id for e in terceira.itens] == esperado[4:]
    assert terceira.tem_mais is False


def test_cursor_inexistente_e_not_found() -> None:
    with pytest.raises(BusinessError) as falha:
        public.eventos_do_usuario(diretor("ana").id, antes=uuid.uuid4())

    assert falha.value.code == "NOT_FOUND"


def test_so_devolve_dataclass_sem_campo_do_modelo() -> None:
    ana = diretor("ana")
    _evento(ana)

    (item,) = public.eventos_do_usuario(ana.id).itens

    nomes = {c.name for c in dataclasses.fields(item)}
    assert nomes == {"id", "titulo", "inicio", "local", "categoria_nome", "situacao", "papel", "resposta"}
