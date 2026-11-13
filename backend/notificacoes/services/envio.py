"""Registro das notificações e agendamento do e-mail (RF-028, RF-029; NOT-R01, NOT-R02, NOT-R07)."""

import uuid
from collections.abc import Iterable

from django.db import transaction

from acesso import public as acesso
from notificacoes import tasks, tipos
from notificacoes.domain.envio import deve_enviar_email
from notificacoes.models import Notificacao, PreferenciaDeAlerta, SituacaoDoEmail


def _desligaram_email_informativo(destinatario_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    """Quem desligou o e-mail dos informativos. Quem não tem linha usa o padrão (ligado)."""
    return set(
        PreferenciaDeAlerta.objects.filter(
            usuario_id__in=list(destinatario_ids), email_informativos=False
        ).values_list("usuario_id", flat=True)
    )


def notificar(
    *,
    tipo: str,
    destinatarios: Iterable[uuid.UUID],
    titulo: str,
    texto: str,
    item_tipo: str,
    item_id: uuid.UUID,
    caminho: str,
    chave: str,
) -> int:
    """Registra a notificação para cada destinatário ativo e agenda o e-mail para depois do commit.

    Chame dentro da transação do caso de uso: o registro entra nela, e o e-mail só sai se ela for confirmada.
    Chamar de novo com a mesma `chave` não cria outra notificação nem outro e-mail. Devolve quantas criou.
    """
    definicao = tipos.obter(tipo)
    ativos = acesso.ids_ativos(set(destinatarios))
    desligaram = _desligaram_email_informativo(ativos)

    criadas = 0
    for destinatario_id in sorted(ativos):
        enviar = deve_enviar_email(definicao.pede_acao, destinatario_id not in desligaram)
        notificacao, criada = Notificacao.objects.get_or_create(
            destinatario_id=destinatario_id,
            chave=chave,
            defaults={
                "tipo": tipo,
                "pede_acao": definicao.pede_acao,
                "titulo": titulo,
                "texto": texto,
                "item_tipo": item_tipo,
                "item_id": item_id,
                "caminho": caminho,
                "email_situacao": SituacaoDoEmail.PENDENTE if enviar else SituacaoDoEmail.DISPENSADO,
            },
        )
        if not criada:
            continue
        criadas += 1
        if enviar:
            _agendar_email(notificacao.id)
    return criadas


def _agendar_email(notificacao_id: uuid.UUID) -> None:
    # Só o ID vai para a fila; o e-mail é montado na hora de enviar.
    transaction.on_commit(lambda: tasks.enviar_email.delay(str(notificacao_id)))
