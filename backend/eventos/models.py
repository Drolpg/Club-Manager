"""Modelos de `eventos`: o aggregate `Evento`, a entidade `Presenca` e o cadastro `CategoriaDeEvento`.

O aggregate é o modelo persistido (ADR-001): o estado só muda pelos métodos dele, e cada método consulta a
tabela de `domain/transicoes.py`. Quem pode agir é conferido pelo serviço antes. Nada é apagado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, NoReturn

from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from eventos.domain.regras import DadosDoEvento, ErroDeRegra, EtapaDeAviso, avaliar_realizacao
from eventos.domain.situacao import ENCERRADAS, SituacaoDoEvento
from eventos.domain.transicoes import ComandoDoEvento, erro_de_situacao, transicao_permitida
from eventos.erros import erro, invalido

S = SituacaoDoEvento
C = ComandoDoEvento

LIMITE_DO_NOME_DA_CATEGORIA = 60


class Imutavel(Exception):
    """O registro não muda (encerrado) ou não é apagado."""


class CategoriaDeEvento(models.Model):
    """Cadastro mantido pelo admin; usada, é desativada, nunca apagada (RN-018)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    nome = models.CharField(max_length=LIMITE_DO_NOME_DA_CATEGORIA)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("nome",)
        constraints = (models.UniqueConstraint(Lower("nome"), name="categoria_de_evento_nome_unico"),)

    def __str__(self) -> str:
        return self.nome

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise Imutavel("Categoria de evento não é apagada; desative.")

    @classmethod
    def criar(cls, nome: str) -> CategoriaDeEvento:
        return cls.objects.create(nome=nome.strip())

    def editar(self, nome: str) -> None:
        self.nome = nome.strip()
        self.save(update_fields=["nome", "atualizada_em"])

    def desativar(self) -> None:
        self.ativa = False
        self.save(update_fields=["ativa", "atualizada_em"])

    def reativar(self) -> None:
        self.ativa = True
        self.save(update_fields=["ativa", "atualizada_em"])


@dataclass(frozen=True)
class Transicao:
    antes: SituacaoDoEvento
    depois: SituacaoDoEvento


_SITUACOES = [(s.value, s.value) for s in SituacaoDoEvento]
_MARCAS = {
    EtapaDeAviso.NA_DATA: "aviso_na_data_em",
    EtapaDeAviso.UM_DIA: "lembrete_1_dia_em",
    EtapaDeAviso.TRES_DIAS: "lembrete_3_dias_em",
}


class Evento(models.Model):
    """Aggregate root. Não guarda valor: o custo existe só no orçamento (INV-EVT-02)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    titulo = models.CharField(max_length=120)
    descricao = models.TextField(max_length=2000, blank=True)
    inicio = models.DateTimeField()
    local = models.CharField(max_length=200)
    categoria = models.ForeignKey(CategoriaDeEvento, on_delete=models.PROTECT, related_name="eventos")
    categoria_nome = models.CharField(max_length=LIMITE_DO_NOME_DA_CATEGORIA)
    proponente_id = models.UUIDField()
    envolve_custo = models.BooleanField()
    situacao = models.CharField(max_length=16, choices=_SITUACOES, default=S.EM_APROVACAO.value)
    # Nulo só dentro da transação da proposta, antes de a solicitação existir.
    solicitacao_do_evento_id = models.UUIDField(unique=True, null=True)
    solicitacao_orcamentaria_id = models.UUIDField(null=True, blank=True)
    publicacoes = models.PositiveIntegerField(default=0)
    ciclo_de_presenca = models.PositiveIntegerField(default=1)
    # Realização (value object)
    realizado_em_data = models.DateField(null=True, blank=True)
    realizacao_motivo = models.TextField(blank=True)
    realizado_por_id = models.UUIDField(null=True, blank=True)
    realizado_em = models.DateTimeField(null=True, blank=True)
    # Cancelamento (value object); ator nulo também quando é o sistema
    cancelamento_motivo = models.TextField(blank=True)
    cancelado_por_id = models.UUIDField(null=True, blank=True)
    cancelado_pelo_sistema = models.BooleanField(default=False)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    # Marcas dos avisos de realização (CA-18)
    aviso_na_data_em = models.DateField(null=True, blank=True)
    lembrete_1_dia_em = models.DateField(null=True, blank=True)
    lembrete_3_dias_em = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-inicio", "-id")
        indexes = (
            models.Index(fields=["situacao"], name="evento_situacao_idx"),
            models.Index(fields=["inicio"], name="evento_inicio_idx"),
            models.Index(fields=["proponente_id"], name="evento_proponente_idx"),
        )
        constraints = (
            models.UniqueConstraint(
                fields=["solicitacao_orcamentaria_id"],
                condition=models.Q(solicitacao_orcamentaria_id__isnull=False),
                name="evento_orcamento_unico",
            ),
            models.CheckConstraint(
                condition=models.Q(situacao__in=[s.value for s in SituacaoDoEvento]),
                name="evento_situacao_valida",
            ),
            models.CheckConstraint(
                condition=~models.Q(situacao="CANCELADO")
                | (models.Q(cancelado_em__isnull=False) & ~models.Q(cancelamento_motivo="")),
                name="evento_cancelado_com_motivo",
            ),
            models.CheckConstraint(
                condition=~models.Q(situacao="REALIZADO")
                | models.Q(realizado_em_data__isnull=False, realizado_em__isnull=False),
                name="evento_realizado_com_data",
            ),
        )

    def __str__(self) -> str:
        return f"{self.titulo} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise Imutavel("Evento não é apagado; cancele.")

    @property
    def data_do_evento(self) -> date:
        """A data do evento no fuso do sistema (spec técnica do M8, "Fuso e datas")."""
        return timezone.localdate(self.inicio)

    @property
    def id_da_solicitacao_do_evento(self) -> uuid.UUID:
        """Só fica nulo dentro da transação da proposta; depois dela, sempre existe."""
        if self.solicitacao_do_evento_id is None:
            raise RuntimeError(f"O evento {self.id} está sem a solicitação dele.")
        return self.solicitacao_do_evento_id

    @property
    def encerrado(self) -> bool:
        return SituacaoDoEvento(self.situacao) in ENCERRADAS

    def _exigir(self, comando: ComandoDoEvento) -> None:
        situacao = SituacaoDoEvento(self.situacao)
        if not transicao_permitida(situacao, comando):
            raise erro(erro_de_situacao(situacao, comando))

    @classmethod
    def propor(
        cls,
        *,
        dados: DadosDoEvento,
        categoria: CategoriaDeEvento,
        proponente_id: uuid.UUID,
        envolve_custo: bool,
    ) -> Evento:
        return cls.objects.create(
            titulo=dados.titulo,
            descricao=dados.descricao,
            local=dados.local,
            inicio=dados.inicio,
            categoria=categoria,
            categoria_nome=categoria.nome,
            proponente_id=proponente_id,
            envolve_custo=envolve_custo,
        )

    def ligar_solicitacao_do_evento(self, solicitacao_id: uuid.UUID) -> None:
        if self.solicitacao_do_evento_id is not None:
            raise ValueError("O evento já tem a solicitação dele.")
        self.solicitacao_do_evento_id = solicitacao_id
        self.save(update_fields=["solicitacao_do_evento_id", "atualizado_em"])

    def editar(self, dados: DadosDoEvento, *, categoria: CategoriaDeEvento, envolve_custo: bool) -> bool:
        """Troca os dados e devolve se a data do evento mudou; se mudou, os avisos de realização recomeçam."""
        self._exigir(C.EDITAR)
        if not envolve_custo and self.solicitacao_orcamentaria_id is not None:
            raise erro("ORCAMENTO_JA_VINCULADO", "O evento tem orçamento: não dá para tirar o custo.")
        data_antes = self.data_do_evento
        self.titulo, self.descricao, self.local, self.inicio = (
            dados.titulo,
            dados.descricao,
            dados.local,
            dados.inicio,
        )
        self.categoria, self.categoria_nome, self.envolve_custo = categoria, categoria.nome, envolve_custo
        data_mudou = self.data_do_evento != data_antes
        if data_mudou:
            self.aviso_na_data_em = self.lembrete_1_dia_em = self.lembrete_3_dias_em = None
        self.save()
        return data_mudou

    def vincular_orcamento(self, solicitacao_id: uuid.UUID) -> None:
        """INV-EVT-07: um orçamento por evento, só com custo e não encerrado."""
        self._exigir(C.VINCULAR_ORCAMENTO)
        if not self.envolve_custo:
            raise erro("EVENTO_SEM_CUSTO")
        if self.solicitacao_orcamentaria_id is not None:
            raise erro("ORCAMENTO_JA_VINCULADO")
        self.solicitacao_orcamentaria_id = solicitacao_id
        self.save(update_fields=["solicitacao_orcamentaria_id", "atualizado_em"])

    def desvincular_orcamento(self, solicitacao_id: uuid.UUID) -> bool:
        """O orçamento cancelado por fora se desliga do evento (adendo 1 da funcional). Diz se desligou."""
        if self.solicitacao_orcamentaria_id != solicitacao_id:
            return False
        self.solicitacao_orcamentaria_id = None
        self.save(update_fields=["solicitacao_orcamentaria_id", "atualizado_em"])
        return True

    def atualizar_situacao(self, nova: SituacaoDoEvento) -> Transicao | None:
        """Grava a situação calculada por `situacao_do_evento`. Encerrado ou igual: nada (INV-EVT-01)."""
        if nova in ENCERRADAS:
            raise ValueError("Realizado e cancelado só por comando.")
        antes = SituacaoDoEvento(self.situacao)
        if self.encerrado or nova == antes:
            return None
        self.situacao = nova.value
        if nova == S.PUBLICADO:
            self.publicacoes += 1
        self.save(update_fields=["situacao", "publicacoes", "atualizado_em"])
        return Transicao(antes, nova)

    def zerar_presencas(self) -> None:
        """Mudar a data zera as presenças (P3) sem apagar: as respostas antigas ficam no ciclo anterior."""
        self.ciclo_de_presenca += 1
        self.save(update_fields=["ciclo_de_presenca", "atualizado_em"])

    def confirmar_realizacao(self, *, data_real: date, motivo: str, ator_id: uuid.UUID, hoje: date) -> None:
        self._exigir(C.CONFIRMAR_REALIZACAO)
        try:
            avaliar_realizacao(
                data_planejada=self.data_do_evento, data_real=data_real, hoje=hoje, motivo=motivo
            )
        except ErroDeRegra as regra:
            if regra.campo is not None:
                raise invalido({regra.campo: [regra.mensagem]}) from None
            raise erro(regra.codigo, regra.mensagem) from None
        self.situacao = S.REALIZADO.value
        self.realizado_em_data = data_real
        self.realizacao_motivo = motivo.strip()
        self.realizado_por_id = ator_id
        self.realizado_em = timezone.now()
        self.save()

    def cancelar(self, *, motivo: str, ator_id: uuid.UUID | None, pelo_sistema: bool = False) -> None:
        """INV-EVT-06: com motivo. Ator nulo é o sistema."""
        self._exigir(C.CANCELAR)
        limpo = motivo.strip()
        if not limpo:
            raise invalido({"motivo": ["Informe o motivo do cancelamento."]})
        self.situacao = S.CANCELADO.value
        self.cancelamento_motivo = limpo
        self.cancelado_por_id = ator_id
        self.cancelado_pelo_sistema = pelo_sistema
        self.cancelado_em = timezone.now()
        self.save()

    def marcar_aviso(self, etapa: EtapaDeAviso, hoje: date) -> None:
        campo = _MARCAS[etapa]
        setattr(self, campo, hoje)
        self.save(update_fields=[campo, "atualizado_em"])

    def marcas_de_aviso(self) -> dict[EtapaDeAviso, date | None]:
        return {etapa: getattr(self, campo) for etapa, campo in _MARCAS.items()}


class RespostaDePresenca(models.TextChoices):
    VOU = "VOU", "Vou"
    NAO_VOU = "NAO_VOU", "Não vou"


class Presenca(models.Model):
    """A resposta de um diretor a um evento publicado, no ciclo de presença atual (regra 12)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    evento = models.ForeignKey(Evento, on_delete=models.PROTECT, related_name="presencas")
    ciclo = models.PositiveIntegerField()
    diretor_id = models.UUIDField()
    resposta = models.CharField(max_length=8, choices=RespostaDePresenca.choices)
    respondida_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("respondida_em", "id")
        constraints = (
            models.UniqueConstraint(
                fields=["evento", "ciclo", "diretor_id"], name="presenca_unica_por_ciclo"
            ),
        )

    def __str__(self) -> str:
        return f"{self.diretor_id}: {self.resposta}"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise Imutavel("Presença não é apagada; mude a resposta.")

    @classmethod
    def responder(cls, evento: Evento, *, diretor_id: uuid.UUID, resposta: str) -> Presenca:
        """Cria a resposta do ciclo atual ou troca a que existe: vale a última (CA-13)."""
        existente = cls.objects.filter(
            evento=evento, ciclo=evento.ciclo_de_presenca, diretor_id=diretor_id
        ).first()
        if existente is None:
            return cls.objects.create(
                evento=evento, ciclo=evento.ciclo_de_presenca, diretor_id=diretor_id, resposta=resposta
            )
        existente.resposta = resposta
        existente.save(update_fields=["resposta", "atualizada_em"])
        return existente
