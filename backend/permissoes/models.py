import uuid
from datetime import datetime

from django.db import models
from django.db.models.functions import Lower


class _ComNome(models.Model):
    """Base de cargo e de setor: nome único sem diferenciar maiúsculas; desativado, nunca apagado."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    nome = models.CharField(max_length=60)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ("nome",)

    def __str__(self) -> str:
        return self.nome

    def renomear(self, nome: str) -> None:
        self.nome = nome

    def desativar(self) -> None:
        self.ativo = False

    def reativar(self) -> None:
        self.ativo = True


class Cargo(_ComNome):
    """Função do diretor no clube. Sem concessão, um cargo não dá permissão nenhuma (RN-006)."""

    class Meta(_ComNome.Meta):
        constraints = (models.UniqueConstraint(Lower("nome"), name="cargo_nome_unico"),)


class Setor(_ComNome):
    """Área do clube. Um usuário pode estar em vários setores."""

    class Meta(_ComNome.Meta):
        constraints = (models.UniqueConstraint(Lower("nome"), name="setor_nome_unico"),)


class Classificacao(models.Model):
    """O cargo e os setores de um diretor. Existir a linha é "ter cargo"; tirar o cargo remove a linha.

    O usuário é de outro módulo, então a referência é por ID, sem chave estrangeira.
    """

    usuario_id = models.UUIDField(primary_key=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name="classificacoes")
    setores = models.ManyToManyField(Setor, related_name="classificacoes", blank=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Classificação de {self.usuario_id}"


class AlvoDaConcessao(models.TextChoices):
    CARGO = "CARGO", "Cargo"
    SETOR = "SETOR", "Setor"
    USUARIO = "USUARIO", "Usuário"


class Concessao(models.Model):
    """Uma permissão do catálogo dada a um cargo, a um setor ou a um usuário.

    Revogar preenche `revogada_em`; nada é apagado. Há no máximo uma concessão ativa por permissão e alvo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    permissao = models.CharField(max_length=80)
    alvo_tipo = models.CharField(max_length=10, choices=AlvoDaConcessao.choices)
    cargo = models.ForeignKey(
        Cargo, on_delete=models.PROTECT, null=True, blank=True, related_name="concessoes"
    )
    setor = models.ForeignKey(
        Setor, on_delete=models.PROTECT, null=True, blank=True, related_name="concessoes"
    )
    usuario_id = models.UUIDField(null=True, blank=True)
    concedida_por_id = models.UUIDField()
    concedida_em = models.DateTimeField()
    revogada_por_id = models.UUIDField(null=True, blank=True)
    revogada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("permissao", "concedida_em")
        constraints = (
            models.UniqueConstraint(
                fields=("permissao", "cargo"),
                condition=models.Q(revogada_em__isnull=True, alvo_tipo="CARGO"),
                name="concessao_ativa_unica_por_cargo",
            ),
            models.UniqueConstraint(
                fields=("permissao", "setor"),
                condition=models.Q(revogada_em__isnull=True, alvo_tipo="SETOR"),
                name="concessao_ativa_unica_por_setor",
            ),
            models.UniqueConstraint(
                fields=("permissao", "usuario_id"),
                condition=models.Q(revogada_em__isnull=True, alvo_tipo="USUARIO"),
                name="concessao_ativa_unica_por_usuario",
            ),
        )

    def __str__(self) -> str:
        return f"{self.permissao} para {self.alvo_tipo}"

    @property
    def ativa(self) -> bool:
        return self.revogada_em is None

    def revogar(self, *, por: uuid.UUID, agora: datetime) -> None:
        self.revogada_por_id = por
        self.revogada_em = agora
