import uuid
from datetime import datetime
from typing import ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class Situacao(models.TextChoices):
    AGUARDANDO_VERIFICACAO = "AGUARDANDO_VERIFICACAO", "Aguardando verificação"
    ATIVO = "ATIVO", "Ativo"
    INATIVO = "INATIVO", "Inativo"


class UsuarioManager(BaseUserManager["Usuario"]):
    """Gerenciador padrão. As contas são criadas pelos serviços, nunca direto por aqui."""


class Usuario(AbstractBaseUser):
    """Pessoa com conta no sistema. Na etapa 1, todo usuário é um diretor.

    A situação e o papel de admin só mudam pelos métodos abaixo. Cargo e setores não ficam aqui: pertencem ao
    módulo `permissoes` (M3). O sistema não guarda CPF (RN-003).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    nome = models.CharField(max_length=120)
    # `unique=True` atende à checagem do Django para o campo de login; a unicidade que vale, sem diferenciar
    # maiúsculas, é a da restrição em `Meta`.
    nome_de_usuario = models.CharField(max_length=30, unique=True)
    email = models.EmailField(max_length=254)
    telefone = models.CharField(max_length=20)
    situacao = models.CharField(
        max_length=30, choices=Situacao.choices, default=Situacao.AGUARDANDO_VERIFICACAO
    )
    admin = models.BooleanField(default=False)
    # Identificador da conta Google, gravado no primeiro uso do login social.
    google_sub = models.CharField(max_length=255, null=True, blank=True, unique=True)
    email_verificado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    objects: ClassVar[UsuarioManager] = UsuarioManager()

    USERNAME_FIELD = "nome_de_usuario"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["nome", "email", "telefone"]

    class Meta:
        ordering = ("nome", "id")
        constraints = (
            # Únicos sem diferenciar maiúsculas de minúsculas (RN-002).
            models.UniqueConstraint(Lower("nome_de_usuario"), name="usuario_nome_de_usuario_unico"),
            models.UniqueConstraint(Lower("email"), name="usuario_email_unico"),
        )

    def __str__(self) -> str:
        return self.nome_de_usuario

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        """Só usuário ativo autentica; o Django confere isto a cada requisição (ACE-R03)."""
        return self.situacao == Situacao.ATIVO

    def verificar_email(self, agora: datetime) -> None:
        self.email_verificado_em = agora
        if self.situacao == Situacao.AGUARDANDO_VERIFICACAO:
            self.situacao = Situacao.ATIVO

    def desativar(self) -> None:
        self.situacao = Situacao.INATIVO

    def reativar(self) -> None:
        self.situacao = Situacao.ATIVO

    def tornar_admin(self) -> None:
        self.admin = True

    def remover_admin(self) -> None:
        self.admin = False
