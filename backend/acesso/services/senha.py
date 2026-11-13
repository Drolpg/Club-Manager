"""Recuperação de senha pelo e-mail verificado (RF-010)."""

import uuid

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction

from acesso import tasks
from acesso.domain.identificacao import normalizar_email
from acesso.models import Situacao, Usuario
from acesso.services.tokens import link_invalido
from auditoria import public as auditoria
from kernel import rate_limit
from kernel.errors import BusinessError

# Pedido de recuperação: 3 por hora por e-mail (technical-spec, "Limites").
_LIMITE_DE_PEDIDOS = 3
_JANELA_DE_PEDIDOS = 60 * 60


def gerar_token_de_recuperacao(usuario: Usuario) -> str:
    """ID do usuário e token do Django, que depende do hash da senha: trocar a senha invalida o link."""
    return f"{usuario.id}.{default_token_generator.make_token(usuario)}"


def pedir_recuperacao(*, email: str) -> None:
    """Enfileira o e-mail se a conta existe e está ativa. Nunca diz se ela existe (RN-025)."""
    email = normalizar_email(email)
    if rate_limit.exceeded("recuperacao-de-senha", email, limit=_LIMITE_DE_PEDIDOS):
        return
    rate_limit.hit("recuperacao-de-senha", email, window=_JANELA_DE_PEDIDOS)
    usuario = Usuario.objects.filter(email__iexact=email, situacao=Situacao.ATIVO).first()
    if usuario is not None:
        tasks.enviar_email_de_recuperacao.delay(str(usuario.id))


@transaction.atomic
def redefinir(*, token: str, senha: str) -> None:
    """Troca a senha. As sessões abertas da conta deixam de valer, porque dependem do hash da senha."""
    id_em_texto, _, token_do_django = token.partition(".")
    try:
        usuario_id = uuid.UUID(id_em_texto)
    except ValueError as erro:
        raise link_invalido() from erro
    usuario = Usuario.objects.select_for_update().filter(pk=usuario_id, situacao=Situacao.ATIVO).first()
    if usuario is None or not default_token_generator.check_token(usuario, token_do_django):
        raise link_invalido()
    try:
        validate_password(senha, user=usuario)
    except ValidationError as erro:
        raise BusinessError(
            "VALIDATION_ERROR",
            "Os dados enviados são inválidos.",
            status=400,
            details={"senha": list(erro.messages)},
        ) from erro
    usuario.set_password(senha)
    usuario.save(update_fields=["password"])
    auditoria.registrar(ator_id=usuario.id, acao="SENHA_REDEFINIDA", item_tipo="usuario", item_id=usuario.id)
    # Quem redefiniu a senha provou que é o dono do e-mail: o bloqueio por tentativas erradas acaba.
    rate_limit.reset("login", str(usuario.id))
