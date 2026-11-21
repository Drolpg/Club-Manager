"""Reações: uma por diretor e comunicado, entre quatro tipos fixos (cenário 6 da funcional; RF-134).

Trocar muda o tipo; retirar marca a data e sai da contagem, e a linha fica (nada é apagado).
Escolher de novo a reação que já se tem também a retira. Nenhuma reação gera notificação.
"""

import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from auditoria import public as auditoria
from comunicacao.domain.autorizacao import Comando, avaliar
from comunicacao.domain.regras import TIPOS_DE_REACAO
from comunicacao.erros import erro, invalido
from comunicacao.models import Comunicado, Reacao
from comunicacao.services import consulta
from comunicacao.services.autorizacao import Quem, exigir, exigir_leitura_de_gestao, quem
from comunicacao.services.comunicados import ITEM, bloquear


def _reacao_do_diretor(comunicado: Comunicado, diretor_id: uuid.UUID) -> Reacao | None:
    return Reacao.objects.filter(comunicado=comunicado, diretor_id=diretor_id).first()


def _ativa(reacao: Reacao | None) -> bool:
    return reacao is not None and reacao.retirada_em is None


def _retirar(ator: Quem, comunicado: Comunicado, reacao: Reacao) -> None:
    tipo = reacao.tipo
    reacao.retirada_em = timezone.now()
    reacao.save()
    auditoria.registrar(
        ator_id=ator.ator_id,
        acao="REACAO_RETIRADA",
        item_tipo=ITEM,
        item_id=comunicado.id,
        dados={"tipo": tipo},
    )


@transaction.atomic
def reagir(ator_id: uuid.UUID, comunicado_id: uuid.UUID, tipo: str) -> dict[str, Any]:
    """Registra, troca ou (se for a mesma) retira a reação. Devolve as reações do comunicado."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = bloquear(comunicado_id, ator)
    existente = _reacao_do_diretor(comunicado, ator_id)
    exigir(avaliar(Comando.REAGIR, ator.fatos(comunicado=comunicado, tem_reacao_ativa=_ativa(existente))))
    if tipo not in TIPOS_DE_REACAO:
        raise invalido({"tipo": ["Escolha ciente, de acordo, dúvida ou comemoração."]})

    if existente is None:
        Reacao.objects.create(comunicado=comunicado, diretor_id=ator_id, tipo=tipo)
        _registrar(ator_id, comunicado, "REACAO_REGISTRADA", {"tipo": tipo})
    elif not _ativa(existente):
        existente.tipo = tipo
        existente.retirada_em = None
        existente.save()
        _registrar(ator_id, comunicado, "REACAO_REGISTRADA", {"tipo": tipo})
    elif existente.tipo == tipo:
        _retirar(ator, comunicado, existente)
    else:
        antes = existente.tipo
        existente.tipo = tipo
        existente.save()
        _registrar(ator_id, comunicado, "REACAO_TROCADA", {"de": antes, "para": tipo})
    return consulta.reacoes_do_comunicado(ator_id, comunicado.id)


@transaction.atomic
def retirar(ator_id: uuid.UUID, comunicado_id: uuid.UUID) -> dict[str, Any]:
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = bloquear(comunicado_id, ator)
    existente = _reacao_do_diretor(comunicado, ator_id)
    exigir(
        avaliar(Comando.RETIRAR_REACAO, ator.fatos(comunicado=comunicado, tem_reacao_ativa=_ativa(existente)))
    )
    if existente is None:  # `avaliar` já recusou; isto é só para o tipo
        raise erro("SEM_REACAO")
    _retirar(ator, comunicado, existente)
    return consulta.reacoes_do_comunicado(ator_id, comunicado.id)


def _registrar(ator_id: uuid.UUID, comunicado: Comunicado, acao: str, dados: dict[str, Any]) -> None:
    auditoria.registrar(ator_id=ator_id, acao=acao, item_tipo=ITEM, item_id=comunicado.id, dados=dados)
