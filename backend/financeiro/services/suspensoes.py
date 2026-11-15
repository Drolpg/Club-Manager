"""Casos de uso de suspensão temporária de cobranças recorrentes."""

import uuid
from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from acesso import public as acesso
from auditoria import public as auditoria
from financeiro.domain.autorizacao import PERM_COBRANCAS_SUSPENDER
from financeiro.domain.competencia import Periodo
from financeiro.erros import erro, erro_validacao
from financeiro.models import Recorrencia, SituacaoSuspensao, Suspensao
from financeiro.services import autorizacao


def serializar_suspensao(
    suspensao: Suspensao,
    nomes: dict[uuid.UUID, str] | None = None,
) -> dict[str, Any]:
    """Formata uma suspensão para o contrato JSON da API."""
    if nomes is not None and suspensao.diretor_id in nomes:
        nome_diretor = nomes[suspensao.diretor_id]
    else:
        usuario = acesso.usuario_por_id(suspensao.diretor_id)
        nome_diretor = usuario.nome if usuario else "Diretor"
        if nomes is not None:
            nomes[suspensao.diretor_id] = nome_diretor
    return {
        "id": suspensao.id,
        "diretor": {"id": suspensao.diretor_id, "nome": nome_diretor},
        "recorrencia_id": suspensao.recorrencia_id,
        "inicio": suspensao.inicio,
        "fim": suspensao.fim,
        "justificativa": suspensao.justificativa,
        "situacao": suspensao.situacao,
        "criada_em": suspensao.criada_em,
        "encerrada_em": suspensao.encerrada_em,
    }


def listar(
    ator_id: uuid.UUID,
    *,
    diretor_id: uuid.UUID | None = None,
    incluir_encerradas: bool = False,
) -> list[dict[str, Any]]:
    """Lista suspensões vigentes ou todas, para leitura da gestão."""
    autorizacao.exigir_leitura_gestao(ator_id)
    qs = Suspensao.objects.all()
    if not incluir_encerradas:
        qs = qs.filter(situacao=SituacaoSuspensao.VIGENTE)
    if diretor_id is not None:
        qs = qs.filter(diretor_id=diretor_id)
    cache: dict[uuid.UUID, str] = {}
    return [serializar_suspensao(item, cache) for item in qs]


@transaction.atomic
def criar(
    ator_id: uuid.UUID,
    *,
    diretor_id: uuid.UUID,
    recorrencia_id: uuid.UUID | None,
    inicio: date,
    fim: date | None,
    justificativa: str,
) -> dict[str, Any]:
    """Cria uma suspensão temporária para impedir geração recorrente no período (CA-26, CA-27)."""
    autorizacao.exigir_permissao(ator_id, PERM_COBRANCAS_SUSPENDER)
    if not justificativa.strip():
        raise erro_validacao("justificativa", "Informe a justificativa da suspensão.")
    if acesso.usuario_por_id(diretor_id) is None:
        raise erro("NOT_FOUND")
    recorrencia: Recorrencia | None = None
    if recorrencia_id is not None:
        recorrencia = Recorrencia.objects.filter(pk=recorrencia_id).first()
        if recorrencia is None:
            raise erro("NOT_FOUND")
    try:
        periodo = Periodo(inicio=inicio, fim=fim)
    except ValueError as exc:
        raise erro_validacao("fim", str(exc)) from None

    suspensao = Suspensao.criar(
        diretor_id=diretor_id,
        recorrencia=recorrencia,
        periodo=periodo,
        justificativa=justificativa,
        criada_por_id=ator_id,
    )
    auditoria.registrar(
        acao="SUSPENSAO_CRIADA",
        ator_id=ator_id,
        item_tipo="suspensao",
        item_id=suspensao.id,
        justificativa=suspensao.justificativa,
        dados={
            "diretor_id": str(diretor_id),
            "recorrencia_id": str(recorrencia_id) if recorrencia_id else None,
            "inicio": inicio.isoformat(),
            "fim": fim.isoformat() if fim else None,
        },
    )
    return serializar_suspensao(suspensao)


@transaction.atomic
def encerrar(ator_id: uuid.UUID, suspensao_id: uuid.UUID) -> dict[str, Any]:
    """Encerra antecipadamente uma suspensão vigente."""
    autorizacao.exigir_permissao(ator_id, PERM_COBRANCAS_SUSPENDER)
    suspensao = Suspensao.objects.select_for_update().filter(pk=suspensao_id).first()
    if suspensao is None:
        raise erro("NOT_FOUND")
    suspensao.encerrar(por_id=ator_id, agora=timezone.now())
    auditoria.registrar(
        acao="SUSPENSAO_ENCERRADA",
        ator_id=ator_id,
        item_tipo="suspensao",
        item_id=suspensao.id,
    )
    return serializar_suspensao(suspensao)


def historico(ator_id: uuid.UUID, suspensao_id: uuid.UUID) -> list[auditoria.Registro]:
    """Histórico auditado da suspensão para a gestão."""
    autorizacao.exigir_leitura_gestao(ator_id)
    if not Suspensao.objects.filter(pk=suspensao_id).exists():
        raise erro("NOT_FOUND")
    return auditoria.historico_do_item("suspensao", suspensao_id)
