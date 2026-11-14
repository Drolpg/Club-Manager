"""O aggregate `Solicitacao` (com `Versao` e `Decisao`) e o cadastro `MotivoDeDecisao`.

Módulo core (ADR-001): o aggregate é o modelo persistido, e o estado só muda pelos métodos dele. Nada é
apagado. Versões e decisões não mudam depois de criadas; a versão só aceita gravar as duas datas de lembrete.
A mesma regra vale no banco, por gatilho (migração `0003`), para o caminho que passa por fora do `save`.
"""

import uuid
from typing import Any, NoReturn

from django.db import models
from django.db.models.functions import Lower

from aprovacoes.domain.transicoes import Situacao


class Imutavel(Exception):
    """Solicitação, versão, decisão e motivo não são apagados; versão e decisão não mudam."""


_SITUACOES = [(s.value, s.value) for s in Situacao]


class Solicitacao(models.Model):
    """Aggregate root. O conteúdo de cada versão pertence ao módulo dono do tipo; o motor não o interpreta."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    tipo = models.CharField(max_length=80)
    # Usuários são de outro módulo: referência por ID, sem chave estrangeira.
    solicitante_id = models.UUIDField()
    aprovador_indicado_id = models.UUIDField(null=True, blank=True)
    situacao = models.CharField(max_length=12, choices=_SITUACOES)
    numero_da_versao_atual = models.PositiveIntegerField(default=1)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = (
            models.Index(fields=["situacao", "tipo"], name="solicitacao_por_situacao"),
            models.Index(fields=["solicitante_id"], name="solicitacao_por_solicitante"),
        )

    def __str__(self) -> str:
        return f"{self.tipo} {self.id}"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise Imutavel("Solicitação não pode ser apagada; cancele.")


# Os únicos campos da versão que podem ser gravados depois da criação.
_DATAS_DE_LEMBRETE = ("lembrete_em", "aviso_ao_admin_em")


class Versao(models.Model):
    """Cada estado do corpo da solicitação (INV-SOL-05). Reenviar, reabrir e editar criam a seguinte."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.PROTECT, related_name="versoes")
    numero = models.PositiveIntegerField()
    conteudo = models.JSONField()
    valor = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    resumo = models.CharField(max_length=200)
    autor_id = models.UUIDField()
    justificativa = models.TextField(blank=True, default="")
    criada_em = models.DateTimeField(auto_now_add=True)
    lembrete_em = models.DateTimeField(null=True, blank=True)
    aviso_ao_admin_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("numero",)
        constraints = (
            models.UniqueConstraint(fields=["solicitacao", "numero"], name="versao_unica_por_numero"),
        )

    def __str__(self) -> str:
        return f"Versão {self.numero} de {self.solicitacao_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            update_fields = kwargs.get("update_fields")
            if update_fields is None or set(update_fields) - set(_DATAS_DE_LEMBRETE):
                self._conferir_que_so_as_datas_mudaram()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise Imutavel("Versão não pode ser apagada.")

    def _conferir_que_so_as_datas_mudaram(self) -> None:
        campos = [
            f.attname for f in self._meta.concrete_fields if f.attname not in (*_DATAS_DE_LEMBRETE, "id")
        ]
        gravada = Versao.objects.filter(pk=self.pk).values(*campos).first()
        if gravada is None:
            return
        for campo in campos:
            if gravada[campo] != getattr(self, campo):
                raise Imutavel(f"O campo {campo!r} da versão não pode ser alterado.")


class TipoDaDecisao(models.TextChoices):
    APROVAR = "APROVAR", "Aprovar"
    CONTESTAR = "CONTESTAR", "Contestar"
    RECUSAR = "RECUSAR", "Recusar"


class MotivoDeDecisao(models.Model):
    """Opção da lista que justifica uma decisão, por tipo de decisão. Desativado, nunca apagado (RN-014)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    tipo_de_decisao = models.CharField(max_length=60)
    texto = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("tipo_de_decisao", "texto")
        constraints = (
            # Conta ativos e inativos: o caminho para um texto que já existiu é reativar (adendo 1, A8).
            models.UniqueConstraint("tipo_de_decisao", Lower("texto"), name="motivo_unico_por_tipo"),
        )

    def __str__(self) -> str:
        return self.texto

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise Imutavel("Motivo de decisão não pode ser apagado; desative.")

    def editar(self, texto: str) -> None:
        self.texto = texto

    def desativar(self) -> None:
        self.ativo = False

    def reativar(self) -> None:
        self.ativo = True


class Decisao(models.Model):
    """Aprovar, contestar ou recusar uma versão (INV-SOL-03, INV-SOL-04). Uma por versão; não muda."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    versao = models.OneToOneField(Versao, on_delete=models.PROTECT, related_name="decisao")
    tipo = models.CharField(max_length=10, choices=TipoDaDecisao.choices)
    aprovador_id = models.UUIDField()
    motivo = models.ForeignKey(MotivoDeDecisao, on_delete=models.PROTECT, related_name="decisoes")
    # O texto do motivo no momento da decisão: mudar o motivo depois não reescreve a decisão.
    motivo_texto = models.CharField(max_length=200)
    texto = models.TextField(blank=True, default="")
    mensagem = models.TextField(blank=True, default="")
    teto_sugerido = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    aprovacao_propria = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.tipo} da versão {self.versao_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise Imutavel("Decisão não pode ser alterada.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise Imutavel("Decisão não pode ser apagada.")
