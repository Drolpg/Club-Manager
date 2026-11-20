"""O único caminho que grava a situação do evento (INV-EVT-01).

Lê a situação das duas solicitações no motor, calcula com `situacao_do_evento` e, conforme a transição,
audita e notifica, na mesma transação de quem pediu o recálculo.
"""

import uuid

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from eventos.domain.situacao import SituacaoDoEvento, situacao_do_evento
from eventos.models import Evento, Transicao
from eventos.services import avisos

S = SituacaoDoEvento


def _situacao(solicitacao_id: uuid.UUID | None) -> str | None:
    return aprovacoes.situacao_de(solicitacao_id).value if solicitacao_id is not None else None


def recalcular(evento: Evento, *, ator_id: uuid.UUID | None) -> Transicao | None:
    """Idempotente: sem mudança, ou com o evento encerrado, não faz nada. O evento já está bloqueado."""
    if evento.encerrado or evento.solicitacao_do_evento_id is None:
        return None
    nova = situacao_do_evento(
        cancelado=False,
        realizado=False,
        situacao_da_solicitacao_do_evento=aprovacoes.situacao_de(evento.solicitacao_do_evento_id).value,
        envolve_custo=evento.envolve_custo,
        situacao_do_orcamento=_situacao(evento.solicitacao_orcamentaria_id),
    )
    transicao = evento.atualizar_situacao(nova)
    if transicao is not None:
        _registrar(evento, transicao, ator_id)
    return transicao


def _registrar(evento: Evento, transicao: Transicao, ator_id: uuid.UUID | None) -> None:
    acao = None
    if transicao.depois == S.PUBLICADO:
        acao = "EVENTO_PUBLICADO"
        avisos.publicado(evento)
    elif transicao.antes == S.PUBLICADO:
        acao = "EVENTO_DESPUBLICADO"
        avisos.despublicado(evento)
    elif transicao.depois == S.RECUSADO:
        acao = "EVENTO_RECUSADO"
    # RECUSADO → EM_APROVACAO é auditado pela reabertura (EVENTO_REABERTO), com a justificativa.
    if acao is not None:
        auditoria.registrar(
            ator_id=ator_id,
            acao=acao,
            item_tipo="evento",
            item_id=evento.id,
            dados={"de": transicao.antes.value, "para": transicao.depois.value},
        )
