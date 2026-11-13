import uuid
from datetime import datetime
from typing import Any, NoReturn

from django.db import models
from django.db.models import Q


class NotificacaoImutavel(Exception):
    """Uma notificação é um registro: o conteúdo nunca muda e ela nunca é apagada (NOT-R05)."""


class SituacaoDoEmail(models.TextChoices):
    PENDENTE = "PENDENTE", "Pendente"
    ENVIADO = "ENVIADO", "Enviado"
    # O destinatário desligou os e-mails informativos, ou deixou de estar ativo antes do envio.
    DISPENSADO = "DISPENSADO", "Dispensado"
    FALHOU = "FALHOU", "Falhou"


# O que nunca muda depois de criada. Só `lida_em` e o resultado do envio ganham valor.
_CONTEUDO = (
    "destinatario_id",
    "tipo",
    "pede_acao",
    "titulo",
    "texto",
    "item_tipo",
    "item_id",
    "caminho",
    "chave",
)


class Notificacao(models.Model):
    """O registro de que um usuário foi avisado de algo (RN-009).

    O destinatário é de outro módulo, então a referência é por ID, sem chave estrangeira. A `chave` identifica
    o fato e, com o destinatário, é única: é o que impede a notificação duplicada (NOT-R02).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    destinatario_id = models.UUIDField()
    tipo = models.CharField(max_length=80)
    # Copiada do tipo no momento da criação: mudar o tipo depois não reescreve o que já foi avisado.
    pede_acao = models.BooleanField()
    titulo = models.CharField(max_length=120)
    texto = models.CharField(max_length=500)
    item_tipo = models.CharField(max_length=60)
    item_id = models.UUIDField()
    caminho = models.CharField(max_length=200)
    chave = models.CharField(max_length=120)
    criada_em = models.DateTimeField(auto_now_add=True)
    lida_em = models.DateTimeField(null=True, blank=True)
    email_situacao = models.CharField(max_length=10, choices=SituacaoDoEmail.choices)
    email_enviado_em = models.DateTimeField(null=True, blank=True)
    email_tentativas = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["destinatario_id", "chave"], name="notificacao_por_destinatario_e_chave"
            ),
        )
        indexes = (
            models.Index(fields=["destinatario_id", "criada_em"], name="notificacao_da_caixa"),
            models.Index(
                fields=["destinatario_id"],
                condition=Q(lida_em__isnull=True),
                name="notificacao_nao_lida",
            ),
        )

    def __str__(self) -> str:
        return f"{self.tipo} para {self.destinatario_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            self._conferir_que_nada_imutavel_mudou(kwargs.get("update_fields"))
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotificacaoImutavel("Notificação não pode ser apagada.")

    def marcar_lida(self, agora: datetime) -> None:
        """Preenche `lida_em` na primeira leitura; as seguintes não mudam a data (NOT-R04)."""
        if self.lida_em is None:
            self.lida_em = agora

    def _conferir_que_nada_imutavel_mudou(self, update_fields: Any) -> None:
        # Só os campos que seriam gravados contam: um valor trocado só na memória não vai para o banco.
        gravados = set(update_fields) if update_fields is not None else None
        campos = [c for c in (*_CONTEUDO, "lida_em") if gravados is None or c in gravados]
        gravada = Notificacao.objects.filter(pk=self.pk).values(*campos).first()
        if gravada is None:
            return
        for campo in campos:
            antes, agora = gravada[campo], getattr(self, campo)
            if campo == "lida_em":
                if antes is not None and antes != agora:
                    raise NotificacaoImutavel("A data da primeira leitura não muda.")
            elif antes != agora:
                raise NotificacaoImutavel(f"O campo {campo!r} da notificação não pode ser alterado.")


class PreferenciaDeAlerta(models.Model):
    """Como o usuário quer ser alertado. Nenhuma chave desliga o registro (RN 1, CA-19).

    A linha é criada quando o usuário altera algo; sem linha, valem os padrões (os dois ligados).
    """

    usuario_id = models.UUIDField(primary_key=True)
    aviso_na_tela = models.BooleanField(default=True)
    email_informativos = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"Preferências de {self.usuario_id}"
