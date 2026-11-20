"""Presença: "vou" ou "não vou", só em evento publicado e de diretor ativo com cargo (regra 12; CA-13, CA-14).

A resposta vale até o evento encerrar; mudar a data começa um ciclo novo (P3) sem apagar as respostas antigas.
"""

import uuid
from typing import Any

from django.db import transaction

from acesso import public as acesso
from auditoria import public as auditoria
from eventos.domain.autorizacao import avaliar
from eventos.domain.transicoes import ComandoDoEvento
from eventos.erros import erro, invalido
from eventos.models import Evento, Presenca, RespostaDePresenca
from eventos.services.autorizacao import exigir, exigir_leitura_de_gestao, fatos
from eventos.services.avisos import diretores_com_cargo
from eventos.services.eventos import bloquear


def _pessoas(ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    pessoas = []
    for usuario_id in ids:
        usuario = acesso.usuario_por_id(usuario_id)
        pessoas.append({"id": usuario_id, "nome": usuario.nome if usuario else ""})
    return sorted(pessoas, key=lambda p: str(p["nome"]).lower())


def quadro_do_evento(evento: Evento, ator_id: uuid.UUID) -> dict[str, Any]:
    """Quem vai, quem não vai e quem, entre os diretores ativos com cargo, não respondeu no ciclo atual."""
    respostas = dict(
        Presenca.objects.filter(evento=evento, ciclo=evento.ciclo_de_presenca).values_list(
            "diretor_id", "resposta"
        )
    )
    vou = [d for d, r in respostas.items() if r == RespostaDePresenca.VOU]
    nao_vou = [d for d, r in respostas.items() if r == RespostaDePresenca.NAO_VOU]
    sem_resposta = [d for d in diretores_com_cargo() if d not in respostas]
    return {
        "vou": _pessoas(vou),
        "nao_vou": _pessoas(nao_vou),
        "sem_resposta": _pessoas(sem_resposta),
        "minha": respostas.get(ator_id),
    }


def quadro(ator_id: uuid.UUID, evento_id: uuid.UUID) -> dict[str, Any]:
    exigir_leitura_de_gestao(ator_id)
    evento = Evento.objects.filter(pk=evento_id).first()
    if evento is None:
        raise erro("NOT_FOUND", "Evento não encontrado.")
    return quadro_do_evento(evento, ator_id)


@transaction.atomic
def responder(ator_id: uuid.UUID, evento_id: uuid.UUID, resposta: str) -> dict[str, Any]:
    evento = bloquear(ator_id, evento_id)
    exigir(avaliar(ComandoDoEvento.RESPONDER_PRESENCA, fatos(ator_id, evento)))
    if resposta not in RespostaDePresenca.values:
        raise invalido({"resposta": ['Responda "VOU" ou "NAO_VOU".']})
    Presenca.responder(evento, diretor_id=ator_id, resposta=resposta)
    auditoria.registrar(
        ator_id=ator_id,
        acao="PRESENCA_RESPONDIDA",
        item_tipo="evento",
        item_id=evento.id,
        dados={"resposta": resposta, "ciclo": evento.ciclo_de_presenca},
    )
    return quadro_do_evento(evento, ator_id)
