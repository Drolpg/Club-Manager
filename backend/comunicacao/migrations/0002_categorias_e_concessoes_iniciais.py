"""Referência obrigatória: as categorias iniciais de documento e as concessões iniciais (P15).

Os setores são encontrados pelo nome, como na `eventos/0002`; setor ausente é pulado. A reversão remove só as
categorias que nenhum documento usa e só as concessões que esta migração criou. Vem antes dos gatilhos de
imutabilidade (`0003`), para a reversão poder remover as categorias.
"""

import uuid

from django.db import migrations
from django.utils import timezone

CATEGORIAS = ("Institucional", "Financeiro", "Eventos", "Outros")
SETORES = ("Financeiro", "Futebol", "Eventos", "Operacional")
PERMISSOES = ("comunicacao.publicar", "comunicacao.enviar_documentos")
SISTEMA = uuid.UUID("00000000-0000-0000-0000-000000000000")


def criar(apps, schema_editor):
    Categoria = apps.get_model("comunicacao", "CategoriaDeDocumento")
    for nome in CATEGORIAS:
        if not Categoria.objects.filter(nome__iexact=nome).exists():
            Categoria.objects.create(nome=nome, ativa=True)

    Setor = apps.get_model("permissoes", "Setor")
    Concessao = apps.get_model("permissoes", "Concessao")
    agora = timezone.now()
    for nome_do_setor in SETORES:
        setor = Setor.objects.filter(nome__iexact=nome_do_setor).first()
        if setor is None:
            continue
        for permissao in PERMISSOES:
            ja_tem = Concessao.objects.filter(
                permissao=permissao, alvo_tipo="SETOR", setor=setor, revogada_em__isnull=True
            ).exists()
            if not ja_tem:
                Concessao.objects.create(
                    permissao=permissao,
                    alvo_tipo="SETOR",
                    setor=setor,
                    concedida_por_id=SISTEMA,
                    concedida_em=agora,
                )


def remover(apps, schema_editor):
    Documento = apps.get_model("comunicacao", "Documento")
    Categoria = apps.get_model("comunicacao", "CategoriaDeDocumento")
    usadas = set(Documento.objects.exclude(categoria__isnull=True).values_list("categoria_id", flat=True))
    categorias = Categoria.objects.filter(nome__in=CATEGORIAS).exclude(id__in=usadas)
    if categorias.exists():
        categorias._raw_delete(categorias.db)

    Concessao = apps.get_model("permissoes", "Concessao")
    criadas = Concessao.objects.filter(permissao__in=PERMISSOES, alvo_tipo="SETOR", concedida_por_id=SISTEMA)
    if criadas.exists():
        criadas._raw_delete(criadas.db)


class Migration(migrations.Migration):
    dependencies = [
        ("comunicacao", "0001_modelos"),
        ("permissoes", "0002_cargos_e_setores_iniciais"),
    ]

    operations = [migrations.RunPython(criar, remover)]
