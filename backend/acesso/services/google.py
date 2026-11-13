"""Entrar e cadastrar-se com o Google (RF-007 a RF-009)."""

from django.db import transaction
from django.utils import timezone

from acesso.domain.cadastro import cadastro_vencido
from acesso.domain.identificacao import normalizar_email
from acesso.google import CredencialGoogleInvalida, IdentidadeGoogle, obter_verificador
from acesso.models import Situacao, Usuario
from acesso.services import cadastro, usuarios
from kernel.errors import BusinessError


def _google_invalido() -> BusinessError:
    return BusinessError("GOOGLE_INVALIDO", "Não foi possível confirmar a sua conta Google.", status=401)


def _identificar(credencial: str) -> IdentidadeGoogle:
    try:
        return obter_verificador().verificar(credencial)
    except CredencialGoogleInvalida as erro:
        raise _google_invalido() from erro


@transaction.atomic
def entrar(*, credencial: str) -> Usuario:
    """Devolve o usuário ativo dono do e-mail confirmado pelo Google. Nunca cria conta (RF-009)."""
    identidade = _identificar(credencial)
    email = normalizar_email(identidade.email)
    usuario = Usuario.objects.select_for_update().filter(email__iexact=email).first()
    agora = timezone.now()

    if usuario is None or (
        usuario.situacao == Situacao.AGUARDANDO_VERIFICACAO
        and cadastro_vencido(agora=agora, criado_em=usuario.criado_em)
    ):
        raise BusinessError(
            "ACESSO_SO_POR_CONVITE", "O acesso é só por convite. Peça um ao administrador.", status=403
        )
    if usuario.situacao == Situacao.INATIVO:
        raise BusinessError("CREDENCIAIS_INVALIDAS", "Usuário ou senha inválidos.", status=401)
    if usuario.google_sub and usuario.google_sub != identidade.sub:
        # O e-mail é o mesmo, mas a conta Google é outra: não é o dono que se vinculou antes.
        raise _google_invalido()

    campos = []
    if not usuario.google_sub:
        usuario.google_sub = identidade.sub
        campos.append("google_sub")
    if usuario.situacao == Situacao.AGUARDANDO_VERIFICACAO:
        # O Google já comprovou o e-mail (funcional, regra 11).
        usuario.verificar_email(agora)
        campos += ["situacao", "email_verificado_em"]
        usuario.save(update_fields=campos)
        cadastro.concluir_cadastro(usuario)
    elif campos:
        usuario.save(update_fields=campos)
    return usuario


@transaction.atomic
def cadastrar(
    *, token: str, credencial: str, nome: str, nome_de_usuario: str, telefone: str, senha: str
) -> Usuario:
    """Cria a conta já ativa, com o e-mail do Google, e gasta o convite. Sem link de verificação."""
    identidade = _identificar(credencial)
    convite = cadastro.reservar_convite(token)
    cadastro.descartar_cadastros_vencidos()
    email = normalizar_email(identidade.email)
    if Usuario.objects.filter(email__iexact=email).exists():
        raise BusinessError(
            "CONTA_JA_EXISTE", "Já existe uma conta com este e-mail. Entre por ela.", status=409
        )
    usuario = usuarios.criar_usuario(
        nome=nome,
        nome_de_usuario=nome_de_usuario,
        email=email,
        telefone=telefone,
        senha=senha,
        situacao=Situacao.ATIVO,
        google_sub=identidade.sub,
    )
    cadastro.usar_convite(convite, usuario)
    cadastro.concluir_cadastro(usuario)
    return usuario
