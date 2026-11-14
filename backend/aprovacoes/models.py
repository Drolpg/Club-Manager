"""O aggregate `Solicitacao` (com `Versao` e `Decisao`) e o cadastro `MotivoDeDecisao`.

Módulo core (ADR-001): o aggregate é o modelo persistido, e o estado só muda pelos métodos dele. Nada é
apagado. Versões e decisões não mudam depois de criadas; a versão só aceita gravar as duas datas de lembrete.
A mesma regra vale no banco, por gatilho (migração `0003`), para o caminho que passa por fora do `save`.
"""

import uuid
from typing import Any, NoReturn

from django.db import models
from django.db.models.functions import Lower

from aprovacoes.domain.transicoes import (
    ERRO_DE_SITUACAO,
    Comando,
    Situacao,
    situacao_apos,
    transicao_permitida,
)
from aprovacoes.erros import erro
from aprovacoes.tipos import ConteudoPreparado
from kernel.dinheiro import Dinheiro


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

    @classmethod
    def abrir(
        cls,
        *,
        tipo: str,
        solicitante_id: uuid.UUID,
        aprovador_indicado_id: uuid.UUID | None,
        preparado: ConteudoPreparado,
    ) -> Solicitacao:
        """Enviar: nasce em análise, com a versão 1. Quem pode enviar é conferido pelo serviço."""
        solicitacao = cls.objects.create(
            tipo=tipo,
            solicitante_id=solicitante_id,
            aprovador_indicado_id=aprovador_indicado_id,
            situacao=Situacao.EM_ANALISE,
            numero_da_versao_atual=1,
        )
        Versao.criar(solicitacao, numero=1, preparado=preparado, autor_id=solicitante_id)
        return solicitacao

    @property
    def versao_atual(self) -> Versao:
        return self.versoes.get(numero=self.numero_da_versao_atual)

    def retirar(self) -> None:
        """INV-SOL-12: só em análise, e sem versão nova. Quem retira é conferido pelo serviço."""
        self._executar(Comando.RETIRAR)
        self._gravar()

    def reenviar(self, preparado: ConteudoPreparado, *, autor_id: uuid.UUID) -> None:
        """INV-SOL-13: contestada ou retirada; nasce a versão seguinte, em análise."""
        self._executar(Comando.REENVIAR)
        self._acrescentar_versao(preparado, autor_id=autor_id)

    def reabrir(self, preparado: ConteudoPreparado, *, autor_id: uuid.UUID, justificativa: str) -> None:
        self._executar(Comando.REABRIR)
        self._acrescentar_versao(preparado, autor_id=autor_id, justificativa=justificativa)

    def editar(self, preparado: ConteudoPreparado, *, autor_id: uuid.UUID, justificativa: str = "") -> None:
        """Só aprovada e antes da execução (INV-SOL-09). A aprovação anterior não vale para a versão nova."""
        self._executar(Comando.EDITAR)
        self._acrescentar_versao(preparado, autor_id=autor_id, justificativa=justificativa)

    def cancelar(self) -> None:
        self._executar(Comando.CANCELAR)
        self._gravar()

    def iniciar_execucao(self) -> None:
        """Comandado pelo módulo dono (por exemplo, quando o recurso é enviado). Daí em diante, INV-SOL-09."""
        self._executar(Comando.INICIAR_EXECUCAO)
        self._gravar()

    def encerrar(self) -> None:
        """Comandado pelo módulo dono, a partir de aprovada ou em execução. Encerrada, não muda mais."""
        self._executar(Comando.ENCERRAR)
        self._gravar()

    def aprovar(
        self,
        *,
        aprovador_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        aprovacao_propria: bool,
    ) -> Decisao:
        return self._decidir(
            Comando.APROVAR,
            aprovador_id=aprovador_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            texto=texto,
            aprovacao_propria=aprovacao_propria,
        )

    def contestar(
        self,
        *,
        aprovador_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        mensagem: str,
        teto_sugerido: Dinheiro | None,
        aprovacao_propria: bool,
    ) -> Decisao:
        return self._decidir(
            Comando.CONTESTAR,
            aprovador_id=aprovador_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            texto=texto,
            mensagem=mensagem,
            teto_sugerido=teto_sugerido,
            aprovacao_propria=aprovacao_propria,
        )

    def recusar(
        self,
        *,
        aprovador_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        aprovacao_propria: bool,
    ) -> Decisao:
        return self._decidir(
            Comando.RECUSAR,
            aprovador_id=aprovador_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            texto=texto,
            aprovacao_propria=aprovacao_propria,
        )

    def _decidir(
        self,
        comando: Comando,
        *,
        aprovador_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        aprovacao_propria: bool,
        mensagem: str = "",
        teto_sugerido: Dinheiro | None = None,
    ) -> Decisao:
        """INV-SOL-01, 03, 04 e 07. Quem pode decidir (INV-SOL-02, 11) é conferido antes, pelo serviço."""
        self._exigir_transicao(comando)
        versao = self.versao_atual
        if Decisao.objects.filter(versao=versao).exists():
            raise erro("NAO_ESTA_EM_ANALISE")
        if comando is Comando.CONTESTAR and not mensagem:
            raise ValueError("Contestar exige mensagem.")
        if teto_sugerido is not None:
            if versao.valor is None:
                raise erro("TETO_SEM_VALOR")
            if teto_sugerido.quantia <= 0:
                raise ValueError("O teto sugerido é maior que zero.")
        decisao = Decisao.objects.create(
            versao=versao,
            tipo=TipoDaDecisao(comando.value),
            aprovador_id=aprovador_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            texto=texto,
            mensagem=mensagem,
            teto_sugerido=teto_sugerido.quantia if teto_sugerido is not None else None,
            aprovacao_propria=aprovacao_propria,
        )
        self._executar(comando)
        self._gravar()
        return decisao

    def _exigir_transicao(self, comando: Comando) -> None:
        if not transicao_permitida(Situacao(self.situacao), comando):
            raise erro(ERRO_DE_SITUACAO[comando])

    def _executar(self, comando: Comando) -> None:
        """Toda mudança de situação passa pela tabela de transições (INV-SOL-08, INV-SOL-09)."""
        self._exigir_transicao(comando)
        self.situacao = situacao_apos(Situacao(self.situacao), comando)

    def _acrescentar_versao(
        self, preparado: ConteudoPreparado, *, autor_id: uuid.UUID, justificativa: str = ""
    ) -> None:
        """INV-SOL-05 e INV-SOL-06: versões só são acrescentadas, e cada uma volta à análise sem decisão."""
        self.numero_da_versao_atual += 1
        Versao.criar(
            self,
            numero=self.numero_da_versao_atual,
            preparado=preparado,
            autor_id=autor_id,
            justificativa=justificativa,
        )
        self._gravar()

    def _gravar(self) -> None:
        self.save(update_fields=["situacao", "numero_da_versao_atual", "atualizada_em"])


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

    @classmethod
    def criar(
        cls,
        solicitacao: Solicitacao,
        *,
        numero: int,
        preparado: ConteudoPreparado,
        autor_id: uuid.UUID,
        justificativa: str = "",
    ) -> Versao:
        """Só o aggregate cria versões. O conteúdo já vem validado e normalizado pelo módulo dono."""
        return cls.objects.create(
            solicitacao=solicitacao,
            numero=numero,
            conteudo=preparado.conteudo,
            valor=preparado.valor.quantia if preparado.valor is not None else None,
            resumo=preparado.resumo,
            autor_id=autor_id,
            justificativa=justificativa,
        )


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
