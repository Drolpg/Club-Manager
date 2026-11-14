"""Dados de referência obrigatórios: categorias de entrada, permissões do setor Financeiro e motivos."""

import uuid

from django.db import migrations
from django.utils import timezone

CATEGORIAS_ENTRADA = ("Mensalidade", "Patrocínio", "Ajuda", "Rifa", "Diversos")

PERMISSOES_FINANCEIRO = (
    "cobrancas.criar",
    "pagamentos.validar",
    "entradas.registrar",
    "entradas.validar",
)

SISTEMA_CONCESSAO_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

MOTIVOS = {
    "financeiro.pagamento_validar": (
        "Conferido em conta pelo titular",
        "Confirmado recebimento em mão",
        "Valor conferido no extrato",
    ),
    "financeiro.pagamento_rejeitar": (
        "Valor não localizado na conta",
        "Comprovante ilegível ou incorreto",
        "Valor divergente da cobrança",
    ),
    "financeiro.cobranca_cancelar": (
        "Cobrança criada por engano",
        "Cobrança duplicada",
        "Acordo administrativo anterior",
    ),
    "financeiro.questionamento_decidir": (
        "Cobrança improcedente após conferência",
        "Cobrança válida e mantida conforme regra",
        "Erro de lançamento confirmado",
    ),
    "financeiro.divida_decidir": (
        "Acordo firmado com a diretoria",
        "Situação excepcional justificada",
        "Aguardando regularização combinada",
    ),
    "financeiro.entrada_validar": (
        "Valor conferido em conta pelo titular",
        "Recebimento confirmado pela tesouraria",
    ),
    "financeiro.entrada_rejeitar": (
        "Valor não localizado na conta",
        "Evidência insuficiente ou inconsistente",
    ),
}


def criar(apps, schema_editor):
    Categoria = apps.get_model("financeiro", "CategoriaFinanceira")
    for nome in CATEGORIAS_ENTRADA:
        if not Categoria.objects.filter(nome__iexact=nome, natureza="ENTRADA").exists():
            Categoria.objects.create(nome=nome, natureza="ENTRADA", ativa=True)

    Setor = apps.get_model("permissoes", "Setor")
    Concessao = apps.get_model("permissoes", "Concessao")
    financeiro = Setor.objects.filter(nome__iexact="Financeiro").first()
    if financeiro is not None:
        agora = timezone.now()
        for codigo in PERMISSOES_FINANCEIRO:
            ja_tem = Concessao.objects.filter(
                permissao=codigo,
                alvo_tipo="SETOR",
                setor=financeiro,
                revogada_em__isnull=True,
            ).exists()
            if not ja_tem:
                Concessao.objects.create(
                    permissao=codigo,
                    alvo_tipo="SETOR",
                    setor=financeiro,
                    concedida_por_id=SISTEMA_CONCESSAO_ID,
                    concedida_em=agora,
                )

    Motivo = apps.get_model("aprovacoes", "MotivoDeDecisao")
    for tipo, textos in MOTIVOS.items():
        for texto in textos:
            if not Motivo.objects.filter(tipo_de_decisao=tipo, texto__iexact=texto).exists():
                Motivo.objects.create(tipo_de_decisao=tipo, texto=texto)


def remover(apps, schema_editor):
    Cobranca = apps.get_model("financeiro", "Cobranca")
    Recorrencia = apps.get_model("financeiro", "Recorrencia")
    Entrada = apps.get_model("financeiro", "Entrada")
    Categoria = apps.get_model("financeiro", "CategoriaFinanceira")
    categorias_usadas = (
        set(Cobranca.objects.values_list("categoria_id", flat=True))
        | set(Recorrencia.objects.values_list("categoria_id", flat=True))
        | set(Entrada.objects.values_list("categoria_id", flat=True))
    )
    cats_qs = Categoria.objects.filter(nome__in=CATEGORIAS_ENTRADA, natureza="ENTRADA").exclude(
        id__in=categorias_usadas
    )
    if cats_qs.exists():
        cats_qs._raw_delete(cats_qs.db)

    Setor = apps.get_model("permissoes", "Setor")
    Concessao = apps.get_model("permissoes", "Concessao")
    financeiro = Setor.objects.filter(nome__iexact="Financeiro").first()
    if financeiro is not None:
        conc_qs = Concessao.objects.filter(
            permissao__in=PERMISSOES_FINANCEIRO,
            alvo_tipo="SETOR",
            setor=financeiro,
            concedida_por_id=SISTEMA_CONCESSAO_ID,
        )
        if conc_qs.exists():
            conc_qs._raw_delete(conc_qs.db)

    Motivo = apps.get_model("aprovacoes", "MotivoDeDecisao")
    Decisao = apps.get_model("aprovacoes", "Decisao")
    Pagamento = apps.get_model("financeiro", "Pagamento")
    Questionamento = apps.get_model("financeiro", "Questionamento")
    Convocacao = apps.get_model("financeiro", "Convocacao")
    Renegociacao = apps.get_model("financeiro", "Renegociacao")

    usados = (
        set(Cobranca.objects.exclude(cancelamento_motivo_id=None).values_list("cancelamento_motivo_id", flat=True))
        | set(Cobranca.objects.exclude(perdao_motivo_id=None).values_list("perdao_motivo_id", flat=True))
        | set(Pagamento.objects.exclude(motivo_id=None).values_list("motivo_id", flat=True))
        | set(Questionamento.objects.exclude(motivo_id=None).values_list("motivo_id", flat=True))
        | set(Convocacao.objects.exclude(motivo_id=None).values_list("motivo_id", flat=True))
        | set(Renegociacao.objects.values_list("motivo_id", flat=True))
        | set(Entrada.objects.exclude(motivo_id=None).values_list("motivo_id", flat=True))
        | set(Decisao.objects.values_list("motivo_id", flat=True))
    )
    for tipo, textos in MOTIVOS.items():
        motivos_qs = Motivo.objects.filter(tipo_de_decisao=tipo, texto__in=textos).exclude(id__in=usados)
        if motivos_qs.exists():
            motivos_qs._raw_delete(motivos_qs.db)


class Migration(migrations.Migration):
    dependencies = [
        ("financeiro", "0001_modelos_iniciais"),
        ("permissoes", "0002_cargos_e_setores_iniciais"),
        ("aprovacoes", "0003_versao_e_decisao_imutaveis"),
    ]

    operations = [
        migrations.RunPython(criar, remover),
    ]
