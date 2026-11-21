"""Comunicados: publicar, editar, despublicar, republicar, fixar e desafixar (cenários 1 a 5 da funcional).

Todo serviço abre a transação, confere quem age, bloqueia o comunicado, grava, audita e notifica na mesma
transação (o e-mail sai depois do commit). A conferência vai na ordem: leitura de gestão (403) → existência e
visibilidade (404) → quem pode (403) → entrada (400) → situação (422).
"""

import uuid
from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from auditoria import public as auditoria
from comunicacao.domain.autorizacao import Comando, avaliar, pode_ver_comunicado
from comunicacao.domain.regras import validar_comunicado, validar_motivo
from comunicacao.domain.valores import SituacaoDoComunicado, SituacaoDoDocumento
from comunicacao.erros import erro, invalido
from comunicacao.models import Comunicado, Documento, VersaoDeComunicado, VinculoDeDocumento
from comunicacao.services import avisos
from comunicacao.services.autorizacao import Quem, exigir, exigir_leitura_de_gestao, quem

ITEM = "comunicado"


def bloquear(comunicado_id: uuid.UUID, ator: Quem) -> Comunicado:
    """O comunicado com a linha bloqueada. Quem não pode vê-lo recebe `NOT_FOUND`, como se não existisse."""
    comunicado = Comunicado.objects.select_for_update().filter(pk=comunicado_id).first()
    if comunicado is None:
        raise erro("NOT_FOUND")
    fatos = ator.fatos(comunicado=comunicado)
    if not pode_ver_comunicado(SituacaoDoComunicado(comunicado.situacao), fatos):
        raise erro("NOT_FOUND")
    return comunicado


def _sem_repeticao(ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
    return list(dict.fromkeys(ids))


def _documentos_a_vincular(ids: list[uuid.UUID]) -> list[Documento]:
    """Os documentos que passam a ser vinculados: têm de existir e estar vigentes (CA-10)."""
    if not ids:
        return []
    achados = {d.id: d for d in Documento.objects.filter(pk__in=ids)}
    if len(achados) != len(ids):
        raise invalido({"documentos_ids": ["Há documento que não existe."]})
    if any(d.situacao == SituacaoDoDocumento.ARQUIVADO for d in achados.values()):
        raise invalido({"documentos_ids": ["Não se vincula documento arquivado."]})
    return [achados[i] for i in ids]


def _ativos(comunicado: Comunicado) -> dict[uuid.UUID, VinculoDeDocumento]:
    vinculos = VinculoDeDocumento.objects.filter(comunicado=comunicado, desvinculado_em__isnull=True)
    return {v.documento_id: v for v in vinculos}


def _vincular(comunicado: Comunicado, documentos: list[Documento]) -> None:
    for documento in documentos:
        VinculoDeDocumento.objects.create(comunicado=comunicado, documento=documento)


@transaction.atomic
def publicar(
    ator_id: uuid.UUID, *, tipo: str, titulo: str, texto: str, documentos_ids: Iterable[uuid.UUID] = ()
) -> Comunicado:
    ator = quem(ator_id)
    exigir(avaliar(Comando.PUBLICAR, ator.fatos()))
    erros = validar_comunicado(tipo, titulo, texto)
    if erros:
        raise invalido(erros)
    ids = _sem_repeticao(documentos_ids)
    documentos = _documentos_a_vincular(ids)

    comunicado = Comunicado.objects.create(
        tipo=tipo, titulo=titulo, texto=texto, autor_id=ator_id, publicado_em=timezone.now()
    )
    VersaoDeComunicado.objects.create(
        comunicado=comunicado, numero=1, titulo=titulo, texto=texto, autor_da_versao_id=ator_id
    )
    _vincular(comunicado, documentos)
    auditoria.registrar(
        ator_id=ator_id,
        acao="COMUNICADO_PUBLICADO",
        item_tipo=ITEM,
        item_id=comunicado.id,
        dados={"tipo": tipo, "documentos": [str(i) for i in ids]},
    )
    avisos.comunicado_publicado(comunicado)
    return comunicado


@transaction.atomic
def editar(
    ator_id: uuid.UUID,
    comunicado_id: uuid.UUID,
    *,
    titulo: str,
    texto: str,
    documentos_ids: Iterable[uuid.UUID] = (),
) -> Comunicado:
    """Troca título, texto e documentos; guarda a versão nova e não notifica (RF-132)."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = bloquear(comunicado_id, ator)
    exigir(avaliar(Comando.EDITAR_COMUNICADO, ator.fatos(comunicado=comunicado)))
    erros = validar_comunicado(comunicado.tipo, titulo, texto)
    if erros:
        raise invalido(erros)

    novos = _sem_repeticao(documentos_ids)
    ativos = _ativos(comunicado)
    entram = [i for i in novos if i not in ativos]
    saem = [i for i in ativos if i not in novos]
    documentos = _documentos_a_vincular(entram)

    versao_anterior = comunicado.versao
    comunicado.titulo = titulo
    comunicado.texto = texto
    comunicado.versao = versao_anterior + 1
    comunicado.editado_em = timezone.now()
    comunicado.save()
    VersaoDeComunicado.objects.create(
        comunicado=comunicado,
        numero=comunicado.versao,
        titulo=titulo,
        texto=texto,
        autor_da_versao_id=ator_id,
    )
    agora = timezone.now()
    for documento_id in saem:
        vinculo = ativos[documento_id]
        vinculo.desvinculado_em = agora
        vinculo.save(update_fields=["desvinculado_em"])
    _vincular(comunicado, documentos)
    auditoria.registrar(
        ator_id=ator_id,
        acao="COMUNICADO_EDITADO",
        item_tipo=ITEM,
        item_id=comunicado.id,
        dados={
            "versao_anterior": versao_anterior,
            "versao_nova": comunicado.versao,
            "documentos_vinculados": [str(i) for i in entram],
            "documentos_desvinculados": [str(i) for i in saem],
        },
    )
    return comunicado


@transaction.atomic
def despublicar(ator_id: uuid.UUID, comunicado_id: uuid.UUID, *, motivo: str) -> Comunicado:
    """Tira do feed, e da fixação, sem apagar; o motivo é obrigatório (RF-133)."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = bloquear(comunicado_id, ator)
    exigir(avaliar(Comando.DESPUBLICAR, ator.fatos(comunicado=comunicado)))
    erros = validar_motivo(motivo)
    if erros:
        raise invalido(erros)

    estava_fixado = comunicado.fixado_em is not None
    comunicado.situacao = SituacaoDoComunicado.DESPUBLICADO.value
    comunicado.fixado_em = None
    comunicado.despublicado_em = timezone.now()
    comunicado.despublicado_por_id = ator_id
    comunicado.motivo_da_despublicacao = motivo
    comunicado.save()
    if estava_fixado:
        auditoria.registrar(
            ator_id=ator_id, acao="COMUNICADO_DESAFIXADO", item_tipo=ITEM, item_id=comunicado.id
        )
    auditoria.registrar(
        ator_id=ator_id,
        acao="COMUNICADO_DESPUBLICADO",
        item_tipo=ITEM,
        item_id=comunicado.id,
        justificativa=motivo,
    )
    return comunicado


@transaction.atomic
def republicar(ator_id: uuid.UUID, comunicado_id: uuid.UUID) -> Comunicado:
    """Volta ao feed sem fixação e sem nova notificação (RF-133); o motivo antigo fica na auditoria."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = bloquear(comunicado_id, ator)
    exigir(avaliar(Comando.REPUBLICAR, ator.fatos(comunicado=comunicado)))

    comunicado.situacao = SituacaoDoComunicado.PUBLICADO.value
    comunicado.despublicado_em = None
    comunicado.despublicado_por_id = None
    comunicado.motivo_da_despublicacao = ""
    comunicado.save()
    auditoria.registrar(ator_id=ator_id, acao="COMUNICADO_REPUBLICADO", item_tipo=ITEM, item_id=comunicado.id)
    return comunicado


@transaction.atomic
def fixar(ator_id: uuid.UUID, comunicado_id: uuid.UUID) -> Comunicado:
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = bloquear(comunicado_id, ator)
    exigir(avaliar(Comando.FIXAR, ator.fatos(comunicado=comunicado)))

    comunicado.fixado_em = timezone.now()
    comunicado.save()
    auditoria.registrar(ator_id=ator_id, acao="COMUNICADO_FIXADO", item_tipo=ITEM, item_id=comunicado.id)
    return comunicado


@transaction.atomic
def desafixar(ator_id: uuid.UUID, comunicado_id: uuid.UUID) -> Comunicado:
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = bloquear(comunicado_id, ator)
    exigir(avaliar(Comando.DESAFIXAR, ator.fatos(comunicado=comunicado)))

    comunicado.fixado_em = None
    comunicado.save()
    auditoria.registrar(ator_id=ator_id, acao="COMUNICADO_DESAFIXADO", item_tipo=ITEM, item_id=comunicado.id)
    return comunicado
