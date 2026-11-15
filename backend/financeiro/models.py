"""Modelos persistidos e aggregates core do módulo financeiro (ADR-001, technical-spec)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, NoReturn

from django.db import models
from django.db.models.functions import Lower

from financeiro.domain.competencia import Periodicidade, Periodo
from financeiro.domain.pix import TipoChavePix, gerar_pix_copia_e_cola, normalizar_e_validar_chave
from financeiro.domain.saidas import (
    ErroDeRegraSaida,
    LiquidacaoResultado,
    avaliar_lembretes_prestacao,
    avaliar_liquidacao,
    validar_devolucao_de_sobra,
    validar_envio_complemento,
    validar_envio_inicial,
)
from financeiro.domain.transicoes import (
    ComandoCobranca,
    ComandoEntrada,
    ComandoSaida,
    SituacaoCobranca,
    SituacaoEntrada,
    SituacaoSaida,
    dias_pausados_em_decisao,
    estado_sem_pagamento,
    transicao_cobranca_permitida,
    transicao_entrada_permitida,
    transicao_saida_permitida,
)
from financeiro.erros import erro, erro_validacao
from kernel.anexos import AnexoSalvo
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError


class NaoPodeApagar(Exception):
    """Cadastros e registros financeiros nunca são apagados (CA-48, INV-COB-16)."""


class NaturezaCategoria(models.TextChoices):
    ENTRADA = "ENTRADA", "Entrada"
    SAIDA = "SAIDA", "Saída"


class FormaPagamento(models.TextChoices):
    COMPROVANTE = "COMPROVANTE", "Comprovante"
    EM_MAO = "EM_MAO", "Em mão"


class SituacaoPagamento(models.TextChoices):
    EM_VALIDACAO = "EM_VALIDACAO", "Em validação"
    VALIDADO = "VALIDADO", "Validado"
    REJEITADO = "REJEITADO", "Rejeitado"


class SituacaoQuestionamento(models.TextChoices):
    ABERTO = "ABERTO", "Aberto"
    DECIDIDO = "DECIDIDO", "Decidido"


class DecisaoQuestionamento(models.TextChoices):
    ISENTAR = "ISENTAR", "Isentar"
    CANCELAR = "CANCELAR", "Cancelar"
    MANTER = "MANTER", "Manter"


class DecisaoDivida(models.TextChoices):
    PERDOAR = "PERDOAR", "Perdoar"
    RENEGOCIAR = "RENEGOCIAR", "Renegociar"
    MANTER = "MANTER", "Manter"


class SituacaoSuspensao(models.TextChoices):
    VIGENTE = "VIGENTE", "Vigente"
    ENCERRADA = "ENCERRADA", "Encerrada"


class TipoEntrada(models.TextChoices):
    SEM_DEVEDOR = "SEM_DEVEDOR", "Sem devedor"
    DEVOLUCAO = "DEVOLUCAO", "Devolução"


class SituacaoPrestacao(models.TextChoices):
    VIGENTE = "VIGENTE", "Vigente"
    DEVOLVIDA = "DEVOLVIDA", "Devolvida"


class SituacaoComplemento(models.TextChoices):
    EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
    APROVADO = "APROVADO", "Aprovado"
    RECUSADO = "RECUSADO", "Recusado"
    CANCELADO = "CANCELADO", "Cancelado"


class AlvoEstorno(models.TextChoices):
    SAIDA = "SAIDA", "Saída"
    ENTRADA = "ENTRADA", "Entrada"
    COBRANCA = "COBRANCA", "Cobrança"


_TIPOS_PIX = [(t.value, t.value) for t in TipoChavePix]
_SITUACOES_COBRANCA = [(s.value, s.value) for s in SituacaoCobranca]
_PERIODICIDADES = [(p.value, p.value) for p in Periodicidade]
_SITUACOES_ENTRADA = [(s.value, s.value) for s in SituacaoEntrada]
_SITUACOES_SAIDA = [(s.value, s.value) for s in SituacaoSaida]


def _traduzir_regra(exc: ErroDeRegraSaida) -> BusinessError:
    if exc.codigo == "VALIDATION_ERROR":
        return erro_validacao(exc.campo or "valor", exc.mensagem)
    return erro(exc.codigo, mensagem=exc.mensagem)


class CategoriaFinanceira(models.Model):
    """Categoria de entrada ou de saída mantida pelo administrador (CA-01, CA-02)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    nome = models.CharField(max_length=80)
    natureza = models.CharField(max_length=10, choices=NaturezaCategoria.choices)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("natureza", "nome")
        constraints = (
            models.UniqueConstraint(
                Lower("nome"), "natureza", name="categoria_financeira_unica_por_natureza"
            ),
        )

    def __str__(self) -> str:
        return f"{self.nome} ({self.natureza})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Categorias financeiras não são apagadas; desative-as.")

    def renomear(self, nome: str) -> None:
        self.nome = nome.strip()

    def desativar(self) -> None:
        if not self.ativa:
            raise erro("JA_ESTA_INATIVO")
        self.ativa = False

    def reativar(self) -> None:
        if self.ativa:
            raise erro("JA_ESTA_ATIVO")
        self.ativa = True


class ChavePix(models.Model):
    """Chave Pix de destino do clube (CA-03). Apenas uma ativa pode estar marcada como padrão."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    tipo = models.CharField(max_length=15, choices=_TIPOS_PIX)
    chave = models.CharField(max_length=140)
    nome_recebedor = models.CharField(max_length=100)
    cidade = models.CharField(max_length=60)
    padrao = models.BooleanField(default=False)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-padrao", "-criada_em")
        constraints = (
            models.UniqueConstraint(
                fields=("padrao",),
                condition=models.Q(padrao=True),
                name="chave_pix_padrao_unica",
            ),
        )

    def __str__(self) -> str:
        return f"{self.tipo}: {self.chave}"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Chaves Pix não são apagadas; desative-as.")

    @classmethod
    def criar(cls, *, tipo: str, chave: str, nome_recebedor: str, cidade: str, padrao: bool) -> ChavePix:
        try:
            chave_norm = normalizar_e_validar_chave(tipo, chave)
        except ValueError as exc:
            raise erro_validacao("chave", str(exc)) from None
        return cls(
            tipo=tipo,
            chave=chave_norm,
            nome_recebedor=nome_recebedor.strip(),
            cidade=cidade.strip(),
            padrao=padrao,
            ativa=True,
        )

    def editar(self, *, tipo: str, chave: str, nome_recebedor: str, cidade: str) -> None:
        try:
            chave_norm = normalizar_e_validar_chave(tipo, chave)
        except ValueError as exc:
            raise erro_validacao("chave", str(exc)) from None
        self.tipo = tipo
        self.chave = chave_norm
        self.nome_recebedor = nome_recebedor.strip()
        self.cidade = cidade.strip()

    def marcar_como_padrao(self) -> None:
        if not self.ativa:
            raise erro("CHAVE_PIX_INATIVA")
        self.padrao = True

    def desmarcar_padrao(self) -> None:
        self.padrao = False

    def desativar(self) -> None:
        if not self.ativa:
            raise erro("JA_ESTA_INATIVO")
        self.ativa = False
        self.padrao = False

    def reativar(self) -> None:
        if self.ativa:
            raise erro("JA_ESTA_ATIVO")
        self.ativa = True


class Recorrencia(models.Model):
    """Aggregate root que descreve cobrança recorrente de um diretor (INV-REC-01..04)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    devedor_id = models.UUIDField()
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="recorrencias")
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    periodicidade = models.CharField(max_length=10, choices=_PERIODICIDADES)
    dia_vencimento = models.PositiveSmallIntegerField()
    mes_vencimento = models.PositiveSmallIntegerField(null=True, blank=True)
    antecedencia_dias = models.PositiveIntegerField(default=10)
    limite_de_inadimplencia = models.PositiveIntegerField(default=30)
    chave_pix = models.ForeignKey(ChavePix, on_delete=models.PROTECT, related_name="recorrencias")
    ativa = models.BooleanField(default=True)
    a_partir_de = models.DateField()
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-criada_em",)
        indexes = (models.Index(fields=["ativa", "devedor_id"], name="recorrencia_ativa_devedor"),)

    def __str__(self) -> str:
        return f"{self.descricao} ({self.periodicidade})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Recorrências não são apagadas; desative-as.")

    @classmethod
    def criar(
        cls,
        *,
        devedor_id: uuid.UUID,
        categoria: CategoriaFinanceira,
        descricao: str,
        valor: Dinheiro,
        periodicidade: Periodicidade,
        dia_vencimento: int,
        mes_vencimento: int | None,
        antecedencia_dias: int,
        limite_de_inadimplencia: int,
        chave_pix: ChavePix,
        a_partir_de: date,
    ) -> Recorrencia:
        if valor.quantia <= 0:
            raise erro("VALOR_INVALIDO")
        if not categoria.ativa or categoria.natureza != NaturezaCategoria.ENTRADA:
            raise erro("CATEGORIA_INATIVA")
        if not chave_pix.ativa:
            raise erro("CHAVE_PIX_INATIVA")
        return cls.objects.create(
            devedor_id=devedor_id,
            categoria=categoria,
            descricao=descricao.strip(),
            valor=valor.quantia,
            periodicidade=periodicidade.value,
            dia_vencimento=dia_vencimento,
            mes_vencimento=mes_vencimento,
            antecedencia_dias=antecedencia_dias,
            limite_de_inadimplencia=limite_de_inadimplencia,
            chave_pix=chave_pix,
            ativa=True,
            a_partir_de=a_partir_de,
        )

    def alterar(
        self,
        *,
        categoria: CategoriaFinanceira,
        descricao: str,
        valor: Dinheiro,
        dia_vencimento: int,
        mes_vencimento: int | None,
        antecedencia_dias: int,
        limite_de_inadimplencia: int,
        chave_pix: ChavePix,
    ) -> None:
        if not self.ativa:
            raise erro("JA_ESTA_INATIVO")
        if valor.quantia <= 0:
            raise erro("VALOR_INVALIDO")
        if not categoria.ativa or categoria.natureza != NaturezaCategoria.ENTRADA:
            raise erro("CATEGORIA_INATIVA")
        if not chave_pix.ativa:
            raise erro("CHAVE_PIX_INATIVA")
        self.categoria = categoria
        self.descricao = descricao.strip()
        self.valor = valor.quantia
        self.dia_vencimento = dia_vencimento
        self.mes_vencimento = mes_vencimento
        self.antecedencia_dias = antecedencia_dias
        self.limite_de_inadimplencia = limite_de_inadimplencia
        self.chave_pix = chave_pix
        self.save()

    def desativar(self) -> None:
        if not self.ativa:
            raise erro("JA_ESTA_INATIVO")
        self.ativa = False
        self.save(update_fields=["ativa", "atualizada_em"])


class Suspensao(models.Model):
    """Aggregate root de suspensão temporária de cobranças recorrentes (INV-SUS-01..04)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    diretor_id = models.UUIDField()
    recorrencia = models.ForeignKey(
        Recorrencia, on_delete=models.PROTECT, null=True, blank=True, related_name="suspensoes"
    )
    inicio = models.DateField()
    fim = models.DateField(null=True, blank=True)
    justificativa = models.TextField(max_length=1000)
    situacao = models.CharField(
        max_length=12, choices=SituacaoSuspensao.choices, default=SituacaoSuspensao.VIGENTE
    )
    criada_por_id = models.UUIDField()
    encerrada_por_id = models.UUIDField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-criada_em",)
        indexes = (models.Index(fields=["diretor_id", "situacao"], name="suspensao_diretor_situacao"),)

    def __str__(self) -> str:
        return f"Suspensão {self.inicio} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Suspensões não são apagadas; encerre-as.")

    @classmethod
    def criar(
        cls,
        *,
        diretor_id: uuid.UUID,
        recorrencia: Recorrencia | None,
        periodo: Periodo,
        justificativa: str,
        criada_por_id: uuid.UUID,
    ) -> Suspensao:
        if recorrencia is not None and recorrencia.devedor_id != diretor_id:
            raise erro_validacao("recorrencia_id", "A recorrência informada não pertence a este diretor.")
        return cls.objects.create(
            diretor_id=diretor_id,
            recorrencia=recorrencia,
            inicio=periodo.inicio,
            fim=periodo.fim,
            justificativa=justificativa.strip(),
            situacao=SituacaoSuspensao.VIGENTE,
            criada_por_id=criada_por_id,
        )

    def encerrar(self, *, por_id: uuid.UUID | None, agora: datetime) -> None:
        if self.situacao != SituacaoSuspensao.VIGENTE:
            raise erro("SUSPENSAO_JA_ENCERRADA")
        self.situacao = SituacaoSuspensao.ENCERRADA
        self.encerrada_por_id = por_id
        self.encerrada_em = agora
        self.save(update_fields=["situacao", "encerrada_por_id", "encerrada_em"])


class Cobranca(models.Model):
    """Aggregate root de cobrança devida por um diretor ao clube (INV-COB-01..17)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    devedor_id = models.UUIDField()
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="cobrancas")
    categoria_nome = models.CharField(max_length=80)
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    vencimento = models.DateField()
    limite_de_inadimplencia = models.PositiveIntegerField(default=30)

    chave_pix = models.ForeignKey(ChavePix, on_delete=models.PROTECT, related_name="cobrancas")
    pix_chave = models.CharField(max_length=140)
    pix_nome_recebedor = models.CharField(max_length=100)
    pix_cidade = models.CharField(max_length=60)
    pix_copia_e_cola = models.TextField()

    situacao = models.CharField(max_length=16, choices=_SITUACOES_COBRANCA, default=SituacaoCobranca.ABERTA)
    recorrencia = models.ForeignKey(
        Recorrencia, on_delete=models.PROTECT, null=True, blank=True, related_name="cobrancas"
    )
    competencia = models.CharField(max_length=16, default="", blank=True)
    cobranca_origem = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="parcelas"
    )

    pausada_por_questionamento_em = models.DateField(null=True, blank=True)
    dias_pausados_inadimplencia = models.PositiveIntegerField(default=0)

    isencao_por_id = models.UUIDField(null=True, blank=True)
    isencao_justificativa = models.TextField(default="", blank=True)
    cancelamento_por_id = models.UUIDField(null=True, blank=True)
    cancelamento_motivo_id = models.UUIDField(null=True, blank=True)
    cancelamento_motivo_texto = models.CharField(max_length=200, default="", blank=True)
    cancelamento_texto = models.TextField(default="", blank=True)
    perdao_por_id = models.UUIDField(null=True, blank=True)
    perdao_motivo_id = models.UUIDField(null=True, blank=True)
    perdao_motivo_texto = models.CharField(max_length=200, default="", blank=True)
    perdao_texto = models.TextField(default="", blank=True)

    lembrete_3_dias_em = models.DateField(null=True, blank=True)
    lembrete_vencimento_em = models.DateField(null=True, blank=True)
    paga_em = models.DateTimeField(null=True, blank=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-criada_em", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("recorrencia", "devedor_id", "competencia"),
                condition=models.Q(recorrencia__isnull=False),
                name="cobranca_unica_por_recorrencia_competencia",
            ),
        )
        indexes = (
            models.Index(fields=["devedor_id", "situacao"], name="cobranca_por_devedor_situacao"),
            models.Index(fields=["situacao", "vencimento"], name="cobranca_por_situacao_venc"),
        )

    def __str__(self) -> str:
        return f"{self.descricao} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Cobranças não são apagadas; cancele ou isente.")

    @classmethod
    def criar(
        cls,
        *,
        devedor_id: uuid.UUID,
        categoria: CategoriaFinanceira,
        descricao: str,
        valor: Dinheiro,
        vencimento: date,
        limite_de_inadimplencia: int,
        chave_pix: ChavePix,
        hoje: date,
        recorrencia: Recorrencia | None = None,
        competencia: str = "",
        cobranca_origem: Cobranca | None = None,
    ) -> Cobranca:
        if valor.quantia <= 0:
            raise erro("VALOR_INVALIDO")
        if vencimento < hoje:
            raise erro("VENCIMENTO_NO_PASSADO")
        if not categoria.ativa or categoria.natureza != NaturezaCategoria.ENTRADA:
            raise erro("CATEGORIA_INATIVA")
        if not chave_pix.ativa:
            raise erro("CHAVE_PIX_INATIVA")

        cobranca_id = uuid.uuid7()
        copia_e_cola = gerar_pix_copia_e_cola(
            chave=chave_pix.chave,
            nome_recebedor=chave_pix.nome_recebedor,
            cidade=chave_pix.cidade,
            valor=valor.quantia,
            cobranca_id=cobranca_id,
        )
        return cls.objects.create(
            id=cobranca_id,
            devedor_id=devedor_id,
            categoria=categoria,
            categoria_nome=categoria.nome,
            descricao=descricao.strip(),
            valor=valor.quantia,
            vencimento=vencimento,
            limite_de_inadimplencia=limite_de_inadimplencia,
            chave_pix=chave_pix,
            pix_chave=chave_pix.chave,
            pix_nome_recebedor=chave_pix.nome_recebedor,
            pix_cidade=chave_pix.cidade,
            pix_copia_e_cola=copia_e_cola,
            situacao=SituacaoCobranca.ABERTA.value,
            recorrencia=recorrencia,
            competencia=competencia,
            cobranca_origem=cobranca_origem,
        )

    def _exigir_transicao(self, comando: ComandoCobranca, codigo_erro: str) -> None:
        if not transicao_cobranca_permitida(SituacaoCobranca(self.situacao), comando):
            raise erro(codigo_erro)

    def cancelar(
        self,
        *,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
    ) -> None:
        self._exigir_transicao(ComandoCobranca.CANCELAR, "NAO_PODE_CANCELAR")
        self.situacao = SituacaoCobranca.CANCELADA.value
        self.cancelamento_por_id = por_id
        self.cancelamento_motivo_id = motivo_id
        self.cancelamento_motivo_texto = motivo_texto
        self.cancelamento_texto = texto.strip()
        self.encerrada_em = agora
        self._fechar_questionamento_aberto(
            DecisaoQuestionamento.CANCELAR, por_id, motivo_id, motivo_texto, texto, agora
        )
        self.save()

    def isentar(self, *, por_id: uuid.UUID, justificativa: str, agora: datetime) -> None:
        self._exigir_transicao(ComandoCobranca.ISENTAR, "NAO_PODE_ISENTAR")
        if not justificativa.strip():
            raise erro_validacao("justificativa", "Informe a justificativa da isenção.")
        self.situacao = SituacaoCobranca.ISENTA.value
        self.isencao_por_id = por_id
        self.isencao_justificativa = justificativa.strip()
        self.encerrada_em = agora
        self.save()

    def registrar_pagamento(
        self,
        *,
        forma: FormaPagamento,
        data_pagamento: date,
        recebedor_id: uuid.UUID | None = None,
        anexo: AnexoSalvo | None = None,
    ) -> Pagamento:
        self._exigir_transicao(ComandoCobranca.REGISTRAR_PAGAMENTO, "NAO_ACEITA_PAGAMENTO")
        if self.pagamentos.filter(situacao=SituacaoPagamento.EM_VALIDACAO).exists():
            raise erro("NAO_ACEITA_PAGAMENTO")
        if forma == FormaPagamento.COMPROVANTE:
            if anexo is None or recebedor_id is not None:
                raise erro_validacao("comprovante", "Anexe o comprovante do pagamento.")
        else:
            if recebedor_id is None or recebedor_id == self.devedor_id or anexo is not None:
                raise erro("RECEBEDOR_INVALIDO")
        pagamento = Pagamento.objects.create(
            cobranca=self,
            forma=forma.value,
            data_pagamento=data_pagamento,
            recebedor_id=recebedor_id,
            comprovante_chave=anexo.chave if anexo else "",
            comprovante_nome=anexo.nome if anexo else "",
            comprovante_mime=anexo.mime if anexo else "",
            comprovante_tamanho=anexo.tamanho if anexo else None,
            situacao=SituacaoPagamento.EM_VALIDACAO,
        )
        self.situacao = SituacaoCobranca.EM_VALIDACAO.value
        self.save(update_fields=["situacao", "atualizada_em"])
        return pagamento

    def validar_pagamento(
        self,
        *,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
    ) -> Pagamento:
        self._exigir_transicao(ComandoCobranca.VALIDAR_PAGAMENTO, "NAO_ESTA_EM_VALIDACAO")
        if por_id == self.devedor_id:
            raise erro("DEVEDOR_NAO_VALIDA")
        pagamento = self.pagamentos.filter(situacao=SituacaoPagamento.EM_VALIDACAO).first()
        if pagamento is None:
            raise erro("NAO_ESTA_EM_VALIDACAO")
        pagamento.situacao = SituacaoPagamento.VALIDADO
        pagamento.decidido_por_id = por_id
        pagamento.motivo_id = motivo_id
        pagamento.motivo_texto = motivo_texto
        pagamento.decisao_texto = texto.strip()
        pagamento.decidido_em = agora
        pagamento.save()
        self.situacao = SituacaoCobranca.PAGA.value
        self.paga_em = agora
        self.encerrada_em = agora
        self.save(update_fields=["situacao", "paga_em", "encerrada_em", "atualizada_em"])
        return pagamento

    def rejeitar_pagamento(
        self,
        *,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
        hoje: date,
    ) -> Pagamento:
        self._exigir_transicao(ComandoCobranca.REJEITAR_PAGAMENTO, "NAO_ESTA_EM_VALIDACAO")
        if por_id == self.devedor_id:
            raise erro("DEVEDOR_NAO_VALIDA")
        pagamento = self.pagamentos.filter(situacao=SituacaoPagamento.EM_VALIDACAO).first()
        if pagamento is None:
            raise erro("NAO_ESTA_EM_VALIDACAO")
        pagamento.situacao = SituacaoPagamento.REJEITADO
        pagamento.decidido_por_id = por_id
        pagamento.motivo_id = motivo_id
        pagamento.motivo_texto = motivo_texto
        pagamento.decisao_texto = texto.strip()
        pagamento.decidido_em = agora
        pagamento.save()
        self.situacao = estado_sem_pagamento(self.vencimento, hoje).value
        self.save(update_fields=["situacao", "atualizada_em"])
        return pagamento

    def estornar(self) -> None:
        self._exigir_transicao(ComandoCobranca.ESTORNAR, "NAO_PODE_ESTORNAR")
        self.situacao = SituacaoCobranca.ESTORNADA.value
        self.save(update_fields=["situacao", "atualizada_em"])

    def marcar_lembrete_3_dias(self, hoje: date) -> bool:
        if (
            self.situacao != SituacaoCobranca.ABERTA
            or self.lembrete_3_dias_em is not None
            or self.tem_questionamento_aberto
        ):
            return False
        self.lembrete_3_dias_em = hoje
        self.save(update_fields=["lembrete_3_dias_em", "atualizada_em"])
        return True

    def marcar_lembrete_vencimento(self, hoje: date) -> bool:
        if (
            self.situacao != SituacaoCobranca.ABERTA
            or self.lembrete_vencimento_em is not None
            or self.tem_questionamento_aberto
        ):
            return False
        self.lembrete_vencimento_em = hoje
        self.save(update_fields=["lembrete_vencimento_em", "atualizada_em"])
        return True

    def marcar_atraso(self, hoje: date) -> bool:
        if (
            self.situacao != SituacaoCobranca.ABERTA
            or self.vencimento >= hoje
            or self.tem_questionamento_aberto
        ):
            return False
        self.situacao = SituacaoCobranca.ATRASADA.value
        self.save(update_fields=["situacao", "atualizada_em"])
        return True

    @property
    def tem_questionamento_aberto(self) -> bool:
        return self.questionamentos.filter(situacao=SituacaoQuestionamento.ABERTO).exists()

    def questionar(self, *, texto: str, hoje: date) -> Questionamento:
        self._exigir_transicao(ComandoCobranca.QUESTIONAR, "NAO_ACEITA_QUESTIONAMENTO")
        if self.tem_questionamento_aberto:
            raise erro("QUESTIONAMENTO_JA_ABERTO")
        limpo = texto.strip()
        if not limpo:
            raise erro_validacao("texto", "Descreva o motivo do questionamento.")
        q = Questionamento.objects.create(cobranca=self, texto=limpo, situacao=SituacaoQuestionamento.ABERTO)
        self.pausada_por_questionamento_em = hoje
        self.save(update_fields=["pausada_por_questionamento_em", "atualizada_em"])
        return q

    def decidir_questionamento(
        self,
        *,
        decisao: DecisaoQuestionamento,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
        hoje: date,
    ) -> Questionamento:
        self._exigir_transicao(ComandoCobranca.DECIDIR_QUESTIONAMENTO, "SEM_QUESTIONAMENTO_ABERTO")
        if por_id == self.devedor_id:
            raise erro("DEVEDOR_NAO_DECIDE")
        q = self.questionamentos.filter(situacao=SituacaoQuestionamento.ABERTO).first()
        if q is None:
            raise erro("SEM_QUESTIONAMENTO_ABERTO")

        q.situacao = SituacaoQuestionamento.DECIDIDO
        q.decisao = decisao.value
        q.decidido_por_id = por_id
        q.motivo_id = motivo_id
        q.motivo_texto = motivo_texto
        q.decisao_texto = texto.strip()
        q.decidido_em = agora
        q.save()

        if decisao == DecisaoQuestionamento.ISENTAR:
            self.situacao = SituacaoCobranca.ISENTA.value
            self.isencao_por_id = por_id
            self.isencao_justificativa = f"{motivo_texto} {texto.strip()}".strip()
            self.encerrada_em = agora
        elif decisao == DecisaoQuestionamento.CANCELAR:
            self.situacao = SituacaoCobranca.CANCELADA.value
            self.cancelamento_por_id = por_id
            self.cancelamento_motivo_id = motivo_id
            self.cancelamento_motivo_texto = motivo_texto
            self.cancelamento_texto = texto.strip()
            self.encerrada_em = agora
        else:
            pausa = dias_pausados_em_decisao(self.pausada_por_questionamento_em, self.vencimento, hoje)
            self.dias_pausados_inadimplencia += pausa
            self.pausada_por_questionamento_em = None

        self.save()
        return q

    def _fechar_questionamento_aberto(
        self,
        decisao: DecisaoQuestionamento,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
    ) -> None:
        q = self.questionamentos.filter(situacao=SituacaoQuestionamento.ABERTO).first()
        if q is not None:
            q.situacao = SituacaoQuestionamento.DECIDIDO
            q.decisao = decisao.value
            q.decidido_por_id = por_id
            q.motivo_id = motivo_id
            q.motivo_texto = motivo_texto
            q.decisao_texto = texto.strip()
            q.decidido_em = agora
            q.save()

    @property
    def convocacao_aberta(self) -> Convocacao | None:
        conv = getattr(self, "convocacao", None)
        if not isinstance(conv, Convocacao) or conv.decidido_em is not None:
            return None
        return conv

    def convocar(self, *, agora: datetime) -> Convocacao | None:
        if (
            self.situacao != SituacaoCobranca.ATRASADA
            or self.tem_questionamento_aberto
            or hasattr(self, "convocacao")
        ):
            return None
        return Convocacao.objects.create(cobranca=self, convocado_em=agora)

    def justificar_divida(self, *, texto: str, agora: datetime) -> Convocacao:
        self._exigir_transicao(ComandoCobranca.JUSTIFICAR_DIVIDA, "SEM_CONVOCACAO_ABERTA")
        conv = self.convocacao_aberta
        if conv is None:
            raise erro("SEM_CONVOCACAO_ABERTA")
        limpo = texto.strip()
        if not limpo:
            raise erro_validacao("texto", "Informe a justificativa da dívida.")
        conv.justificativa_do_devedor = limpo
        conv.justificada_em = agora
        conv.save(update_fields=["justificativa_do_devedor", "justificada_em"])
        return conv

    def perdoar(
        self,
        *,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
    ) -> None:
        self._exigir_transicao(ComandoCobranca.PERDOAR, "NAO_ESTA_ATRASADA")
        if por_id == self.devedor_id:
            raise erro("DEVEDOR_NAO_DECIDE")
        self.situacao = SituacaoCobranca.PERDOADA.value
        self.perdao_por_id = por_id
        self.perdao_motivo_id = motivo_id
        self.perdao_motivo_texto = motivo_texto
        self.perdao_texto = texto.strip()
        self.encerrada_em = agora
        self._registrar_decisao_convocacao(
            DecisaoDivida.PERDOAR, por_id, motivo_id, motivo_texto, texto, agora
        )
        self.save()

    def marcar_renegociada(
        self,
        *,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        valor_acordado: Decimal,
        quantidade_parcelas: int,
        agora: datetime,
    ) -> Renegociacao:
        self._exigir_transicao(ComandoCobranca.RENEGOCIAR, "NAO_ESTA_ATRASADA")
        if por_id == self.devedor_id:
            raise erro("DEVEDOR_NAO_DECIDE")
        self.situacao = SituacaoCobranca.RENEGOCIADA.value
        self.encerrada_em = agora
        self._registrar_decisao_convocacao(
            DecisaoDivida.RENEGOCIAR, por_id, motivo_id, motivo_texto, texto, agora
        )
        self.save(update_fields=["situacao", "encerrada_em", "atualizada_em"])
        return Renegociacao.objects.create(
            cobranca_original=self,
            valor_acordado=valor_acordado,
            quantidade_parcelas=quantidade_parcelas,
            decidido_por_id=por_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            decisao_texto=texto.strip(),
        )

    def manter_divida(
        self,
        *,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
    ) -> Convocacao:
        self._exigir_transicao(ComandoCobranca.MANTER_DIVIDA, "SEM_CONVOCACAO_ABERTA")
        if por_id == self.devedor_id:
            raise erro("DEVEDOR_NAO_DECIDE")
        conv = self.convocacao_aberta
        if conv is None:
            raise erro("SEM_CONVOCACAO_ABERTA")
        self._registrar_decisao_convocacao(
            DecisaoDivida.MANTER, por_id, motivo_id, motivo_texto, texto, agora
        )
        conv.refresh_from_db()
        return conv

    def _registrar_decisao_convocacao(
        self,
        decisao: DecisaoDivida,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
    ) -> None:
        conv = self.convocacao_aberta
        if conv is not None:
            conv.decisao = decisao.value
            conv.decidido_por_id = por_id
            conv.motivo_id = motivo_id
            conv.motivo_texto = motivo_texto
            conv.decisao_texto = texto.strip()
            conv.decidido_em = agora
            conv.save()


class Pagamento(models.Model):
    """Tentativa de pagamento registrada pelo devedor dentro de `Cobranca`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    cobranca = models.ForeignKey(Cobranca, on_delete=models.PROTECT, related_name="pagamentos")
    forma = models.CharField(max_length=15, choices=FormaPagamento.choices)
    data_pagamento = models.DateField()
    recebedor_id = models.UUIDField(null=True, blank=True)
    comprovante_chave = models.CharField(max_length=255, default="", blank=True)
    comprovante_nome = models.CharField(max_length=160, default="", blank=True)
    comprovante_mime = models.CharField(max_length=60, default="", blank=True)
    comprovante_tamanho = models.PositiveIntegerField(null=True, blank=True)
    situacao = models.CharField(
        max_length=16, choices=SituacaoPagamento.choices, default=SituacaoPagamento.EM_VALIDACAO
    )
    decidido_por_id = models.UUIDField(null=True, blank=True)
    motivo_id = models.UUIDField(null=True, blank=True)
    motivo_texto = models.CharField(max_length=200, default="", blank=True)
    decisao_texto = models.TextField(default="", blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)
    decidido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-registrado_em",)
        constraints = (
            models.UniqueConstraint(
                fields=("cobranca",),
                condition=models.Q(situacao="EM_VALIDACAO"),
                name="pagamento_em_validacao_unico",
            ),
        )

    def __str__(self) -> str:
        return f"Pagamento {self.forma} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Pagamentos não são apagados.")


class Questionamento(models.Model):
    """Questionamento de cobrança aberto pelo devedor."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    cobranca = models.ForeignKey(Cobranca, on_delete=models.PROTECT, related_name="questionamentos")
    texto = models.TextField(max_length=1000)
    situacao = models.CharField(
        max_length=12, choices=SituacaoQuestionamento.choices, default=SituacaoQuestionamento.ABERTO
    )
    decisao = models.CharField(max_length=16, choices=DecisaoQuestionamento.choices, default="", blank=True)
    decidido_por_id = models.UUIDField(null=True, blank=True)
    motivo_id = models.UUIDField(null=True, blank=True)
    motivo_texto = models.CharField(max_length=200, default="", blank=True)
    decisao_texto = models.TextField(default="", blank=True)
    aberto_em = models.DateTimeField(auto_now_add=True)
    decidido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-aberto_em",)
        constraints = (
            models.UniqueConstraint(
                fields=("cobranca",),
                condition=models.Q(situacao="ABERTO"),
                name="questionamento_aberto_unico",
            ),
        )

    def __str__(self) -> str:
        return f"Questionamento {self.id} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Questionamentos não são apagados.")


class Convocacao(models.Model):
    """Convocação de inadimplência vinculada a uma cobrança atrasada."""

    cobranca = models.OneToOneField(
        Cobranca, primary_key=True, on_delete=models.PROTECT, related_name="convocacao"
    )
    convocado_em = models.DateTimeField()
    justificativa_do_devedor = models.TextField(max_length=1000, default="", blank=True)
    justificada_em = models.DateTimeField(null=True, blank=True)
    decisao = models.CharField(max_length=16, choices=DecisaoDivida.choices, default="", blank=True)
    decidido_por_id = models.UUIDField(null=True, blank=True)
    motivo_id = models.UUIDField(null=True, blank=True)
    motivo_texto = models.CharField(max_length=200, default="", blank=True)
    decisao_texto = models.TextField(default="", blank=True)
    decidido_em = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Convocação {self.cobranca_id}"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Convocações não são apagadas.")


class Renegociacao(models.Model):
    """Acordo imutável que encerrou uma cobrança atrasada e gerou parcelas (INV-REN-01)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    cobranca_original = models.OneToOneField(Cobranca, on_delete=models.PROTECT, related_name="renegociacao")
    valor_acordado = models.DecimalField(max_digits=12, decimal_places=2)
    quantidade_parcelas = models.PositiveIntegerField()
    decidido_por_id = models.UUIDField()
    motivo_id = models.UUIDField()
    motivo_texto = models.CharField(max_length=200)
    decisao_texto = models.TextField(default="", blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Renegociação {self.id} ({self.quantidade_parcelas}x)"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise NaoPodeApagar("Renegociação é imutável após registrada.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Renegociações não são apagadas.")


class Entrada(models.Model):
    """Aggregate root de entrada sem devedor (patrocínio, rifa, ajuda) ou devolução."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    tipo = models.CharField(max_length=16, choices=TipoEntrada.choices, default=TipoEntrada.SEM_DEVEDOR)
    saida = models.ForeignKey(
        "Saida",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="devolucoes",
    )
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="entradas")
    categoria_nome = models.CharField(max_length=80)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    data = models.DateField()
    origem = models.CharField(max_length=150)
    evidencia_texto = models.TextField(max_length=1000, default="", blank=True)
    comprovante_chave = models.CharField(max_length=255, default="", blank=True)
    comprovante_nome = models.CharField(max_length=160, default="", blank=True)
    comprovante_mime = models.CharField(max_length=60, default="", blank=True)
    comprovante_tamanho = models.PositiveIntegerField(null=True, blank=True)
    registrada_por_id = models.UUIDField()
    situacao = models.CharField(
        max_length=16, choices=_SITUACOES_ENTRADA, default=SituacaoEntrada.EM_VALIDACAO.value
    )
    decidido_por_id = models.UUIDField(null=True, blank=True)
    motivo_id = models.UUIDField(null=True, blank=True)
    motivo_texto = models.CharField(max_length=200, default="", blank=True)
    decisao_texto = models.TextField(default="", blank=True)
    registrada_em = models.DateTimeField(auto_now_add=True)
    decidido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-registrada_em", "-id")
        indexes = (models.Index(fields=["situacao", "data"], name="entrada_por_situacao_data"),)

    def __str__(self) -> str:
        return f"{self.origem} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Entradas não são apagadas.")

    @classmethod
    def registrar(
        cls,
        *,
        categoria: CategoriaFinanceira,
        valor: Dinheiro,
        data: date,
        origem: str,
        evidencia_texto: str,
        anexo: AnexoSalvo | None,
        registrada_por_id: uuid.UUID,
        tipo: TipoEntrada = TipoEntrada.SEM_DEVEDOR,
        saida: Saida | None = None,
    ) -> Entrada:
        if valor.quantia <= 0:
            raise erro("VALOR_INVALIDO")
        if not categoria.ativa or categoria.natureza != NaturezaCategoria.ENTRADA:
            raise erro("CATEGORIA_INATIVA")
        texto_limpo = evidencia_texto.strip()
        if not texto_limpo and anexo is None:
            raise erro_validacao("evidencia_texto", "Informe o comprovante ou um texto de evidência.")
        if saida is not None:
            if tipo != TipoEntrada.DEVOLUCAO:
                raise erro("NAO_ACEITA_DEVOLUCAO")
            try:
                validar_devolucao_de_sobra(
                    situacao=SituacaoSaida(saida.situacao),
                    valor=valor.quantia,
                    total_enviado=saida.total_enviado(),
                    total_devolvido_ativo=saida.total_devolvido_ativo(),
                )
            except ErroDeRegraSaida as exc:
                raise _traduzir_regra(exc) from None
        return cls.objects.create(
            tipo=tipo,
            saida=saida,
            categoria=categoria,
            categoria_nome=categoria.nome,
            valor=valor.quantia,
            data=data,
            origem=origem.strip(),
            evidencia_texto=texto_limpo,
            comprovante_chave=anexo.chave if anexo else "",
            comprovante_nome=anexo.nome if anexo else "",
            comprovante_mime=anexo.mime if anexo else "",
            comprovante_tamanho=anexo.tamanho if anexo else None,
            registrada_por_id=registrada_por_id,
            situacao=SituacaoEntrada.EM_VALIDACAO.value,
        )

    def validar(
        self, *, por_id: uuid.UUID, motivo_id: uuid.UUID, motivo_texto: str, texto: str, agora: datetime
    ) -> None:
        self._decidir(
            ComandoEntrada.VALIDAR,
            SituacaoEntrada.VALIDADA,
            por_id=por_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            texto=texto,
            agora=agora,
        )

    def rejeitar(
        self, *, por_id: uuid.UUID, motivo_id: uuid.UUID, motivo_texto: str, texto: str, agora: datetime
    ) -> None:
        self._decidir(
            ComandoEntrada.REJEITAR,
            SituacaoEntrada.REJEITADA,
            por_id=por_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            texto=texto,
            agora=agora,
        )

    def estornar(self) -> None:
        if not transicao_entrada_permitida(SituacaoEntrada(self.situacao), ComandoEntrada.ESTORNAR):
            raise erro("NAO_PODE_ESTORNAR")
        if self.saida is not None and self.saida.situacao == SituacaoSaida.LIQUIDADA.value:
            raise erro(
                "NAO_PODE_ESTORNAR",
                mensagem="Estorne a saída liquidada antes de estornar esta devolução.",
            )
        self.situacao = SituacaoEntrada.ESTORNADA.value
        self.save(update_fields=["situacao"])

    def _decidir(
        self,
        comando: ComandoEntrada,
        nova_situacao: SituacaoEntrada,
        *,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
    ) -> None:
        if not transicao_entrada_permitida(SituacaoEntrada(self.situacao), comando):
            raise erro("NAO_ESTA_EM_VALIDACAO")
        if por_id == self.registrada_por_id:
            raise erro("REGISTRADOR_NAO_VALIDA")
        self.situacao = nova_situacao.value
        self.decidido_por_id = por_id
        self.motivo_id = motivo_id
        self.motivo_texto = motivo_texto
        self.decisao_texto = texto.strip()
        self.decidido_em = agora
        self.save()


class Cotacao(models.Model):
    """Arquivo de cotação anexado na abertura ou edição do gasto aprovado (CA-04, imutável)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    enviada_por_id = models.UUIDField()
    chave = models.CharField(max_length=255)
    nome = models.CharField(max_length=160)
    mime = models.CharField(max_length=60)
    tamanho = models.PositiveIntegerField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-criada_em", "-id")

    def __str__(self) -> str:
        return self.nome

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise NaoPodeApagar("Cotações não podem ser alteradas após o envio.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Cotações não são apagadas.")


class Saida(models.Model):
    """Aggregate root da execução financeira de um gasto aprovado (INV-SAI-01..09)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    solicitacao_id = models.UUIDField(db_index=True)
    versao_aprovada = models.PositiveIntegerField()
    solicitante_id = models.UUIDField()
    categoria = models.ForeignKey(CategoriaFinanceira, on_delete=models.PROTECT, related_name="saidas")
    categoria_nome = models.CharField(max_length=80)
    setor_id = models.UUIDField()
    setor_nome = models.CharField(max_length=80)
    evento_id = models.UUIDField(null=True, blank=True, db_index=True)
    cotacao = models.ForeignKey(
        Cotacao,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="saidas",
    )
    descricao = models.CharField(max_length=200)
    valor_aprovado = models.DecimalField(max_digits=12, decimal_places=2)
    valor_nao_reembolsado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    liquidacao_justificativa = models.TextField(default="", blank=True)
    situacao = models.CharField(
        max_length=20, choices=_SITUACOES_SAIDA, default=SituacaoSaida.AGUARDANDO_ENVIO.value
    )
    primeiro_envio_em = models.DateTimeField(null=True, blank=True)
    lembrete_5_dias_em = models.DateField(null=True, blank=True)
    aviso_7_dias_em = models.DateField(null=True, blank=True)
    liquidada_por_id = models.UUIDField(null=True, blank=True)
    liquidada_em = models.DateTimeField(null=True, blank=True)
    cancelada_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-criada_em", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("solicitacao_id",),
                condition=~models.Q(situacao="CANCELADA"),
                name="saida_ativa_unica_por_solicitacao",
            ),
            models.UniqueConstraint(
                fields=("solicitacao_id", "versao_aprovada"),
                name="saida_unica_por_versao_solicitacao",
            ),
            models.CheckConstraint(
                condition=models.Q(valor_aprovado__gt=Decimal("0.00")),
                name="saida_valor_aprovado_positivo",
            ),
        )
        indexes = (
            models.Index(fields=["situacao", "primeiro_envio_em"], name="saida_situacao_envio"),
            models.Index(fields=["solicitante_id", "situacao"], name="saida_solicitante_situacao"),
        )

    def __str__(self) -> str:
        return f"{self.descricao} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Saídas não são apagadas; cancele ou estorne.")

    def _exigir_transicao(self, comando: ComandoSaida, codigo_erro: str) -> None:
        if not transicao_saida_permitida(SituacaoSaida(self.situacao), comando):
            raise erro(codigo_erro)

    def complementos_aprovados_total(self) -> Decimal:
        valores = self.complementos.filter(situacao=SituacaoComplemento.APROVADO).values_list(
            "valor", flat=True
        )
        return sum(valores, Decimal("0.00"))

    def valor_aprovado_total(self) -> Decimal:
        return self.valor_aprovado + self.complementos_aprovados_total()

    def total_enviado(self) -> Decimal:
        return sum(self.envios.values_list("valor", flat=True), Decimal("0.00"))

    def total_devolvido_validado(self) -> Decimal:
        valores = self.devolucoes.filter(situacao=SituacaoEntrada.VALIDADA.value).values_list(
            "valor", flat=True
        )
        return sum(valores, Decimal("0.00"))

    def total_devolvido_pendente(self) -> Decimal:
        valores = self.devolucoes.filter(situacao=SituacaoEntrada.EM_VALIDACAO.value).values_list(
            "valor", flat=True
        )
        return sum(valores, Decimal("0.00"))

    def total_devolvido_ativo(self) -> Decimal:
        return self.total_devolvido_validado() + self.total_devolvido_pendente()

    def prestacao_vigente(self) -> PrestacaoDeContas | None:
        return self.prestacoes.filter(situacao=SituacaoPrestacao.VIGENTE).first()

    def complemento_em_andamento(self) -> Complemento | None:
        return self.complementos.filter(situacao=SituacaoComplemento.EM_ANDAMENTO).first()

    def complemento_aprovado_pendente_envio(self) -> Complemento | None:
        return (
            self.complementos.filter(situacao=SituacaoComplemento.APROVADO, envio__isnull=True)
            .order_by("aprovado_em", "criado_em")
            .first()
        )

    @classmethod
    def abrir(
        cls,
        *,
        solicitacao_id: uuid.UUID,
        versao_aprovada: int,
        solicitante_id: uuid.UUID,
        categoria: CategoriaFinanceira,
        setor_id: uuid.UUID,
        setor_nome: str,
        descricao: str,
        valor_aprovado: Dinheiro,
        evento_id: uuid.UUID | None = None,
        cotacao: Cotacao | None = None,
    ) -> Saida:
        if valor_aprovado.quantia <= 0:
            raise erro("VALOR_INVALIDO")
        if categoria.natureza != NaturezaCategoria.SAIDA:
            raise erro("CATEGORIA_INATIVA")
        return cls.objects.create(
            solicitacao_id=solicitacao_id,
            versao_aprovada=versao_aprovada,
            solicitante_id=solicitante_id,
            categoria=categoria,
            categoria_nome=categoria.nome,
            setor_id=setor_id,
            setor_nome=setor_nome.strip(),
            evento_id=evento_id,
            cotacao=cotacao,
            descricao=descricao.strip(),
            valor_aprovado=valor_aprovado.quantia,
            situacao=SituacaoSaida.AGUARDANDO_ENVIO.value,
        )

    def registrar_envio(
        self,
        *,
        valor: Dinheiro,
        enviado_por_id: uuid.UUID,
        enviado_em: datetime,
        comprovante: AnexoSalvo,
        complemento: Complemento | None = None,
    ) -> Envio:
        self._exigir_transicao(ComandoSaida.ENVIAR_RECURSO, "NAO_AGUARDA_ENVIO")
        tem_comp = bool(comprovante and comprovante.chave)
        situacao_atual = SituacaoSaida(self.situacao)
        if complemento is None:
            try:
                validar_envio_inicial(
                    situacao=situacao_atual,
                    valor=valor.quantia,
                    valor_aprovado=self.valor_aprovado,
                    tem_comprovante=tem_comp,
                )
            except ErroDeRegraSaida as exc:
                raise _traduzir_regra(exc) from None
            self.situacao = SituacaoSaida.RECURSO_ENVIADO.value
            self.primeiro_envio_em = enviado_em
            self.save(update_fields=["situacao", "primeiro_envio_em", "atualizada_em"])
        else:
            if (
                complemento.saida_id != self.id
                or complemento.situacao != SituacaoComplemento.APROVADO
                or Envio.objects.filter(complemento=complemento).exists()
            ):
                raise erro("NAO_AGUARDA_ENVIO")
            try:
                validar_envio_complemento(
                    situacao=situacao_atual,
                    valor=valor.quantia,
                    valor_aprovado=self.valor_aprovado,
                    complementos_aprovados=self.complementos_aprovados_total(),
                    total_ja_enviado=self.total_enviado(),
                    tem_complemento_aprovado_pendente=True,
                    tem_comprovante=tem_comp,
                )
            except ErroDeRegraSaida as exc:
                raise _traduzir_regra(exc) from None

        return Envio.objects.create(
            saida=self,
            complemento=complemento,
            valor=valor.quantia,
            enviado_por_id=enviado_por_id,
            enviado_em=enviado_em,
            comprovante_chave=comprovante.chave,
            comprovante_nome=comprovante.nome,
            comprovante_mime=comprovante.mime,
            comprovante_tamanho=comprovante.tamanho,
        )

    def prestar_contas(
        self,
        *,
        valor: Dinheiro,
        descricao: str,
        comprovante: AnexoSalvo | None,
        por_id: uuid.UUID,
    ) -> PrestacaoDeContas:
        if por_id != self.solicitante_id:
            raise erro("SO_O_SOLICITANTE")
        self._exigir_transicao(ComandoSaida.PRESTAR_CONTAS, "NAO_AGUARDA_PRESTACAO")
        if valor.quantia <= 0:
            raise erro("VALOR_INVALIDO")
        limpa = descricao.strip()
        if not limpa and comprovante is None:
            raise erro_validacao("comprovante", "Anexe o comprovante ou descreva a despesa realizada.")
        if self.prestacao_vigente() is not None:
            raise erro("NAO_AGUARDA_PRESTACAO")
        prestacao = PrestacaoDeContas.objects.create(
            saida=self,
            valor=valor.quantia,
            descricao=limpa,
            registrada_por_id=por_id,
            comprovante_chave=comprovante.chave if comprovante else "",
            comprovante_nome=comprovante.nome if comprovante else "",
            comprovante_mime=comprovante.mime if comprovante else "",
            comprovante_tamanho=comprovante.tamanho if comprovante else None,
        )
        self.situacao = SituacaoSaida.EM_CONFERENCIA.value
        self.save(update_fields=["situacao", "atualizada_em"])
        return prestacao

    def devolver_prestacao(
        self,
        *,
        por_id: uuid.UUID,
        motivo_id: uuid.UUID,
        motivo_texto: str,
        texto: str,
        agora: datetime,
    ) -> PrestacaoDeContas:
        self._exigir_transicao(ComandoSaida.DEVOLVER_PRESTACAO, "NAO_ESTA_EM_CONFERENCIA")
        if por_id == self.solicitante_id:
            raise erro("SOLICITANTE_NAO_LIQUIDA")
        prestacao = self.prestacao_vigente()
        if prestacao is None:
            raise erro("NAO_ESTA_EM_CONFERENCIA")
        prestacao.situacao = SituacaoPrestacao.DEVOLVIDA
        prestacao.devolvida_por_id = por_id
        prestacao.motivo_devolucao_id = motivo_id
        prestacao.motivo_devolucao_texto = motivo_texto
        prestacao.texto_devolucao = texto.strip()
        prestacao.devolvida_em = agora
        prestacao.save()
        self.situacao = SituacaoSaida.RECURSO_ENVIADO.value
        self.save(update_fields=["situacao", "atualizada_em"])
        return prestacao

    def liquidar(
        self,
        *,
        por_id: uuid.UUID,
        justificativa: str,
        agora: datetime,
    ) -> LiquidacaoResultado:
        self._exigir_transicao(ComandoSaida.LIQUIDAR, "NAO_ESTA_EM_CONFERENCIA")
        if por_id == self.solicitante_id:
            raise erro("SOLICITANTE_NAO_LIQUIDA")
        prestacao = self.prestacao_vigente()
        if prestacao is None:
            raise erro("NAO_ESTA_EM_CONFERENCIA")
        try:
            resultado = avaliar_liquidacao(
                situacao=SituacaoSaida(self.situacao),
                valor_prestacao=prestacao.valor,
                total_enviado=self.total_enviado(),
                total_devolvido_validado=self.total_devolvido_validado(),
                tem_devolucao_em_validacao=self.devolucoes.filter(
                    situacao=SituacaoEntrada.EM_VALIDACAO.value
                ).exists(),
                tem_complemento_em_andamento=self.complemento_em_andamento() is not None,
                tem_complemento_aprovado_sem_envio=self.complemento_aprovado_pendente_envio() is not None,
                justificativa=justificativa,
            )
        except ErroDeRegraSaida as exc:
            raise _traduzir_regra(exc) from None
        self.situacao = SituacaoSaida.LIQUIDADA.value
        self.valor_nao_reembolsado = resultado.valor_nao_reembolsado
        self.liquidacao_justificativa = justificativa.strip()
        self.liquidada_por_id = por_id
        self.liquidada_em = agora
        self.save(
            update_fields=[
                "situacao",
                "valor_nao_reembolsado",
                "liquidacao_justificativa",
                "liquidada_por_id",
                "liquidada_em",
                "atualizada_em",
            ]
        )
        return resultado

    def cancelar(self, *, agora: datetime) -> None:
        self._exigir_transicao(ComandoSaida.CANCELAR, "NAO_PODE_CANCELAR")
        if self.envios.exists():
            raise erro("NAO_PODE_CANCELAR")
        self.situacao = SituacaoSaida.CANCELADA.value
        self.cancelada_em = agora
        self.save(update_fields=["situacao", "cancelada_em", "atualizada_em"])

    def estornar(self) -> None:
        self._exigir_transicao(ComandoSaida.ESTORNAR, "NAO_PODE_ESTORNAR")
        self.situacao = SituacaoSaida.ESTORNADA.value
        self.save(update_fields=["situacao", "atualizada_em"])

    def marcar_lembrete_5_dias(self, hoje: date) -> bool:
        primeiro_envio = self.primeiro_envio_em.date() if self.primeiro_envio_em else None
        resultado = avaliar_lembretes_prestacao(
            situacao=SituacaoSaida(self.situacao),
            primeiro_envio_em=primeiro_envio,
            hoje=hoje,
            lembrete_5_dias_em=self.lembrete_5_dias_em,
            aviso_7_dias_em=self.aviso_7_dias_em,
        )
        if not resultado.enviar_lembrete_5_dias:
            return False
        self.lembrete_5_dias_em = hoje
        self.save(update_fields=["lembrete_5_dias_em", "atualizada_em"])
        return True

    def marcar_aviso_7_dias(self, hoje: date) -> bool:
        primeiro_envio = self.primeiro_envio_em.date() if self.primeiro_envio_em else None
        resultado = avaliar_lembretes_prestacao(
            situacao=SituacaoSaida(self.situacao),
            primeiro_envio_em=primeiro_envio,
            hoje=hoje,
            lembrete_5_dias_em=self.lembrete_5_dias_em,
            aviso_7_dias_em=self.aviso_7_dias_em,
        )
        if not resultado.enviar_aviso_7_dias:
            return False
        self.aviso_7_dias_em = hoje
        self.save(update_fields=["aviso_7_dias_em", "atualizada_em"])
        return True


class Complemento(models.Model):
    """Pedido complementar de orçamento vinculado a uma saída em conferência (RF-079, P12)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    saida = models.ForeignKey(Saida, on_delete=models.PROTECT, related_name="complementos")
    solicitacao_id = models.UUIDField(unique=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    situacao = models.CharField(
        max_length=16, choices=SituacaoComplemento.choices, default=SituacaoComplemento.EM_ANDAMENTO
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)
    decidido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-criado_em", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("saida",),
                condition=models.Q(situacao="EM_ANDAMENTO"),
                name="complemento_em_andamento_unico",
            ),
            models.CheckConstraint(
                condition=models.Q(valor__gt=Decimal("0.00")),
                name="complemento_valor_positivo",
            ),
        )

    def __str__(self) -> str:
        return f"Complemento {self.valor} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Complementos não são apagados.")

    def aprovar(self, agora: datetime, *, valor: Dinheiro | None = None) -> None:
        if self.situacao != SituacaoComplemento.EM_ANDAMENTO:
            return
        if valor is not None:
            self.valor = valor.quantia
        self.situacao = SituacaoComplemento.APROVADO
        self.aprovado_em = agora
        self.decidido_em = agora
        self.save()

    def recusar(self, agora: datetime) -> None:
        if self.situacao != SituacaoComplemento.EM_ANDAMENTO:
            return
        self.situacao = SituacaoComplemento.RECUSADO
        self.decidido_em = agora
        self.save()

    def cancelar(self, agora: datetime) -> None:
        if self.situacao != SituacaoComplemento.EM_ANDAMENTO:
            return
        self.situacao = SituacaoComplemento.CANCELADO
        self.decidido_em = agora
        self.save()


class Envio(models.Model):
    """Remessa financeira efetiva de recurso para o solicitante da saída (imutável)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    saida = models.ForeignKey(Saida, on_delete=models.PROTECT, related_name="envios")
    complemento = models.OneToOneField(
        Complemento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="envio",
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    enviado_por_id = models.UUIDField()
    enviado_em = models.DateTimeField()
    comprovante_chave = models.CharField(max_length=255)
    comprovante_nome = models.CharField(max_length=160)
    comprovante_mime = models.CharField(max_length=60)
    comprovante_tamanho = models.PositiveIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("enviado_em", "criado_em", "id")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(valor__gt=Decimal("0.00")),
                name="envio_valor_positivo",
            ),
        )

    def __str__(self) -> str:
        return f"Envio {self.valor}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise NaoPodeApagar("Envios são imutáveis após o registro.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Envios não são apagados.")


class PrestacaoDeContas(models.Model):
    """Prestação de contas submetida pelo solicitante para conferência (INV-SAI-04)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    saida = models.ForeignKey(Saida, on_delete=models.PROTECT, related_name="prestacoes")
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    descricao = models.TextField(max_length=1000, default="", blank=True)
    registrada_por_id = models.UUIDField()
    registrada_em = models.DateTimeField(auto_now_add=True)
    situacao = models.CharField(
        max_length=12, choices=SituacaoPrestacao.choices, default=SituacaoPrestacao.VIGENTE
    )
    devolvida_por_id = models.UUIDField(null=True, blank=True)
    motivo_devolucao_id = models.UUIDField(null=True, blank=True)
    motivo_devolucao_texto = models.CharField(max_length=200, default="", blank=True)
    texto_devolucao = models.TextField(default="", blank=True)
    devolvida_em = models.DateTimeField(null=True, blank=True)
    comprovante_chave = models.CharField(max_length=255, default="", blank=True)
    comprovante_nome = models.CharField(max_length=160, default="", blank=True)
    comprovante_mime = models.CharField(max_length=60, default="", blank=True)
    comprovante_tamanho = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("-registrada_em", "-id")
        constraints = (
            models.UniqueConstraint(
                fields=("saida",),
                condition=models.Q(situacao="VIGENTE"),
                name="prestacao_vigente_unica_por_saida",
            ),
            models.CheckConstraint(
                condition=models.Q(valor__gt=Decimal("0.00")),
                name="prestacao_valor_positivo",
            ),
            models.CheckConstraint(
                condition=~models.Q(descricao="") | ~models.Q(comprovante_chave=""),
                name="prestacao_exige_comprovante_ou_descricao",
            ),
        )

    def __str__(self) -> str:
        return f"Prestação {self.valor} ({self.situacao})"

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Prestações de contas não são apagadas.")


class Estorno(models.Model):
    """Lançamento compensatório ligado a registro financeiro encerrado (ADR-013, INV-SAI-09)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    alvo_tipo = models.CharField(max_length=12, choices=AlvoEstorno.choices)
    saida = models.OneToOneField(
        Saida, on_delete=models.PROTECT, null=True, blank=True, related_name="estorno"
    )
    entrada = models.OneToOneField(
        Entrada, on_delete=models.PROTECT, null=True, blank=True, related_name="estorno"
    )
    cobranca = models.OneToOneField(
        Cobranca, on_delete=models.PROTECT, null=True, blank=True, related_name="estorno"
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    motivo_id = models.UUIDField()
    motivo_texto = models.CharField(max_length=200)
    justificativa = models.TextField(max_length=1000)
    registrado_por_id = models.UUIDField()
    registrado_em = models.DateTimeField()

    class Meta:
        ordering = ("-registrado_em", "-id")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(valor__gt=Decimal("0.00")),
                name="estorno_valor_positivo",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        alvo_tipo="SAIDA",
                        saida__isnull=False,
                        entrada__isnull=True,
                        cobranca__isnull=True,
                    )
                    | models.Q(
                        alvo_tipo="ENTRADA",
                        saida__isnull=True,
                        entrada__isnull=False,
                        cobranca__isnull=True,
                    )
                    | models.Q(
                        alvo_tipo="COBRANCA",
                        saida__isnull=True,
                        entrada__isnull=True,
                        cobranca__isnull=False,
                    )
                ),
                name="estorno_alvo_unico_coerente",
            ),
        )

    def __str__(self) -> str:
        return f"Estorno {self.alvo_tipo} ({self.valor})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise NaoPodeApagar("Estornos são lançamentos imutáveis.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NaoPodeApagar("Estornos não são apagados.")
