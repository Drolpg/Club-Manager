"""Casos de uso de inadimplência: justificativa, perdão, renegociação e manutenção de dívida."""

import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro import tipos
from financeiro.domain.autorizacao import PERM_DIVIDAS_DECIDIR
from financeiro.domain.transicoes import ComandoCobranca
from financeiro.erros import erro
from financeiro.models import Cobranca
from financeiro.services import autorizacao, avisos
from financeiro.services.cobrancas import resolver_chave_pix
from kernel.dinheiro import Dinheiro
from permissoes import public as permissoes


def _trancar_para_decisao(ator_id: uuid.UUID, cobranca_id: uuid.UUID) -> Cobranca:
    cobranca = (
        Cobranca.objects.select_for_update()
        .select_related("categoria", "chave_pix")
        .filter(pk=cobranca_id)
        .first()
    )
    if cobranca is None:
        autorizacao.exigir_permissao(ator_id, PERM_DIVIDAS_DECIDIR)
        raise erro("NOT_FOUND")
    return cobranca


@transaction.atomic
def justificar_divida(*, ator_id: uuid.UUID, cobranca_id: uuid.UUID, texto: str) -> Cobranca:
    """Registra a justificativa do devedor após convocação automática por atraso (CA-36)."""
    usuario = autorizacao.exigir_diretor_ativo(ator_id)
    cobranca = Cobranca.objects.select_for_update().filter(pk=cobranca_id).first()
    if cobranca is None:
        if not (usuario.admin or permissoes.le_gestao(ator_id)):
            raise erro("PERMISSION_DENIED")
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.JUSTIFICAR_DIVIDA)
    cobranca.justificar_divida(texto=texto, agora=timezone.now())
    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_DIVIDA_JUSTIFICADA",
        item_tipo="cobranca",
        item_id=cobranca.id,
        justificativa=texto.strip(),
    )
    avisos.divida_justificada(cobranca)
    return cobranca


@transaction.atomic
def perdoar(
    *,
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    motivo_id: uuid.UUID,
    texto: str = "",
) -> Cobranca:
    """Perdoa cobrança atrasada e encerra eventual convocação em aberto (CA-37)."""
    cobranca = _trancar_para_decisao(ator_id, cobranca_id)
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.PERDOAR)
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_DIVIDA_DECIDIR)
    cobranca.perdoar(
        por_id=ator_id,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        texto=texto,
        agora=timezone.now(),
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_PERDOADA",
        item_tipo="cobranca",
        item_id=cobranca.id,
        justificativa=texto.strip() or motivo_texto,
        dados={"motivo_id": str(motivo_id), "motivo_texto": motivo_texto},
    )
    avisos.divida_decidida(cobranca, decisao="PERDOAR", motivo_texto=motivo_texto)
    return cobranca


@transaction.atomic
def renegociar(
    *,
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    motivo_id: uuid.UUID,
    texto: str = "",
    parcelas: list[dict[str, Any]],
) -> Cobranca:
    """Encerra dívida atrasada como RENEGOCIADA e gera parcelas atomicamente (CA-38, INV-REN)."""
    cobranca = _trancar_para_decisao(ator_id, cobranca_id)
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.RENEGOCIAR)
    if not parcelas:
        raise erro("PARCELAS_INVALIDAS")
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_DIVIDA_DECIDIR)
    chave_pix = cobranca.chave_pix if cobranca.chave_pix.ativa else resolver_chave_pix(None)

    try:
        valores = [Dinheiro(item["valor"]) for item in parcelas]
    except ValueError:
        raise erro("VALOR_INVALIDO") from None
    valor_acordado = sum((v.quantia for v in valores), start=Decimal("0.00"))
    agora = timezone.now()
    hoje = timezone.localdate()

    reneg = cobranca.marcar_renegociada(
        por_id=ator_id,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        texto=texto,
        valor_acordado=valor_acordado,
        quantidade_parcelas=len(parcelas),
        agora=agora,
    )

    novas_parcelas: list[Cobranca] = []
    total_parcelas = len(parcelas)
    for idx, (item, valor_item) in enumerate(zip(parcelas, valores, strict=True), start=1):
        descricao = f"{cobranca.descricao} (parcela {idx}/{total_parcelas})"[:200]
        parcela = Cobranca.criar(
            devedor_id=cobranca.devedor_id,
            categoria=cobranca.categoria,
            descricao=descricao,
            valor=valor_item,
            vencimento=item["vencimento"],
            limite_de_inadimplencia=cobranca.limite_de_inadimplencia,
            chave_pix=chave_pix,
            hoje=hoje,
            cobranca_origem=cobranca,
        )
        auditoria.registrar(
            ator_id=ator_id,
            acao="COBRANCA_CRIADA",
            item_tipo="cobranca",
            item_id=parcela.id,
            dados={
                "cobranca_origem_id": str(cobranca.id),
                "renegociacao_id": str(reneg.id),
                "parcela": idx,
                "total_parcelas": total_parcelas,
                "valor": str(parcela.valor),
                "vencimento": parcela.vencimento.isoformat(),
            },
        )
        novas_parcelas.append(parcela)

    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_RENEGOCIADA",
        item_tipo="cobranca",
        item_id=cobranca.id,
        justificativa=texto.strip() or motivo_texto,
        dados={
            "renegociacao_id": str(reneg.id),
            "motivo_id": str(motivo_id),
            "motivo_texto": motivo_texto,
            "valor_acordado": str(reneg.valor_acordado),
            "quantidade_parcelas": reneg.quantidade_parcelas,
            "parcela_ids": [str(p.id) for p in novas_parcelas],
        },
    )
    avisos.divida_decidida(cobranca, decisao="RENEGOCIAR", motivo_texto=motivo_texto)
    for parcela in novas_parcelas:
        avisos.cobranca_criada(parcela)
    return cobranca


@transaction.atomic
def manter_divida(
    *,
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    motivo_id: uuid.UUID,
    texto: str = "",
) -> Cobranca:
    """Fecha convocação aberta mantendo a cobrança como ATRASADA (CA-40)."""
    cobranca = _trancar_para_decisao(ator_id, cobranca_id)
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.MANTER_DIVIDA)
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_DIVIDA_DECIDIR)
    cobranca.manter_divida(
        por_id=ator_id,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        texto=texto,
        agora=timezone.now(),
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_DIVIDA_MANTIDA",
        item_tipo="cobranca",
        item_id=cobranca.id,
        justificativa=texto.strip() or motivo_texto,
        dados={"motivo_id": str(motivo_id), "motivo_texto": motivo_texto},
    )
    avisos.divida_decidida(cobranca, decisao="MANTER", motivo_texto=motivo_texto)
    return cobranca
