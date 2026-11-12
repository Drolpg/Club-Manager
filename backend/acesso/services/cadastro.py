"""Cadastro pelo convite, com senha, e verificação do e-mail (RF-004, RF-005)."""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from acesso import tasks
from acesso.domain.cadastro import PRAZO_DE_VERIFICACAO, cadastro_vencido
from acesso.domain.convite import SituacaoDoConvite
from acesso.domain.identificacao import normalizar_email
from acesso.models import Convite, Situacao, Usuario
from acesso.services import convites, tokens, usuarios
from auditoria import public as auditoria
from kernel import rate_limit

# Reenvio do link de verificação: 3 por hora por conta (technical-spec, "Limites").
_LIMITE_DE_REENVIO = 3
_JANELA_DE_REENVIO = 60 * 60


def reservar_convite(token: str) -> Convite:
    """Bloqueia a linha do convite e confere que ele está ativo (ACE-R01). Chame dentro de uma transação."""
    convite = Convite.objects.select_for_update().filter(token_hash=convites.hash_do_token(token)).first()
    if convite is None or convite.situacao(timezone.now()) != SituacaoDoConvite.ATIVO:
        raise convites.convite_invalido()
    return convite


def usar_convite(convite: Convite, usuario: Usuario) -> None:
    convite.marcar_usado(usuario=usuario, agora=timezone.now())
    convite.save(update_fields=["usado_em", "usado_por"])
    auditoria.registrar(ator_id=usuario.id, acao="CONVITE_USADO", item_tipo="convite", item_id=convite.id)


@transaction.atomic
def cadastrar(
    *, token: str, nome: str, nome_de_usuario: str, telefone: str, email: str, senha: str
) -> Usuario:
    """Cria o cadastro aguardando verificação e gasta o convite.

    Se os dados forem recusados, a transação é desfeita e o convite continua ativo.
    """
    convite = reservar_convite(token)
    # Um cadastro vencido que a tarefa agendada ainda não descartou não pode prender nome de usuário
    # nem e-mail.
    descartar_cadastros_vencidos()
    usuario = usuarios.criar_usuario(
        nome=nome,
        nome_de_usuario=nome_de_usuario,
        email=email,
        telefone=telefone,
        senha=senha,
        situacao=Situacao.AGUARDANDO_VERIFICACAO,
    )
    usar_convite(convite, usuario)
    usuario_id = str(usuario.id)
    transaction.on_commit(lambda: tasks.enviar_email_de_verificacao.delay(usuario_id))
    return usuario


def concluir_cadastro(usuario: Usuario) -> None:
    """Registra a conclusão e avisa os admins. O usuário já está ativo e salvo."""
    auditoria.registrar(
        ator_id=usuario.id, acao="CADASTRO_CONCLUIDO", item_tipo="usuario", item_id=usuario.id
    )
    usuario_id = str(usuario.id)
    transaction.on_commit(lambda: tasks.avisar_admins_de_diretor_a_classificar.delay(usuario_id))


@transaction.atomic
def verificar(*, token: str) -> Usuario:
    usuario_id, email = tokens.ler_token_de_verificacao(token)
    usuario = Usuario.objects.select_for_update().filter(pk=usuario_id).first()
    agora = timezone.now()
    if (
        usuario is None
        or usuario.situacao != Situacao.AGUARDANDO_VERIFICACAO
        or usuario.email != email
        or cadastro_vencido(agora=agora, criado_em=usuario.criado_em)
    ):
        raise tokens.link_invalido()
    usuario.verificar_email(agora)
    usuario.save(update_fields=["situacao", "email_verificado_em"])
    concluir_cadastro(usuario)
    return usuario


def reenviar_verificacao(*, identificador: str) -> None:
    """Reenvia o link a quem aguarda verificação. Nunca diz se a conta existe (RN-025)."""
    identificador = normalizar_email(identificador)
    usuario = Usuario.objects.filter(
        Q(nome_de_usuario__iexact=identificador) | Q(email__iexact=identificador),
        situacao=Situacao.AGUARDANDO_VERIFICACAO,
    ).first()
    if usuario is None or cadastro_vencido(agora=timezone.now(), criado_em=usuario.criado_em):
        return
    chave = str(usuario.id)
    if rate_limit.exceeded("reenvio-de-verificacao", chave, limit=_LIMITE_DE_REENVIO):
        return
    rate_limit.hit("reenvio-de-verificacao", chave, window=_JANELA_DE_REENVIO)
    tasks.enviar_email_de_verificacao.delay(chave)


@transaction.atomic
def descartar_cadastros_vencidos() -> int:
    """Remove cadastros que não foram verificados no prazo, liberando nome de usuário e e-mail (ACE-R06).

    Um cadastro não verificado ainda não é um usuário do clube; por isso pode ser removido. O convite que ele
    usou continua usado.
    """
    limite = timezone.now() - PRAZO_DE_VERIFICACAO
    vencidos = list(
        Usuario.objects.select_for_update()
        .filter(situacao=Situacao.AGUARDANDO_VERIFICACAO, criado_em__lte=limite)
        .values_list("id", flat=True)
    )
    for usuario_id in vencidos:
        auditoria.registrar(ator_id=None, acao="CADASTRO_DESCARTADO", item_tipo="usuario", item_id=usuario_id)
    Usuario.objects.filter(pk__in=vencidos).delete()
    return len(vencidos)
