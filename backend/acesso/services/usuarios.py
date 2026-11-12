"""Criação e administração de usuários."""

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
