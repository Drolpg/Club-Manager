"""Lembretes da solicitação parada (RF-121; adendo 1, A10).

Três e sete dias corridos desde a criação da versão atual. Cada aviso acontece uma vez por versão: a data
gravada na versão e a chave da notificação garantem isso, e rodar de novo não repete nada (RNF-10). Cada
solicitação é tratada numa transação própria, com a linha bloqueada, e a situação e a versão são conferidas de
novo.
"""

import uuid
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import F, Q

from aprovacoes.domain.transicoes import Situacao
from aprovacoes.models import Solicitacao, Versao
from aprovacoes.services import avisos

LEMBRETE = timedelta(days=3)
AVISO_AO_ADMIN = timedelta(days=7)


def lembrar_paradas(agora: datetime) -> int:
    """Manda os lembretes que faltam e devolve quantos mandou."""
    pendentes = (
        Versao.objects.filter(
            solicitacao__situacao=Situacao.EM_ANALISE, numero=F("solicitacao__numero_da_versao_atual")
        )
        .filter(
            Q(lembrete_em__isnull=True, criada_em__lte=agora - LEMBRETE)
            | Q(aviso_ao_admin_em__isnull=True, criada_em__lte=agora - AVISO_AO_ADMIN)
        )
        .values_list("solicitacao_id", flat=True)
    )
    return sum(_lembrar(solicitacao_id, agora) for solicitacao_id in list(pendentes))


@transaction.atomic
def _lembrar(solicitacao_id: uuid.UUID, agora: datetime) -> int:
    solicitacao = Solicitacao.objects.select_for_update().get(pk=solicitacao_id)
    if solicitacao.situacao != Situacao.EM_ANALISE:
        return 0
    versao = solicitacao.versao_atual
    mandados = 0
    if versao.lembrete_em is None and versao.criada_em <= agora - LEMBRETE:
        avisos.lembrete(solicitacao)
        versao.lembrete_em = agora
        mandados += 1
    if versao.aviso_ao_admin_em is None and versao.criada_em <= agora - AVISO_AO_ADMIN:
        avisos.parada(solicitacao)
        versao.aviso_ao_admin_em = agora
        mandados += 1
    if mandados:
        versao.save(update_fields=["lembrete_em", "aviso_ao_admin_em"])
    return mandados
