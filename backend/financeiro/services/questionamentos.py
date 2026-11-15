"""Casos de uso de questionamento de cobrança pelo devedor e decisão pelo financeiro."""

import uuid

from django.db import transaction
from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro import tipos
from financeiro.domain.autorizacao import PERM_QUESTIONAMENTOS_DECIDIR
from financeiro.domain.transicoes import ComandoCobranca
from financeiro.erros import erro
from financeiro.models import Cobranca, DecisaoQuestionamento
from financeiro.services import autorizacao, avisos
from permissoes import public as permissoes


def _obter_ou_negar_leitura(ator_id: uuid.UUID, cobranca_id: uuid.UUID) -> Cobranca:
    usuario = autorizacao.exigir_diretor_ativo(ator_id)
    cobranca = Cobranca.objects.select_for_update().filter(pk=cobranca_id).first()
    if cobranca is None:
        if not (usuario.admin or permissoes.le_gestao(ator_id)):
            raise erro("PERMISSION_DENIED")
        raise erro("NOT_FOUND")
    return cobranca


@transaction.atomic
def questionar(*, ator_id: uuid.UUID, cobranca_id: uuid.UUID, texto: str) -> Cobranca:
    """Abre um questionamento sobre a cobrança (apenas o devedor ativo)."""
    cobranca = _obter_ou_negar_leitura(ator_id, cobranca_id)
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.QUESTIONAR)
    hoje = timezone.localdate()
    quest = cobranca.questionar(texto=texto, hoje=hoje)
    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_QUESTIONADA",
        item_tipo="cobranca",
        item_id=cobranca.id,
        justificativa=quest.texto,
        dados={"questionamento_id": str(quest.id)},
    )
    avisos.cobranca_questionada(cobranca, quest)
    return cobranca


@transaction.atomic
def decidir(
    *,
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    decisao: str,
    motivo_id: uuid.UUID,
    texto: str = "",
) -> Cobranca:
    """Decide questionamento aberto com ISENTAR, CANCELAR ou MANTER (CA-33)."""
    cobranca = Cobranca.objects.select_for_update().filter(pk=cobranca_id).first()
    if cobranca is None:
        autorizacao.exigir_permissao(ator_id, PERM_QUESTIONAMENTOS_DECIDIR)
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.DECIDIR_QUESTIONAMENTO)
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_QUESTIONAMENTO_DECIDIR)
    agora = timezone.now()
    hoje = timezone.localdate()
    quest = cobranca.decidir_questionamento(
        decisao=DecisaoQuestionamento(decisao),
        por_id=ator_id,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        texto=texto,
        agora=agora,
        hoje=hoje,
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_QUESTIONAMENTO_DECIDIDO",
        item_tipo="cobranca",
        item_id=cobranca.id,
        justificativa=texto.strip() or motivo_texto,
        dados={
            "questionamento_id": str(quest.id),
            "decisao": quest.decisao,
            "motivo_id": str(motivo_id),
            "motivo_texto": motivo_texto,
        },
    )
    avisos.questionamento_decidido(cobranca, quest)
    return cobranca
