"""E-mail de uma notificação. É chamado pela tarefa, depois do commit.

O e-mail é texto puro: o título no assunto e, no corpo, o texto e o link do item no site. O link exige login e
não leva token (regra 13). Nenhum dado pessoal além do que o texto já diz, e nada disso vai para o log.
"""

import logging
import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from acesso import public as acesso
from notificacoes.models import Notificacao, SituacaoDoEmail

logger = logging.getLogger(__name__)


def _corpo(notificacao: Notificacao) -> str:
    return f"{notificacao.texto}\n\n{settings.SITE_URL}{notificacao.caminho}"


def enviar(notificacao_id: uuid.UUID) -> None:
    """Envia o e-mail de uma notificação pendente. Idempotente: só a situação `PENDENTE` é enviada.

    Toda chamada que chega ao envio conta uma tentativa. Se o servidor falhar, a exceção sobe para a tarefa
    tentar de novo; a tentativa já fica gravada.
    """
    notificacao = Notificacao.objects.filter(pk=notificacao_id).first()
    if notificacao is None or notificacao.email_situacao != SituacaoDoEmail.PENDENTE:
        return
    notificacao.email_tentativas += 1
    destinatario = acesso.usuario_por_id(notificacao.destinatario_id)
    if destinatario is None or not destinatario.ativo:
        # Quem saiu do clube depois do aviso não recebe e-mail (regra 7).
        notificacao.email_situacao = SituacaoDoEmail.DISPENSADO
        notificacao.save(update_fields=["email_situacao", "email_tentativas"])
        return
    try:
        send_mail(
            subject=notificacao.titulo,
            message=_corpo(notificacao),
            from_email=None,
            recipient_list=[destinatario.email],
        )
    except Exception as erro:
        notificacao.save(update_fields=["email_tentativas"])
        # Só o ID e o tipo do erro: a mensagem do servidor pode trazer o endereço do destinatário.
        logger.warning(
            "Falha ao enviar o e-mail da notificação %s (tentativa %d): %s",
            notificacao.id,
            notificacao.email_tentativas,
            type(erro).__name__,
        )
        raise
    notificacao.email_situacao = SituacaoDoEmail.ENVIADO
    notificacao.email_enviado_em = timezone.now()
    notificacao.save(update_fields=["email_situacao", "email_enviado_em", "email_tentativas"])


def registrar_falha(notificacao_id: uuid.UUID) -> None:
    """Grava `FALHOU` quando a tarefa desistiu. A notificação continua na caixa do destinatário."""
    Notificacao.objects.filter(pk=notificacao_id, email_situacao=SituacaoDoEmail.PENDENTE).update(
        email_situacao=SituacaoDoEmail.FALHOU
    )
