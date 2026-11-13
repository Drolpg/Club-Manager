"""E-mails transacionais do acesso. São chamados pelas tarefas, depois do commit.

Cada função recebe só o ID do usuário e monta o link na hora de enviar: nenhum token passa pela fila.
"""

import uuid

from django.conf import settings
from django.core.mail import send_mail

from acesso.models import Situacao, Usuario
from acesso.services.tokens import gerar_token_de_verificacao


def enviar_verificacao(usuario_id: uuid.UUID) -> None:
    usuario = Usuario.objects.filter(pk=usuario_id, situacao=Situacao.AGUARDANDO_VERIFICACAO).first()
    if usuario is None:
        return
    link = f"{settings.SITE_URL}/verificar/{gerar_token_de_verificacao(usuario)}"
    send_mail(
        subject="Confirme seu e-mail no Club Manager",
        message=(
            f"Olá, {usuario.nome}.\n\n"
            "Para concluir o seu cadastro no Club Manager, confirme o seu e-mail abrindo o link abaixo. "
            "Ele vale por 24 horas.\n\n"
            f"{link}\n\n"
            "Se você não pediu este cadastro, ignore esta mensagem."
        ),
        from_email=None,
        recipient_list=[usuario.email],
    )


def enviar_recuperacao(usuario_id: uuid.UUID) -> None:
    from acesso.services.senha import gerar_token_de_recuperacao

    usuario = Usuario.objects.filter(pk=usuario_id, situacao=Situacao.ATIVO).first()
    if usuario is None:
        return
    link = f"{settings.SITE_URL}/redefinir-senha/{gerar_token_de_recuperacao(usuario)}"
    send_mail(
        subject="Redefinição de senha no Club Manager",
        message=(
            f"Olá, {usuario.nome}.\n\n"
            "Recebemos um pedido para redefinir a sua senha no Club Manager. Abra o link abaixo para "
            "escolher uma nova. Ele vale por 1 hora e só funciona uma vez.\n\n"
            f"{link}\n\n"
            "Se não foi você, ignore esta mensagem: a sua senha continua a mesma."
        ),
        from_email=None,
        recipient_list=[usuario.email],
    )
