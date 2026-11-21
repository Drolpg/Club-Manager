"""Modelos de `comunicacao`: comunicados, reações, comentários, documentos e as versões de cada um.

Contexto de apoio, em camadas (ADR-001): os modelos são tabelas, com as regras nos serviços e as garantias de
integridade no banco (`CheckConstraint`, únicos e os gatilhos da migração `0003`). Nada é apagado (RN-014).
"""

from __future__ import annotations

import uuid
from typing import Any, NoReturn

from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from comunicacao.domain.regras import LIMITE_DO_TITULO
from comunicacao.domain.valores import (
    SituacaoDoComentario,
    SituacaoDoComunicado,
    SituacaoDoDocumento,
    TipoDeComunicado,
    TipoDeDocumento,
    TipoDeReacao,
)

LIMITE_DO_NOME_DA_CATEGORIA = 60


def _escolhas(enum: Any) -> list[tuple[str, str]]:
    return [(item.value, item.value) for item in enum]


class Imutavel(Exception):
    """O registro não é apagado."""


class SemExclusao(models.Model):
    """Base dos modelos que nunca são apagados; o gatilho do banco é a segunda barreira."""

    class Meta:
        abstract = True

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise Imutavel(f"{type(self).__name__} não é apagado.")


class CategoriaDeDocumento(SemExclusao):
    """Cadastro mantido pelo admin; usada, é desativada, nunca apagada (RN-018)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    nome = models.CharField(max_length=LIMITE_DO_NOME_DA_CATEGORIA)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("nome",)
        constraints = (models.UniqueConstraint(Lower("nome"), name="categoria_de_documento_nome_unico"),)

    def __str__(self) -> str:
        return self.nome


class Comunicado(SemExclusao):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    tipo = models.CharField(max_length=16, choices=_escolhas(TipoDeComunicado))
    titulo = models.CharField(max_length=LIMITE_DO_TITULO)
    texto = models.TextField()
    autor_id = models.UUIDField()
    situacao = models.CharField(
        max_length=16, choices=_escolhas(SituacaoDoComunicado), default=SituacaoDoComunicado.PUBLICADO.value
    )
    fixado_em = models.DateTimeField(null=True, blank=True)
    # A primeira publicação: republicar não a muda.
    publicado_em = models.DateTimeField(default=timezone.now)
    versao = models.PositiveIntegerField(default=1)
    editado_em = models.DateTimeField(null=True, blank=True)
    despublicado_em = models.DateTimeField(null=True, blank=True)
    despublicado_por_id = models.UUIDField(null=True, blank=True)
    motivo_da_despublicacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = (
            models.Index(fields=["situacao"], name="comunicado_situacao_idx"),
            models.Index(fields=["fixado_em"], name="comunicado_fixado_idx"),
            models.Index(fields=["autor_id"], name="comunicado_autor_idx"),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(tipo__in=[t.value for t in TipoDeComunicado]),
                name="comunicado_tipo_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(situacao__in=[s.value for s in SituacaoDoComunicado]),
                name="comunicado_situacao_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(fixado_em__isnull=True) | models.Q(situacao="PUBLICADO"),
                name="comunicado_fixado_so_publicado",
            ),
            models.CheckConstraint(
                condition=~models.Q(situacao="DESPUBLICADO") | ~models.Q(motivo_da_despublicacao=""),
                name="comunicado_despublicado_com_motivo",
            ),
        )

    def __str__(self) -> str:
        return f"{self.titulo} ({self.situacao})"


class VersaoDeComunicado(SemExclusao):
    """O texto de cada edição; guarda o antes e o depois, que a auditoria não leva (D1). Imutável."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    comunicado = models.ForeignKey(Comunicado, on_delete=models.PROTECT, related_name="versoes")
    numero = models.PositiveIntegerField()
    titulo = models.CharField(max_length=LIMITE_DO_TITULO)
    texto = models.TextField()
    autor_da_versao_id = models.UUIDField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("numero",)
        constraints = (
            models.UniqueConstraint(fields=["comunicado", "numero"], name="versao_de_comunicado_unica"),
        )

    def __str__(self) -> str:
        return f"{self.comunicado_id} v{self.numero}"


class Documento(SemExclusao):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    tipo = models.CharField(max_length=16, choices=_escolhas(TipoDeDocumento))
    titulo = models.CharField(max_length=LIMITE_DO_TITULO)
    descricao = models.TextField(blank=True)
    categoria = models.ForeignKey(
        CategoriaDeDocumento, on_delete=models.PROTECT, related_name="documentos", null=True, blank=True
    )
    categoria_nome = models.CharField(max_length=LIMITE_DO_NOME_DA_CATEGORIA, blank=True)
    data_da_reuniao = models.DateField(null=True, blank=True)
    enviado_por_id = models.UUIDField()
    situacao = models.CharField(
        max_length=16, choices=_escolhas(SituacaoDoDocumento), default=SituacaoDoDocumento.VIGENTE.value
    )
    versao_atual = models.PositiveIntegerField(default=1)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = (
            models.Index(fields=["situacao"], name="documento_situacao_idx"),
            models.Index(fields=["tipo"], name="documento_tipo_idx"),
            models.Index(fields=["enviado_por_id"], name="documento_enviado_por_idx"),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(situacao__in=[s.value for s in SituacaoDoDocumento]),
                name="documento_situacao_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(tipo="ATA", categoria__isnull=True, data_da_reuniao__isnull=False)
                | models.Q(tipo="DOCUMENTO", categoria__isnull=False, data_da_reuniao__isnull=True),
                name="documento_ata_ou_categoria",
            ),
        )

    def __str__(self) -> str:
        return f"{self.titulo} ({self.tipo})"


class VersaoDeDocumento(SemExclusao):
    """Cada arquivo enviado para o documento; só a de `numero = versao_atual` é a vigente. Imutável."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    documento = models.ForeignKey(Documento, on_delete=models.PROTECT, related_name="versoes")
    numero = models.PositiveIntegerField()
    chave = models.CharField(max_length=255)
    nome = models.CharField(max_length=150)
    mime = models.CharField(max_length=100)
    tamanho = models.PositiveBigIntegerField()
    motivo = models.TextField(blank=True)
    enviada_por_id = models.UUIDField()
    enviada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("numero",)
        constraints = (
            models.UniqueConstraint(fields=["documento", "numero"], name="versao_de_documento_unica"),
            models.CheckConstraint(
                condition=models.Q(numero=1) | ~models.Q(motivo=""),
                name="versao_de_documento_com_motivo",
            ),
        )

    def __str__(self) -> str:
        return f"{self.documento_id} v{self.numero}"


class VinculoDeDocumento(SemExclusao):
    """O comunicado indexa o documento; desvincular marca a data, sem apagar."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    comunicado = models.ForeignKey(Comunicado, on_delete=models.PROTECT, related_name="vinculos")
    documento = models.ForeignKey(Documento, on_delete=models.PROTECT, related_name="vinculos")
    vinculado_em = models.DateTimeField(default=timezone.now)
    desvinculado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["comunicado", "documento"],
                condition=models.Q(desvinculado_em__isnull=True),
                name="vinculo_ativo_unico",
            ),
        )

    def __str__(self) -> str:
        return f"{self.comunicado_id} -> {self.documento_id}"


class Reacao(SemExclusao):
    """Uma por diretor e comunicado. Trocar muda o tipo; retirar marca a data e sai da contagem."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    comunicado = models.ForeignKey(Comunicado, on_delete=models.PROTECT, related_name="reacoes")
    diretor_id = models.UUIDField()
    tipo = models.CharField(max_length=16, choices=_escolhas(TipoDeReacao))
    retirada_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=["comunicado", "diretor_id"], name="reacao_unica_por_diretor"),
            models.CheckConstraint(
                condition=models.Q(tipo__in=[t.value for t in TipoDeReacao]), name="reacao_tipo_valido"
            ),
        )

    def __str__(self) -> str:
        return f"{self.diretor_id}: {self.tipo}"


class Comentario(SemExclusao):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    comunicado = models.ForeignKey(Comunicado, on_delete=models.PROTECT, related_name="comentarios")
    autor_id = models.UUIDField()
    texto = models.TextField()
    situacao = models.CharField(
        max_length=16, choices=_escolhas(SituacaoDoComentario), default=SituacaoDoComentario.VISIVEL.value
    )
    oculto_por_id = models.UUIDField(null=True, blank=True)
    oculto_pela_gerencia = models.BooleanField(default=False)
    motivo_da_ocultacao = models.TextField(blank=True)
    oculto_em = models.DateTimeField(null=True, blank=True)
    editado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(situacao__in=[s.value for s in SituacaoDoComentario]),
                name="comentario_situacao_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(oculto_pela_gerencia=False)
                | (models.Q(situacao="OCULTO") & ~models.Q(motivo_da_ocultacao="")),
                name="comentario_ocultado_pela_gerencia_com_motivo",
            ),
        )

    def __str__(self) -> str:
        return f"{self.autor_id}: {self.situacao}"


class VersaoDeComentario(SemExclusao):
    """O texto de cada edição do comentário (a versão 1 nasce com ele). Imutável."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    comentario = models.ForeignKey(Comentario, on_delete=models.PROTECT, related_name="versoes")
    numero = models.PositiveIntegerField()
    texto = models.TextField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("numero",)
        constraints = (
            models.UniqueConstraint(fields=["comentario", "numero"], name="versao_de_comentario_unica"),
        )

    def __str__(self) -> str:
        return f"{self.comentario_id} v{self.numero}"
