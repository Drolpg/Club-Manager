"""Aprovar, contestar e recusar (RF-036 a RF-038; RN-010 a RN-012).

Ordem: entrada (textos, teto e motivo) → leitura de gestão → existência, com a linha bloqueada → quem pode e
situação (`avaliar`) → regras da versão (teto só com valor) → decisão → auditoria → aviso ao módulo dono.
O bloqueio da linha faz a segunda de duas decisões simultâneas esperar e encontrar a solicitação fora de
análise (CA-06); o índice único da decisão por versão é a segunda barreira.
"""

import uuid
from decimal import Decimal

from django.db import transaction

from aprovacoes import tipos
from aprovacoes.domain.decisores import avaliar
from aprovacoes.domain.transicoes import Comando
from aprovacoes.models import Solicitacao
from aprovacoes.services import avisos
from aprovacoes.services.autorizacao import exigir, fatos_de
from aprovacoes.services.motivos import motivo_aplicado
from aprovacoes.services.solicitacoes import (
    ITEM_DA_AUDITORIA,
    avisar_o_dono,
    bloquear,
    texto_obrigatorio,
    texto_opcional,
)
from aprovacoes.tipos import Acontecimento
from auditoria import public as auditoria
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError

_TIPO_DE_DECISAO = {
    Comando.APROVAR: tipos.APROVAR,
    Comando.CONTESTAR: tipos.CONTESTAR,
    Comando.RECUSAR: tipos.RECUSAR,
}
_ACONTECIMENTO = {
    Comando.APROVAR: Acontecimento.APROVADA,
    Comando.CONTESTAR: Acontecimento.CONTESTADA,
    Comando.RECUSAR: Acontecimento.RECUSADA,
}


def _teto(teto_sugerido: Decimal | str | None) -> Dinheiro | None:
    if teto_sugerido is None:
        return None
    try:
        teto = Dinheiro(teto_sugerido)
    except TypeError, ValueError:
        teto = None
    if teto is None or teto.quantia <= 0:
        raise BusinessError(
            "VALIDATION_ERROR",
            "Os dados enviados são inválidos.",
            status=400,
            details={"teto_sugerido": ["Informe um valor maior que zero, com até duas casas."]},
        )
    return teto


def _decidir(
    comando: Comando,
    *,
    ator_id: uuid.UUID,
    solicitacao_id: uuid.UUID,
    motivo_id: uuid.UUID,
    texto: str | None,
    mensagem: str = "",
    teto_sugerido: Dinheiro | None = None,
) -> Solicitacao:
    texto = texto_opcional("texto", texto)
    motivo_texto = motivo_aplicado(motivo_id, _TIPO_DE_DECISAO[comando])
    solicitacao = bloquear(ator_id, solicitacao_id)
    avaliacao = avaliar(comando, fatos_de(solicitacao, ator_id))
    exigir(avaliacao)
    propria = avaliacao.aprovacao_propria
    if comando is Comando.CONTESTAR:
        decisao = solicitacao.contestar(
            aprovador_id=ator_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            texto=texto,
            mensagem=mensagem,
            teto_sugerido=teto_sugerido,
            aprovacao_propria=propria,
        )
    else:
        decidir = solicitacao.aprovar if comando is Comando.APROVAR else solicitacao.recusar
        decisao = decidir(
            aprovador_id=ator_id,
            motivo_id=motivo_id,
            motivo_texto=motivo_texto,
            texto=texto,
            aprovacao_propria=propria,
        )
    auditoria.registrar(
        ator_id=ator_id,
        acao=f"SOLICITACAO_{_ACONTECIMENTO[comando].value}",
        item_tipo=ITEM_DA_AUDITORIA,
        item_id=solicitacao.id,
        justificativa=motivo_texto,
        dados={
            "versao": solicitacao.numero_da_versao_atual,
            "decisao_id": str(decisao.id),
            "motivo_id": str(motivo_id),
            "aprovacao_propria": avaliacao.aprovacao_propria,
        },
    )
    avisar_o_dono(solicitacao, _ACONTECIMENTO[comando], ator_id, teto_sugerido)
    avisos.decidida(solicitacao, decisao)
    if propria:
        avisos.aprovacao_propria(solicitacao, decisao)
    return solicitacao


@transaction.atomic
def aprovar(
    *, ator_id: uuid.UUID, solicitacao_id: uuid.UUID, motivo_id: uuid.UUID, texto: str | None = None
) -> Solicitacao:
    return _decidir(
        Comando.APROVAR, ator_id=ator_id, solicitacao_id=solicitacao_id, motivo_id=motivo_id, texto=texto
    )


@transaction.atomic
def contestar(
    *,
    ator_id: uuid.UUID,
    solicitacao_id: uuid.UUID,
    motivo_id: uuid.UUID,
    mensagem: str,
    texto: str | None = None,
    teto_sugerido: Decimal | str | None = None,
) -> Solicitacao:
    """Devolve ao solicitante para ajustes: motivo, mensagem e, se a versão tem valor, um teto sugerido."""
    return _decidir(
        Comando.CONTESTAR,
        ator_id=ator_id,
        solicitacao_id=solicitacao_id,
        motivo_id=motivo_id,
        texto=texto,
        mensagem=texto_obrigatorio("mensagem", mensagem),
        teto_sugerido=_teto(teto_sugerido),
    )


@transaction.atomic
def recusar(
    *, ator_id: uuid.UUID, solicitacao_id: uuid.UUID, motivo_id: uuid.UUID, texto: str | None = None
) -> Solicitacao:
    return _decidir(
        Comando.RECUSAR, ator_id=ator_id, solicitacao_id=solicitacao_id, motivo_id=motivo_id, texto=texto
    )
