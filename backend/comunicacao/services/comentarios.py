"""Comentários: comentar, editar o próprio, ocultar e reexibir (cenários 7 a 9 da funcional; RF-135 a RF-138).

A ordem de bloqueio é sempre comunicado → comentário. Nada é apagado: o texto de cada edição fica em
`VersaoDeComentario` (D1), e o oculto continua no banco, visível a quem pode (autor, quem gerencia, admin).
"""

import uuid

from django.db import transaction
from django.utils import timezone

from auditoria import public as auditoria
from comunicacao.domain.autorizacao import Comando, avaliar, ocultar_pela_gerencia, pode_ver_comentario
from comunicacao.domain.regras import validar_comentario, validar_motivo
from comunicacao.domain.valores import SituacaoDoComentario
from comunicacao.erros import erro, invalido
from comunicacao.models import Comentario, Comunicado, VersaoDeComentario
from comunicacao.services import avisos
from comunicacao.services.autorizacao import Quem, exigir, exigir_leitura_de_gestao, quem
from comunicacao.services.comunicados import bloquear

ITEM = "comentario"


def _bloquear(comentario_id: uuid.UUID, ator: Quem) -> tuple[Comunicado, Comentario]:
    """Bloqueia o comunicado e depois o comentário. Quem não pode ver um dos dois recebe `NOT_FOUND`."""
    achado = Comentario.objects.filter(pk=comentario_id).values_list("comunicado_id", flat=True).first()
    if achado is None:
        raise erro("NOT_FOUND")
    comunicado = bloquear(achado, ator)
    comentario = Comentario.objects.select_for_update().get(pk=comentario_id)
    fatos = ator.fatos(comunicado=comunicado, comentario=comentario)
    if not pode_ver_comentario(SituacaoDoComentario(comentario.situacao), fatos):
        raise erro("NOT_FOUND")
    return comunicado, comentario


@transaction.atomic
def comentar(ator_id: uuid.UUID, comunicado_id: uuid.UUID, texto: str) -> Comentario:
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = bloquear(comunicado_id, ator)
    exigir(avaliar(Comando.COMENTAR, ator.fatos(comunicado=comunicado)))
    erros = validar_comentario(texto)
    if erros:
        raise invalido(erros)

    comentario = Comentario.objects.create(comunicado=comunicado, autor_id=ator_id, texto=texto)
    VersaoDeComentario.objects.create(comentario=comentario, numero=1, texto=texto)
    auditoria.registrar(
        ator_id=ator_id,
        acao="COMENTARIO_CRIADO",
        item_tipo=ITEM,
        item_id=comentario.id,
        dados={"comunicado_id": str(comunicado.id)},
    )
    avisos.comentario_novo(comunicado, comentario)
    return comentario


@transaction.atomic
def editar(ator_id: uuid.UUID, comentario_id: uuid.UUID, texto: str) -> Comentario:
    """Só o autor, com o comunicado publicado; marca "editado" e não notifica (RF-136)."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado, comentario = _bloquear(comentario_id, ator)
    exigir(avaliar(Comando.EDITAR_COMENTARIO, ator.fatos(comunicado=comunicado, comentario=comentario)))
    erros = validar_comentario(texto)
    if erros:
        raise invalido(erros)

    anterior = VersaoDeComentario.objects.filter(comentario=comentario).count()
    comentario.texto = texto
    comentario.editado_em = timezone.now()
    comentario.save()
    VersaoDeComentario.objects.create(comentario=comentario, numero=anterior + 1, texto=texto)
    auditoria.registrar(
        ator_id=ator_id,
        acao="COMENTARIO_EDITADO",
        item_tipo=ITEM,
        item_id=comentario.id,
        dados={"versao_anterior": anterior, "versao_nova": anterior + 1},
    )
    return comentario


@transaction.atomic
def ocultar(ator_id: uuid.UUID, comentario_id: uuid.UUID, motivo: str = "") -> Comentario:
    """O autor oculta o próprio, sem motivo; quem gerencia oculta o de qualquer um, com motivo (RF-137)."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado, comentario = _bloquear(comentario_id, ator)
    fatos = ator.fatos(comunicado=comunicado, comentario=comentario)
    exigir(avaliar(Comando.OCULTAR_COMENTARIO, fatos))
    pela_gerencia = ocultar_pela_gerencia(fatos)
    if pela_gerencia:
        erros = validar_motivo(motivo)
        if erros:
            raise invalido(erros)

    comentario.situacao = SituacaoDoComentario.OCULTO.value
    comentario.oculto_por_id = ator_id
    comentario.oculto_pela_gerencia = pela_gerencia
    comentario.motivo_da_ocultacao = motivo if pela_gerencia else ""
    comentario.oculto_em = timezone.now()
    comentario.save()
    auditoria.registrar(
        ator_id=ator_id,
        acao="COMENTARIO_OCULTADO",
        item_tipo=ITEM,
        item_id=comentario.id,
        justificativa=comentario.motivo_da_ocultacao,
        dados={"pela_gerencia": pela_gerencia, "comunicado_id": str(comunicado.id)},
    )
    return comentario


@transaction.atomic
def reexibir(ator_id: uuid.UUID, comentario_id: uuid.UUID) -> Comentario:
    """O autor reexibe o que ele mesmo ocultou; o que a gerência ocultou, só a gerência (P16)."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado, comentario = _bloquear(comentario_id, ator)
    exigir(avaliar(Comando.REEXIBIR_COMENTARIO, ator.fatos(comunicado=comunicado, comentario=comentario)))

    comentario.situacao = SituacaoDoComentario.VISIVEL.value
    comentario.oculto_por_id = None
    comentario.oculto_pela_gerencia = False
    comentario.motivo_da_ocultacao = ""
    comentario.oculto_em = None
    comentario.save()
    auditoria.registrar(
        ator_id=ator_id,
        acao="COMENTARIO_REEXIBIDO",
        item_tipo=ITEM,
        item_id=comentario.id,
        dados={"comunicado_id": str(comunicado.id)},
    )
    return comentario
