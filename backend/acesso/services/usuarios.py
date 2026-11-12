"""Criação e administração de usuários."""

import uuid

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from acesso.domain.identificacao import (
    nome_de_usuario_valido,
    normalizar_email,
    normalizar_telefone,
    telefone_valido,
)
from acesso.models import Situacao, Usuario
from acesso.services.autorizacao import exigir_admin
from auditoria import public as auditoria
from kernel.errors import BusinessError


def _email_valido(email: str) -> bool:
    try:
        validate_email(email)
    except ValidationError:
        return False
    return True


def validar_dados(*, nome: str, nome_de_usuario: str, email: str, telefone: str, senha: str) -> None:
    """Confere formato e política de senha. Levanta `VALIDATION_ERROR` apontando cada campo."""
    erros: dict[str, list[str]] = {}
    if not nome.strip():
        erros["nome"] = ["Informe o nome."]
    if not nome_de_usuario_valido(nome_de_usuario):
        erros["nome_de_usuario"] = [
            "Use de 3 a 30 caracteres: letras sem acento, números, ponto, hífen ou sublinhado."
        ]
    if not _email_valido(email):
        erros["email"] = ["Informe um e-mail válido."]
    if not telefone_valido(telefone):
        erros["telefone"] = ["Informe um telefone com 8 a 15 dígitos."]
    try:
        # O validador compara a senha com os dados do usuário, para recusar senhas parecidas com eles.
        validate_password(senha, user=Usuario(nome=nome, nome_de_usuario=nome_de_usuario, email=email))
    except ValidationError as erro:
        erros["senha"] = list(erro.messages)
    if erros:
        raise BusinessError("VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details=erros)


def criar_usuario(
    *,
    nome: str,
    nome_de_usuario: str,
    email: str,
    telefone: str,
    senha: str,
    situacao: Situacao,
    admin: bool = False,
    google_sub: str | None = None,
) -> Usuario:
    """Cria a conta depois de validar os dados e a unicidade. Chame dentro de uma transação."""
    email = normalizar_email(email)
    telefone = normalizar_telefone(telefone)
    nome_de_usuario = nome_de_usuario.strip()
    validar_dados(nome=nome, nome_de_usuario=nome_de_usuario, email=email, telefone=telefone, senha=senha)

    if Usuario.objects.filter(nome_de_usuario__iexact=nome_de_usuario).exists():
        raise BusinessError("NOME_DE_USUARIO_EM_USO", "Este nome de usuário já está em uso.", status=409)
    if Usuario.objects.filter(email__iexact=email).exists():
        raise BusinessError("EMAIL_EM_USO", "Este e-mail já está em uso.", status=409)

    usuario = Usuario(
        nome=nome.strip(),
        nome_de_usuario=nome_de_usuario,
        email=email,
        telefone=telefone,
        situacao=situacao,
        admin=admin,
        google_sub=google_sub,
    )
    if situacao == Situacao.ATIVO:
        usuario.email_verificado_em = timezone.now()
    usuario.set_password(senha)
    try:
        # O savepoint mantém a transação de fora utilizável se dois cadastros disputarem o mesmo nome.
        with transaction.atomic():
            usuario.save()
    except IntegrityError as erro:
        if "email" in str(erro):
            raise BusinessError("EMAIL_EM_USO", "Este e-mail já está em uso.", status=409) from erro
        raise BusinessError(
            "NOME_DE_USUARIO_EM_USO", "Este nome de usuário já está em uso.", status=409
        ) from erro
    return usuario


@transaction.atomic
def criar_admin(*, nome: str, nome_de_usuario: str, email: str, telefone: str, senha: str) -> Usuario:
    """Cria um admin ativo, com o e-mail já verificado. Usado só pelo comando do servidor (RF-014)."""
    usuario = criar_usuario(
        nome=nome,
        nome_de_usuario=nome_de_usuario,
        email=email,
        telefone=telefone,
        senha=senha,
        situacao=Situacao.ATIVO,
        admin=True,
    )
    auditoria.registrar(
        ator_id=None, acao="ADMIN_CRIADO_POR_COMANDO", item_tipo="usuario", item_id=usuario.id
    )
    return usuario


def listar(*, ator: Usuario) -> list[Usuario]:
    exigir_admin(ator)
    return list(Usuario.objects.all())


def _alvo(usuario_id: uuid.UUID) -> Usuario:
    usuario = Usuario.objects.select_for_update().filter(pk=usuario_id).first()
    if usuario is None:
        raise BusinessError("NOT_FOUND", "Usuário não encontrado.", status=404)
    return usuario


def _impedir_em_si_mesmo(ator: Usuario, alvo: Usuario) -> None:
    # Com isto, sempre existe ao menos um admin ativo (RN-024, ACE-R04).
    if ator.id == alvo.id:
        raise BusinessError("NAO_PODE_ALTERAR_A_SI_MESMO", "Esta ação precisa ser feita por outro admin.")


def _exigir_situacao(alvo: Usuario, situacao: Situacao, codigo: str, mensagem: str) -> None:
    if alvo.situacao != situacao:
        raise BusinessError(codigo, mensagem)


def _auditar(ator: Usuario, alvo: Usuario, acao: str) -> None:
    auditoria.registrar(ator_id=ator.id, acao=acao, item_tipo="usuario", item_id=alvo.id)


@transaction.atomic
def desativar(*, ator: Usuario, usuario_id: uuid.UUID) -> Usuario:
    """Tira o acesso na hora: a sessão é conferida a cada requisição e só usuário ativo é reconhecido."""
    exigir_admin(ator)
    alvo = _alvo(usuario_id)
    _impedir_em_si_mesmo(ator, alvo)
    _exigir_situacao(alvo, Situacao.ATIVO, "USUARIO_NAO_ESTA_ATIVO", "Só usuário ativo pode ser desativado.")
    alvo.desativar()
    alvo.save(update_fields=["situacao"])
    _auditar(ator, alvo, "USUARIO_DESATIVADO")
    return alvo


@transaction.atomic
def reativar(*, ator: Usuario, usuario_id: uuid.UUID) -> Usuario:
    exigir_admin(ator)
    alvo = _alvo(usuario_id)
    _exigir_situacao(
        alvo, Situacao.INATIVO, "USUARIO_NAO_ESTA_INATIVO", "Só usuário inativo pode ser reativado."
    )
    alvo.reativar()
    alvo.save(update_fields=["situacao"])
    _auditar(ator, alvo, "USUARIO_REATIVADO")
    return alvo


@transaction.atomic
def tornar_admin(*, ator: Usuario, usuario_id: uuid.UUID) -> Usuario:
    exigir_admin(ator)
    alvo = _alvo(usuario_id)
    _exigir_situacao(alvo, Situacao.ATIVO, "USUARIO_NAO_ESTA_ATIVO", "Só usuário ativo pode virar admin.")
    if alvo.admin:
        raise BusinessError("USUARIO_JA_E_ADMIN", "Este usuário já é admin.")
    alvo.tornar_admin()
    alvo.save(update_fields=["admin"])
    _auditar(ator, alvo, "PAPEL_DE_ADMIN_DADO")
    return alvo


@transaction.atomic
def remover_admin(*, ator: Usuario, usuario_id: uuid.UUID) -> Usuario:
    exigir_admin(ator)
    alvo = _alvo(usuario_id)
    _impedir_em_si_mesmo(ator, alvo)
    if not alvo.admin:
        raise BusinessError("USUARIO_NAO_E_ADMIN", "Este usuário não é admin.")
    alvo.remover_admin()
    alvo.save(update_fields=["admin"])
    _auditar(ator, alvo, "PAPEL_DE_ADMIN_REMOVIDO")
    return alvo
