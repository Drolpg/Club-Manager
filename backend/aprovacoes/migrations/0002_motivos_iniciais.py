"""Dados de referência obrigatórios: a lista sugerida de motivos de decisão (decisão 1 da spec funcional).

O admin pode editar, desativar e criar outros. A reversão remove só os que nenhuma decisão usa.
"""

from django.db import migrations

MOTIVOS = {
    "solicitacao.aprovar": (
        "Dentro do orçamento",
        "Necessário para a atividade do clube",
        "Conforme combinado em reunião",
    ),
    "solicitacao.contestar": (
        "Valor acima do necessário",
        "Faltam detalhes dos itens",
        "Falta justificativa",
        "Data ou prazo a rever",
    ),
    "solicitacao.recusar": (
        "Sem caixa disponível",
        "Fora das prioridades do clube",
        "Pedido duplicado",
    ),
}


def criar(apps, schema_editor):
    Motivo = apps.get_model("aprovacoes", "MotivoDeDecisao")
    for tipo, textos in MOTIVOS.items():
        for texto in textos:
            if not Motivo.objects.filter(tipo_de_decisao=tipo, texto__iexact=texto).exists():
                Motivo.objects.create(tipo_de_decisao=tipo, texto=texto)


def remover(apps, schema_editor):
    Motivo = apps.get_model("aprovacoes", "MotivoDeDecisao")
    for tipo, textos in MOTIVOS.items():
        Motivo.objects.filter(tipo_de_decisao=tipo, texto__in=textos, decisoes__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("aprovacoes", "0001_solicitacao_versao_decisao_motivo"),
    ]

    operations = [
        migrations.RunPython(criar, remover),
    ]
