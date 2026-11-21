"""A rotina diária de `eventos` (CA-18, CA-25): cancelar pela data e avisar quem pode confirmar a realização.

Idempotente: o cancelamento muda a situação, e cada aviso tem a marca no evento e a chave na notificação. Cada
evento é tratado na própria transação; o erro de um vai para o log e não impede os outros.
"""

import logging
import uuid
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from auditoria import public as auditoria
from eventos.domain.regras import avisos_de_realizacao_devidos
from eventos.domain.situacao import SituacaoDoEvento
from eventos.models import Evento
from eventos.services import avisos, eventos

logger = logging.getLogger(__name__)

S = SituacaoDoEvento


def _inicio_do_dia(dia: date) -> datetime:
    """A meia-noite do dia no fuso do sistema: o limite de "a data do evento é antes de `dia`"."""
    return timezone.make_aware(datetime.combine(dia, time.min))


@transaction.atomic
def _avisar(evento_id: uuid.UUID, hoje: date) -> int:
    evento = Evento.objects.select_for_update().filter(pk=evento_id, situacao=S.PUBLICADO.value).first()
    if evento is None:
        return 0
    devidas = avisos_de_realizacao_devidos(
        data_do_evento=evento.data_do_evento, hoje=hoje, marcas=evento.marcas_de_aviso()
    )
    for etapa in devidas:
        evento.marcar_aviso(etapa, hoje)
        avisos.realizacao_pendente(evento, etapa.value)
        auditoria.registrar(
            ator_id=None,
            acao="AVISO_DE_REALIZACAO_ENVIADO",
            item_tipo="evento",
            item_id=evento.id,
            dados={"etapa": etapa.value, "data_do_evento": evento.data_do_evento.isoformat()},
        )
    return len(devidas)


def executar(hoje: date) -> dict[str, int]:
    contagem = {"cancelados": 0, "avisos": 0, "erros": 0}
    nao_publicados = Evento.objects.filter(
        situacao__in=[S.EM_APROVACAO.value, S.RECUSADO.value], inicio__lt=_inicio_do_dia(hoje)
    ).values_list("id", flat=True)
    for evento_id in list(nao_publicados):
        try:
            contagem["cancelados"] += int(eventos.cancelar_pelo_sistema(evento_id, hoje))
        except Exception:
            logger.exception("eventos.rotina_diaria.cancelar_falhou", extra={"evento_id": str(evento_id)})
            contagem["erros"] += 1
    publicados = Evento.objects.filter(
        situacao=S.PUBLICADO.value, inicio__lt=_inicio_do_dia(hoje + timedelta(days=1))
    ).values_list("id", flat=True)
    for evento_id in list(publicados):
        try:
            contagem["avisos"] += _avisar(evento_id, hoje)
        except Exception:
            logger.exception("eventos.rotina_diaria.avisar_falhou", extra={"evento_id": str(evento_id)})
            contagem["erros"] += 1
    return contagem
