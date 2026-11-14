"""Execução e encerramento: comandados só pelo módulo dono do tipo, pela API pública, sem rota (CA-18).

O módulo dono já decidiu quem pode (quem envia o recurso, quem liquida); o motor confere a situação, audita e
não avisa o dono de volta, porque foi ele quem pediu a mudança.
"""

import uuid

from django.db import transaction

from aprovacoes.domain.transicoes import Situacao
from aprovacoes.models import Solicitacao
from aprovacoes.services.solicitacoes import ITEM_DA_AUDITORIA
from auditoria import public as auditoria
from kernel.errors import BusinessError


def _buscar(solicitacao_id: uuid.UUID, *, bloquear: bool) -> Solicitacao:
    consulta = Solicitacao.objects.select_for_update() if bloquear else Solicitacao.objects
    solicitacao = consulta.filter(pk=solicitacao_id).first()
    if solicitacao is None:
        raise BusinessError("NOT_FOUND", "Solicitação não encontrada.", status=404)
    return solicitacao


def _auditar(solicitacao: Solicitacao, acao: str, ator_id: uuid.UUID | None) -> None:
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao,
        item_tipo=ITEM_DA_AUDITORIA,
        item_id=solicitacao.id,
        dados={"versao": solicitacao.numero_da_versao_atual},
    )


@transaction.atomic
def iniciar_execucao(solicitacao_id: uuid.UUID, *, ator_id: uuid.UUID | None = None) -> Solicitacao:
    solicitacao = _buscar(solicitacao_id, bloquear=True)
    solicitacao.iniciar_execucao()
    _auditar(solicitacao, "SOLICITACAO_EM_EXECUCAO", ator_id)
    return solicitacao


@transaction.atomic
def encerrar(solicitacao_id: uuid.UUID, *, ator_id: uuid.UUID | None = None) -> Solicitacao:
    solicitacao = _buscar(solicitacao_id, bloquear=True)
    solicitacao.encerrar()
    _auditar(solicitacao, "SOLICITACAO_ENCERRADA", ator_id)
    return solicitacao


def situacao_de(solicitacao_id: uuid.UUID) -> Situacao:
    return Situacao(_buscar(solicitacao_id, bloquear=False).situacao)
