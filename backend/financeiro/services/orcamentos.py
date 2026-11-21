"""Orçamento de evento: abrir com o vínculo e cancelar junto com o evento (adendo 1 da spec técnica do M7).

O orçamento é uma solicitação de gasto comum. O que o liga ao evento é o registro `OrcamentoDeEvento`, criado
na mesma transação do envio; o conteúdo da solicitação não leva o `evento_id`.
"""

import uuid
from typing import Any

from django.db import transaction

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro.domain.transicoes import SituacaoSaida
from financeiro.models import OrcamentoDeEvento, Saida
from financeiro.services import avisos, gastos

_RECURSO_ENVIADO = (aprovacoes.Situacao.EM_EXECUCAO, aprovacoes.Situacao.ENCERRADA)


@transaction.atomic
def abrir(
    *,
    solicitante_id: uuid.UUID,
    descricao: str,
    categoria_id: uuid.UUID,
    setor_id: uuid.UUID,
    itens: list[dict[str, Any]],
    evento_id: uuid.UUID,
    aprovador_indicado_id: uuid.UUID | None = None,
    cotacao_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Envia a solicitação de gasto e grava o vínculo com o evento. `eventos` confere quem pode abrir."""
    info = gastos.abrir_solicitacao(
        solicitante_id,
        descricao=descricao,
        categoria_id=categoria_id,
        setor_id=setor_id,
        itens=itens,
        cotacao_id=cotacao_id,
        aprovador_indicado_id=aprovador_indicado_id,
    )
    OrcamentoDeEvento.objects.create(solicitacao_id=info.id, evento_id=evento_id)
    return info.id


def evento_do_orcamento(solicitacao_id: uuid.UUID) -> uuid.UUID | None:
    vinculo = OrcamentoDeEvento.objects.filter(solicitacao_id=solicitacao_id).first()
    return vinculo.evento_id if vinculo else None


@transaction.atomic
def cancelar_com_o_evento(
    solicitacao_id: uuid.UUID,
    *,
    evento_id: uuid.UUID,
    titulo_do_evento: str,
    ator_id: uuid.UUID | None,
    motivo: str,
) -> None:
    """Sem recurso enviado, cancela a solicitação (e o tratador cancela a saída que aguardava envio). Com o
    recurso enviado, nada é cancelado: a saída segue, e quem liquida é avisado. Ator nulo é o sistema.
    """
    if evento_do_orcamento(solicitacao_id) != evento_id:
        raise ValueError(f"A solicitação {solicitacao_id} não é do evento {evento_id}.")
    # A saída antes da solicitação: a mesma ordem de bloqueio do envio de recurso.
    saida = (
        Saida.objects.select_for_update()
        .filter(solicitacao_id=solicitacao_id)
        .exclude(situacao__in=[SituacaoSaida.CANCELADA.value, SituacaoSaida.ESTORNADA.value])
        .first()
    )
    situacao = aprovacoes.obter_solicitacao(solicitacao_id).situacao
    if situacao == aprovacoes.Situacao.CANCELADA:
        return
    if situacao in _RECURSO_ENVIADO:
        if saida is not None:
            auditoria.registrar(
                ator_id=ator_id,
                acao="ORCAMENTO_DE_EVENTO_CANCELADO",
                item_tipo="saida",
                item_id=saida.id,
                justificativa=motivo,
                dados={"solicitacao_id": str(solicitacao_id), "evento_id": str(evento_id)},
            )
            avisos.orcamento_de_evento_cancelado(saida, titulo_do_evento=titulo_do_evento)
        return
    aprovacoes.cancelar_pelo_dono(solicitacao_id, tipo=gastos.TIPO_GASTO, ator_id=ator_id, motivo=motivo)
