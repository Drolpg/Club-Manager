"""Dados de referência: os setores e os cargos com que o sistema nasce (spec funcional, decisões 1 e 2).

Nenhum vem com permissão. O admin pode renomear, desativar e criar outros.
"""

from django.db import migrations

SETORES = ("Financeiro", "Futebol", "Eventos", "Operacional")
CARGOS = ("Presidente", "Vice-presidente", "Tesoureiro", "Secretário", "Diretor")


def criar(apps, schema_editor):
    for nome_do_modelo, nomes in (("Setor", SETORES), ("Cargo", CARGOS)):
        modelo = apps.get_model("permissoes", nome_do_modelo)
        for nome in nomes:
            if not modelo.objects.filter(nome__iexact=nome).exists():
                modelo.objects.create(nome=nome)


def remover(apps, schema_editor):
    # Só remove o que ninguém usa: um item já atribuído ou com concessão fica.
    Cargo = apps.get_model("permissoes", "Cargo")
    Setor = apps.get_model("permissoes", "Setor")
    Cargo.objects.filter(nome__in=CARGOS, classificacoes__isnull=True, concessoes__isnull=True).delete()
    Setor.objects.filter(nome__in=SETORES, classificacoes__isnull=True, concessoes__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("permissoes", "0001_cargo_setor_classificacao_concessao"),
    ]

    operations = [
        migrations.RunPython(criar, remover),
    ]
