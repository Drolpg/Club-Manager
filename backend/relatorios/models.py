"""O pedido de relatório (spec técnica `relatorios/relatorios-pdf-e-csv`, "Modelo `PedidoDeRelatorio`").

Contexto de apoio, em camadas (ADR-001): o modelo é uma tabela, sem aggregate. As transições estão em
`relatorios/domain/pedido.py` e só os serviços as aplicam. O pedido nunca é apagado; o arquivo, sim, depois de
7 dias (ADR-020), e a chave continua registrada.
"""

from __future__ import annotations

import uuid
from typing import Any, NoReturn

from django.db import models
from django.db.models import Q

from relatorios.domain.pedido import COM_ARQUIVO, Formato, SituacaoDoPedido


class PedidoNaoEApagado(Exception):
    """O pedido de relatório fica, com quem pediu, quando, o tipo e os parâmetros."""


def _escolhas(enum: Any) -> list[tuple[str, str]]:
    return [(item.value, item.value) for item in enum]


class PedidoDeRelatorio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    tipo = models.CharField(max_length=40)
    formato = models.CharField(max_length=3, choices=_escolhas(Formato))
    parametros = models.JSONField(default=dict)
    # Referência por ID, sem chave estrangeira para `acesso` (regra do plano).
    pedido_por_id = models.UUIDField()
    pedido_em = models.DateTimeField()
    situacao = models.CharField(max_length=10, choices=_escolhas(SituacaoDoPedido))
    iniciado_em = models.DateTimeField(null=True)
    concluido_em = models.DateTimeField(null=True)
    expira_em = models.DateTimeField(null=True)
    expirado_em = models.DateTimeField(null=True)
    arquivo_chave = models.CharField(max_length=200, default="")
    arquivo_nome = models.CharField(max_length=200, default="")
    arquivo_mime = models.CharField(max_length=60, default="")
    arquivo_tamanho = models.PositiveBigIntegerField(null=True)
    codigo_da_falha = models.CharField(max_length=30, default="")

    class Meta:
        indexes = (
            models.Index(fields=("pedido_por_id", "pedido_em"), name="pedido_por_usuario"),
            models.Index(fields=("situacao", "expira_em"), name="pedido_por_situacao"),
        )
        constraints = (
            models.CheckConstraint(
                condition=Q(situacao__in=[s.value for s in SituacaoDoPedido]), name="pedido_situacao_valida"
            ),
            models.CheckConstraint(
                condition=Q(formato__in=[f.value for f in Formato]), name="pedido_formato_valido"
            ),
            models.CheckConstraint(
                # Ordenado: a ordem de um frozenset muda entre processos, e a migração ficaria instável.
                condition=~Q(situacao__in=sorted(s.value for s in COM_ARQUIVO)) | ~Q(arquivo_chave=""),
                name="pedido_pronto_tem_arquivo",
            ),
        )

    def __str__(self) -> str:
        return f"{self.tipo} {self.formato} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise PedidoNaoEApagado("O pedido de relatório não é apagado.")
