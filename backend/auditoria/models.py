import uuid
from typing import Any, NoReturn

from django.db import models


class RegistroImutavel(Exception):
    """Um registro de auditoria nunca é alterado nem apagado (AUD-01, AUD-04)."""


class RegistroDeAuditoria(models.Model):
    """Quem fez o quê, quando, sobre qual item e por quê.

    Só inserção. O modelo recusa alterar e apagar, e um gatilho no banco recusa o mesmo para qualquer outro
    caminho (migração 0001). Guarda IDs e códigos, nunca dados pessoais, senhas ou tokens.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    # Nulo quando a ação vem do sistema ou de um comando no servidor.
    ator_id = models.UUIDField(null=True, blank=True)
    acao = models.CharField(max_length=60)
    item_tipo = models.CharField(max_length=60)
    item_id = models.UUIDField()
    justificativa = models.TextField(blank=True, default="")
    dados = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("criado_em", "id")
        indexes = (
            models.Index(fields=["item_tipo", "item_id", "criado_em"], name="auditoria_por_item"),
            models.Index(fields=["ator_id", "criado_em"], name="auditoria_por_ator"),
        )

    def __str__(self) -> str:
        return f"{self.acao} em {self.item_tipo}:{self.item_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise RegistroImutavel("Registro de auditoria não pode ser alterado.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise RegistroImutavel("Registro de auditoria não pode ser apagado.")
