"""Leitura do feed: o feed, os despublicados e o detalhe do comunicado (CA-02, CA-08).

Devolve dicts com campos declarados, nunca o modelo. A contagem de reações e a de comentários ignoram o que
está retirado ou oculto (P18).
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Count, Q, QuerySet

from acesso import public as acesso
from comunicacao.domain.autorizacao import (
    acoes_do_comentario,
    acoes_do_comunicado,
    pode_ver_comunicado,
)
from comunicacao.domain.regras import TIPOS_DE_REACAO
from comunicacao.domain.valores import SituacaoDoComentario, SituacaoDoComunicado
from comunicacao.erros import erro
from comunicacao.models import Comentario, Comunicado, Reacao, VinculoDeDocumento
from comunicacao.services.autorizacao import Quem, exigir_leitura_de_gestao, quem

LIMITE_PADRAO = 20
LIMITE_MAXIMO = 50


def limite_valido(limite: int | None) -> int:
    if limite is None:
        return LIMITE_PADRAO
    return max(1, min(limite, LIMITE_MAXIMO))


@dataclass
class _Nomes:
    """Cache dos nomes de uma resposta: uma consulta a `acesso` por pessoa."""

    por_id: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)

    def pessoa(self, usuario_id: uuid.UUID) -> dict[str, Any]:
        if usuario_id not in self.por_id:
            usuario = acesso.usuario_por_id(usuario_id)
            self.por_id[usuario_id] = {"id": usuario_id, "nome": usuario.nome if usuario else ""}
        return self.por_id[usuario_id]


def _contagem_vazia() -> dict[str, int]:
    return dict.fromkeys(TIPOS_DE_REACAO, 0)


@dataclass
class _Lote:
    """O que se lê do banco de uma vez para uma lista de comunicados."""

    documentos: dict[uuid.UUID, list[dict[str, Any]]]
    contagem: dict[uuid.UUID, dict[str, int]]
    quem_reagiu: dict[uuid.UUID, dict[str, list[uuid.UUID]]]
    minhas: dict[uuid.UUID, str]
    comentarios: dict[uuid.UUID, int]


def _ler_lote(comunicados: list[Comunicado], ator_id: uuid.UUID) -> _Lote:
    ids = [c.id for c in comunicados]
    documentos: dict[uuid.UUID, list[dict[str, Any]]] = {i: [] for i in ids}
    vinculos = VinculoDeDocumento.objects.filter(
        comunicado_id__in=ids, desvinculado_em__isnull=True
    ).select_related("documento")
    for vinculo in vinculos.order_by("vinculado_em", "id"):
        documento = vinculo.documento
        documentos[vinculo.comunicado_id].append(
            {
                "id": documento.id,
                "titulo": documento.titulo,
                "tipo": documento.tipo,
                "situacao": documento.situacao,
            }
        )

    contagem = {i: _contagem_vazia() for i in ids}
    quem_reagiu: dict[uuid.UUID, dict[str, list[uuid.UUID]]] = {
        i: {t: [] for t in TIPOS_DE_REACAO} for i in ids
    }
    minhas: dict[uuid.UUID, str] = {}
    reacoes = Reacao.objects.filter(comunicado_id__in=ids, retirada_em__isnull=True).order_by(
        "criada_em", "id"
    )
    for reacao in reacoes:
        contagem[reacao.comunicado_id][reacao.tipo] += 1
        quem_reagiu[reacao.comunicado_id][reacao.tipo].append(reacao.diretor_id)
        if reacao.diretor_id == ator_id:
            minhas[reacao.comunicado_id] = reacao.tipo

    total = dict.fromkeys(ids, 0)
    visiveis = Comentario.objects.filter(comunicado_id__in=ids, situacao=SituacaoDoComentario.VISIVEL.value)
    for linha in visiveis.values("comunicado_id").annotate(n=Count("id")):
        total[linha["comunicado_id"]] = linha["n"]
    return _Lote(documentos, contagem, quem_reagiu, minhas, total)


def _item(
    comunicado: Comunicado, ator: Quem, lote: _Lote, nomes: _Nomes, *, com_quem_reagiu: bool = False
) -> dict[str, Any]:
    minha = lote.minhas.get(comunicado.id)
    fatos = ator.fatos(comunicado=comunicado, tem_reacao_ativa=minha is not None)
    reacoes: dict[str, Any] = {"contagem": lote.contagem[comunicado.id], "minha": minha}
    if com_quem_reagiu:
        reacoes["quem"] = {
            tipo: [nomes.pessoa(i) for i in ids] for tipo, ids in lote.quem_reagiu[comunicado.id].items()
        }
    despublicado = None
    if comunicado.situacao == SituacaoDoComunicado.DESPUBLICADO:
        por = comunicado.despublicado_por_id
        despublicado = {
            "em": comunicado.despublicado_em,
            "por": nomes.pessoa(por) if por else None,
            "motivo": comunicado.motivo_da_despublicacao,
        }
    return {
        "id": comunicado.id,
        "tipo": comunicado.tipo,
        "titulo": comunicado.titulo,
        "texto": comunicado.texto,
        "autor": nomes.pessoa(comunicado.autor_id),
        "situacao": comunicado.situacao,
        "fixado": comunicado.fixado_em is not None,
        "fixado_em": comunicado.fixado_em,
        "publicado_em": comunicado.publicado_em,
        "editado": comunicado.editado_em is not None,
        "editado_em": comunicado.editado_em,
        "despublicado": despublicado,
        "documentos": lote.documentos[comunicado.id],
        "reacoes": reacoes,
        "total_de_comentarios": lote.comentarios[comunicado.id],
        "acoes": [comando.value for comando in acoes_do_comunicado(fatos)],
    }


def _itens(comunicados: list[Comunicado], ator: Quem) -> list[dict[str, Any]]:
    lote = _ler_lote(comunicados, ator.ator_id)
    nomes = _Nomes()
    return [_item(c, ator, lote, nomes) for c in comunicados]


def _depois_de(qs: QuerySet[Comunicado], antes: uuid.UUID | None) -> QuerySet[Comunicado]:
    """O cursor é o ID do último item da página anterior; o UUID v7 ordena pela criação."""
    if antes is None:
        return qs
    if not Comunicado.objects.filter(pk=antes).exists():
        raise erro("NOT_FOUND")
    return qs.filter(id__lt=antes)


def _pagina(
    qs: QuerySet[Comunicado], antes: uuid.UUID | None, limite: int | None
) -> tuple[list[Comunicado], bool]:
    tamanho = limite_valido(limite)
    achados = list(_depois_de(qs, antes).order_by("-id")[: tamanho + 1])
    return achados[:tamanho], len(achados) > tamanho


def feed(ator_id: uuid.UUID, *, antes: uuid.UUID | None = None, limite: int | None = None) -> dict[str, Any]:
    """Os publicados: fixados à parte, só na primeira página (D3); o resto, do mais novo ao mais antigo."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    publicados = Comunicado.objects.filter(situacao=SituacaoDoComunicado.PUBLICADO.value)
    fixados: list[Comunicado] = []
    if antes is None:
        fixados = list(publicados.filter(fixado_em__isnull=False).order_by("-fixado_em", "-id"))
    pagina, tem_mais = _pagina(publicados.filter(fixado_em__isnull=True), antes, limite)
    itens = _itens(fixados + pagina, ator)
    return {"fixados": itens[: len(fixados)], "itens": itens[len(fixados) :], "tem_mais": tem_mais}


def despublicados(
    ator_id: uuid.UUID, *, antes: uuid.UUID | None = None, limite: int | None = None
) -> dict[str, Any]:
    """Quem gerencia vê todos; o autor, os seus; os demais, nenhum (regra 5 da funcional)."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    qs = Comunicado.objects.filter(situacao=SituacaoDoComunicado.DESPUBLICADO.value)
    if not ator.pode_gerenciar:
        qs = qs.filter(autor_id=ator_id)
    pagina, tem_mais = _pagina(qs, antes, limite)
    return {"itens": _itens(pagina, ator), "tem_mais": tem_mais}


def detalhe(ator_id: uuid.UUID, comunicado_id: uuid.UUID) -> dict[str, Any]:
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = Comunicado.objects.filter(pk=comunicado_id).first()
    if comunicado is None or not pode_ver_comunicado(
        SituacaoDoComunicado(comunicado.situacao), ator.fatos(comunicado=comunicado)
    ):
        raise erro("NOT_FOUND")
    lote = _ler_lote([comunicado], ator_id)
    return _item(comunicado, ator, lote, _Nomes(), com_quem_reagiu=True)


def _comunicado_visivel(ator: Quem, comunicado_id: uuid.UUID) -> Comunicado:
    comunicado = Comunicado.objects.filter(pk=comunicado_id).first()
    if comunicado is None or not pode_ver_comunicado(
        SituacaoDoComunicado(comunicado.situacao), ator.fatos(comunicado=comunicado)
    ):
        raise erro("NOT_FOUND")
    return comunicado


def reacoes_do_comunicado(ator_id: uuid.UUID, comunicado_id: uuid.UUID) -> dict[str, Any]:
    """A contagem por tipo, quem reagiu e a reação de quem pergunta."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = _comunicado_visivel(ator, comunicado_id)
    lote = _ler_lote([comunicado], ator_id)
    nomes = _Nomes()
    return {
        "contagem": lote.contagem[comunicado.id],
        "minha": lote.minhas.get(comunicado.id),
        "quem": {
            tipo: [nomes.pessoa(i) for i in ids] for tipo, ids in lote.quem_reagiu[comunicado.id].items()
        },
    }


def _comentario(comentario: Comentario, comunicado: Comunicado, ator: Quem, nomes: _Nomes) -> dict[str, Any]:
    fatos = ator.fatos(comunicado=comunicado, comentario=comentario)
    oculto = None
    if comentario.situacao == SituacaoDoComentario.OCULTO:
        por = comentario.oculto_por_id
        oculto = {
            "em": comentario.oculto_em,
            "por": nomes.pessoa(por) if por else None,
            "pela_gerencia": comentario.oculto_pela_gerencia,
            "motivo": comentario.motivo_da_ocultacao,
        }
    return {
        "id": comentario.id,
        "autor": nomes.pessoa(comentario.autor_id),
        "texto": comentario.texto,
        "situacao": comentario.situacao,
        "criado_em": comentario.criado_em,
        "editado": comentario.editado_em is not None,
        "editado_em": comentario.editado_em,
        "oculto": oculto,
        "acoes": [comando.value for comando in acoes_do_comentario(fatos)],
    }


def comentarios(
    ator_id: uuid.UUID,
    comunicado_id: uuid.UUID,
    *,
    depois: uuid.UUID | None = None,
    limite: int | None = None,
) -> dict[str, Any]:
    """Do mais antigo ao mais novo. O oculto só aparece ao autor dele e a quem gerencia (regra 20)."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    comunicado = _comunicado_visivel(ator, comunicado_id)
    qs = Comentario.objects.filter(comunicado=comunicado)
    if not ator.pode_gerenciar:
        qs = qs.filter(Q(situacao=SituacaoDoComentario.VISIVEL.value) | Q(autor_id=ator_id))
    if depois is not None:
        if not Comentario.objects.filter(pk=depois, comunicado=comunicado).exists():
            raise erro("NOT_FOUND")
        qs = qs.filter(id__gt=depois)
    tamanho = limite_valido(limite)
    achados = list(qs.order_by("id")[: tamanho + 1])
    nomes = _Nomes()
    itens = [_comentario(c, comunicado, ator, nomes) for c in achados[:tamanho]]
    return {"itens": itens, "tem_mais": len(achados) > tamanho}
