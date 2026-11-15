"""Rotina diária idempotente de geração de recorrências e monitoramento de cobranças."""

from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from acesso import public as acesso
from auditoria import public as auditoria
from financeiro.domain.competencia import (
    Periodicidade,
    RecorrenciaParaGeracao,
    SuspensaoParaVerificacao,
    competencias_a_gerar,
    suspensa_na_data,
)
from financeiro.domain.transicoes import SituacaoCobranca
from financeiro.models import Cobranca, Recorrencia, SituacaoSuspensao, Suspensao
from financeiro.services import avisos
from kernel.dinheiro import Dinheiro


def _gerar_para_competencia(rec: Recorrencia, codigo: str, vencimento: date, hoje: date) -> bool:
    with transaction.atomic():
        if Cobranca.objects.filter(recorrencia=rec, competencia=codigo).exists():
            return False
        try:
            with transaction.atomic():
                cobranca = Cobranca.criar(
                    devedor_id=rec.devedor_id,
                    categoria=rec.categoria,
                    descricao=rec.descricao,
                    valor=Dinheiro(rec.valor),
                    vencimento=vencimento,
                    limite_de_inadimplencia=rec.limite_de_inadimplencia,
                    chave_pix=rec.chave_pix,
                    hoje=hoje,
                    recorrencia=rec,
                    competencia=codigo,
                )
        except IntegrityError:
            return False
        auditoria.registrar(
            acao="COBRANCA_GERADA_RECORRENCIA",
            ator_id=None,
            item_tipo="cobranca",
            item_id=cobranca.id,
            dados={"recorrencia_id": str(rec.id), "competencia": codigo},
        )
        avisos.cobranca_criada(cobranca)
        return True


def _gerar_cobrancas_recorrentes(hoje: date) -> int:
    geradas = 0
    recorrencias = Recorrencia.objects.filter(ativa=True).select_related("categoria", "chave_pix")
    for rec in recorrencias:
        devedor = acesso.usuario_por_id(rec.devedor_id)
        if devedor is None or not devedor.ativo:
            continue
        if not rec.categoria.ativa or not rec.chave_pix.ativa:
            continue
        elegiveis = competencias_a_gerar(
            RecorrenciaParaGeracao(
                id=rec.id,
                periodicidade=Periodicidade(rec.periodicidade),
                dia_vencimento=rec.dia_vencimento,
                mes_vencimento=rec.mes_vencimento,
                antecedencia_dias=rec.antecedencia_dias,
                a_partir_de=rec.a_partir_de,
            ),
            hoje,
        )
        if not elegiveis:
            continue
        suspensoes = [
            SuspensaoParaVerificacao(
                recorrencia_id=s.recorrencia_id,
                inicio=s.inicio,
                fim=s.fim,
                vigente=True,
            )
            for s in Suspensao.objects.filter(diretor_id=rec.devedor_id, situacao=SituacaoSuspensao.VIGENTE)
        ]
        for item in elegiveis:
            if suspensa_na_data(suspensoes, rec.id, item.vencimento):
                continue
            if _gerar_para_competencia(rec, item.codigo, item.vencimento, hoje):
                geradas += 1
    return geradas


def _enviar_lembretes_3_dias(hoje: date) -> int:
    limite = hoje + timedelta(days=3)
    ids = list(
        Cobranca.objects.filter(
            situacao=SituacaoCobranca.ABERTA,
            lembrete_3_dias_em__isnull=True,
            vencimento__gt=hoje,
            vencimento__lte=limite,
        ).values_list("id", flat=True)
    )
    enviados = 0
    for cid in ids:
        with transaction.atomic():
            cobranca = Cobranca.objects.select_for_update().get(pk=cid)
            if cobranca.marcar_lembrete_3_dias(hoje):
                avisos.lembrete_3_dias(cobranca)
                enviados += 1
    return enviados


def _enviar_lembretes_vencimento(hoje: date) -> int:
    ids = list(
        Cobranca.objects.filter(
            situacao=SituacaoCobranca.ABERTA,
            lembrete_vencimento_em__isnull=True,
            vencimento=hoje,
        ).values_list("id", flat=True)
    )
    enviados = 0
    for cid in ids:
        with transaction.atomic():
            cobranca = Cobranca.objects.select_for_update().get(pk=cid)
            if cobranca.marcar_lembrete_vencimento(hoje):
                avisos.lembrete_vencimento(cobranca)
                enviados += 1
    return enviados


def _marcar_atrasadas(hoje: date) -> int:
    ids = list(
        Cobranca.objects.filter(
            situacao=SituacaoCobranca.ABERTA,
            vencimento__lt=hoje,
        ).values_list("id", flat=True)
    )
    marcadas = 0
    for cid in ids:
        with transaction.atomic():
            cobranca = Cobranca.objects.select_for_update().get(pk=cid)
            if cobranca.marcar_atraso(hoje):
                auditoria.registrar(
                    acao="COBRANCA_ATRASADA",
                    ator_id=None,
                    item_tipo="cobranca",
                    item_id=cobranca.id,
                    dados={
                        "vencimento": cobranca.vencimento.isoformat(),
                        "data_referencia": hoje.isoformat(),
                    },
                )
                avisos.cobranca_atrasada(cobranca)
                marcadas += 1
    return marcadas


def executar(hoje: date | None = None) -> dict[str, int]:
    """Executa toda a rotina diária financeira de forma idempotente para `hoje`."""
    data_ref = hoje or timezone.localdate()
    return {
        "recorrencias_geradas": _gerar_cobrancas_recorrentes(data_ref),
        "lembretes_3_dias": _enviar_lembretes_3_dias(data_ref),
        "lembretes_vencimento": _enviar_lembretes_vencimento(data_ref),
        "atrasadas": _marcar_atrasadas(data_ref),
        "convocadas": 0,
    }
