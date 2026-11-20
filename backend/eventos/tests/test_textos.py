"""Textos visíveis ao usuário seguem a linguagem ubíqua: só solicitações são aprovadas; o evento é publicado.

Achado D2 da auditoria de coerência do M8 (2026-11-20).
"""

import re

import pytest

from eventos import tipos
from eventos.models import Presenca, RespostaDePresenca
from eventos.services import eventos
from eventos.tests.conftest import aprovar, caixa, proposta, recarregado
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

_EVENTO_APROVADO = re.compile(r"\bevento\b[^.]*\baprovado\b", re.IGNORECASE)


def test_descricoes_das_notificacoes_nao_chamam_o_evento_de_aprovado() -> None:
    for codigo, (_, descricao) in tipos.TIPOS_DE_NOTIFICACAO.items():
        assert not _EVENTO_APROVADO.search(descricao), codigo
    assert tipos.TIPOS_DE_NOTIFICACAO[tipos.NOTIF_MONTAR_ORCAMENTO][1] == (
        "A solicitação de um evento com custo foi aprovada e o evento espera o orçamento."
    )


def test_aviso_de_fora_do_calendario_fala_da_solicitacao(papeis: dict[str, Usuario]) -> None:
    evento = eventos.propor(papeis["proponente"].id, **proposta())
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    Presenca.responder(recarregado(evento), diretor_id=papeis["comum"].id, resposta=RespostaDePresenca.VOU)
    dados = proposta(titulo="Amistoso remarcado")
    del dados["inicio"]

    eventos.editar(papeis["proponente"].id, evento.id, inicio=recarregado(evento).inicio, **dados)

    [aviso] = caixa(papeis["comum"], "eventos.despublicado")
    assert "até a solicitação do evento ser aprovada de novo" in aviso["texto"]
    assert not _EVENTO_APROVADO.search(aviso["texto"])
