"""Referência obrigatória: as categorias iniciais (P8) e as concessões iniciais (P5, P6).

Os setores são encontrados pelo nome, como na `financeiro/0003`; setor ausente é pulado. A reversão remove só as
categorias que nenhum evento usa e só as concessões que esta migração criou. Vem antes dos gatilhos de
imutabilidade (`0003`), para a reversão poder remover as categorias.
"""

import uuid

from django.db import migrations
from django.utils import timezone

CATEGORIAS = ("Jogo", "Reunião", "Festa", "Outros")
SETORES_QUE_PROPOEM = ("Financeiro", "Futebol", "Eventos", "Operacional")
SETOR_QUE_APROVA = "Eventos"
SISTEMA = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _concessoes():
    concessoes = [(setor, "eventos.propor") for setor in SETORES_QUE_PROPOEM]
    concessoes.append((SETOR_QUE_APROVA, "eventos.aprovar"))
    return concessoes


def criar(apps, schema_editor):
    Categoria = apps.get_model("eventos", "CategoriaDeEvento")
    for nome in CATEGORIAS:
        if not Categoria.objects.filter(nome__iexact=nome).exists():
            Categoria.objects.create(nome=nome, ativa=True)

    Setor = apps.get_model("permissoes", "Setor")
    Concessao = apps.get_model("permissoes", "Concessao")
    agora = timezone.now()
    for nome_do_setor, permissao in _concessoes():
        setor = Setor.objects.filter(nome__iexact=nome_do_setor).first()
        if setor is None:
            continue
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
    Evento = apps.get_model("eventos", "Evento")
    Categoria = apps.get_model("eventos", "CategoriaDeEvento")
    usadas = set(Evento.objects.values_list("categoria_id", flat=True))
    categorias = Categoria.objects.filter(nome__in=CATEGORIAS).exclude(id__in=usadas)
    if categorias.exists():
        categorias._raw_delete(categorias.db)

    Concessao = apps.get_model("permissoes", "Concessao")
    criadas = Concessao.objects.filter(
        permissao__in=("eventos.propor", "eventos.aprovar"), alvo_tipo="SETOR", concedida_por_id=SISTEMA
    )
    if criadas.exists():
        criadas._raw_delete(criadas.db)


class Migration(migrations.Migration):
    dependencies = [
        ("eventos", "0001_categoria_evento_presenca"),
        ("permissoes", "0002_cargos_e_setores_iniciais"),
    ]

    operations = [migrations.RunPython(criar, remover)]
