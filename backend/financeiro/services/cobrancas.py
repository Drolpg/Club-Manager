"""Criação de cobranças (avulsa e em lote) e cancelamento (Parte 1)."""

import uuid
from collections.abc import Iterable
from datetime import date

from django.db import transaction
from django.utils import timezone

from acesso import public as acesso
from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro import tipos
from financeiro.domain.autorizacao import PERM_COBRANCAS_CRIAR, PERM_COBRANCAS_ISENTAR
from financeiro.domain.transicoes import ComandoCobranca
from financeiro.erros import erro, erro_validacao
from financeiro.models import CategoriaFinanceira, ChavePix, Cobranca, NaturezaCategoria
from financeiro.services import avisos
from financeiro.services.autorizacao import exigir_comando_cobranca, exigir_permissao
from kernel.dinheiro import Dinheiro
from permissoes import public as permissoes

ITEM_AUDITORIA = "cobranca"


def resolver_categoria_entrada(categoria_id: uuid.UUID) -> CategoriaFinanceira:
    categoria = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
    if categoria is None:
        raise erro_validacao("categoria_id", "Categoria financeira não encontrada.")
    if not categoria.ativa:
        raise erro("CATEGORIA_INATIVA")
    if categoria.natureza != NaturezaCategoria.ENTRADA:
        raise erro_validacao("categoria_id", "Escolha uma categoria da natureza ENTRADA.")
    return categoria


def resolver_chave_pix(chave_pix_id: uuid.UUID | None) -> ChavePix:
    if chave_pix_id is None:
        padrao = ChavePix.objects.filter(padrao=True, ativa=True).first()
        if padrao is None:
            raise erro("CHAVE_PIX_PADRAO_NAO_CONFIGURADA")
        return padrao
    chave = ChavePix.objects.filter(pk=chave_pix_id).first()
    if chave is None:
        raise erro_validacao("chave_pix_id", "Chave Pix não encontrada.")
    if not chave.ativa:
        raise erro("CHAVE_PIX_INATIVA")
    return chave


def validar_devedores_ativos(devedor_ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
    unicos = list(dict.fromkeys(devedor_ids))
    if not unicos:
        raise erro_validacao("devedor_ids", "Selecione ao menos um diretor ativo.")
    ativos = acesso.ids_ativos(unicos)
    if len(ativos) != len(unicos):
        raise erro("DEVEDOR_INATIVO")
    return unicos


@transaction.atomic
def criar_avulsa(
    *,
    ator_id: uuid.UUID,
    devedor_id: uuid.UUID,
    categoria_id: uuid.UUID,
    descricao: str,
    valor: Dinheiro,
    vencimento: date,
    limite_de_inadimplencia: int = 30,
    chave_pix_id: uuid.UUID | None = None,
) -> Cobranca:
    exigir_permissao(ator_id, PERM_COBRANCAS_CRIAR)
    hoje = timezone.localdate()
    validar_devedores_ativos([devedor_id])
    categoria = resolver_categoria_entrada(categoria_id)
    chave_pix = resolver_chave_pix(chave_pix_id)
    cobranca = Cobranca.criar(
        devedor_id=devedor_id,
        categoria=categoria,
        descricao=descricao,
        valor=valor,
        vencimento=vencimento,
        limite_de_inadimplencia=limite_de_inadimplencia,
        chave_pix=chave_pix,
        hoje=hoje,
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_CRIADA",
        item_tipo=ITEM_AUDITORIA,
        item_id=cobranca.id,
        dados={"devedor_id": str(devedor_id), "valor": str(valor), "vencimento": vencimento.isoformat()},
    )
    avisos.cobranca_criada(cobranca)
    return cobranca


@transaction.atomic
def criar_lote(
    *,
    ator_id: uuid.UUID,
    devedor_ids: list[uuid.UUID] | None,
    todos_ativos_com_cargo: bool,
    categoria_id: uuid.UUID,
    descricao: str,
    valor: Dinheiro,
    vencimento: date,
    limite_de_inadimplencia: int = 30,
    chave_pix_id: uuid.UUID | None = None,
) -> list[Cobranca]:
    exigir_permissao(ator_id, PERM_COBRANCAS_CRIAR)
    hoje = timezone.localdate()
    alvos = permissoes.usuarios_ativos_com_cargo() if todos_ativos_com_cargo else (devedor_ids or [])
    destinos = validar_devedores_ativos(alvos)
    categoria = resolver_categoria_entrada(categoria_id)
    chave_pix = resolver_chave_pix(chave_pix_id)

    criadas: list[Cobranca] = []
    for devedor_id in destinos:
        cobranca = Cobranca.criar(
            devedor_id=devedor_id,
            categoria=categoria,
            descricao=descricao,
            valor=valor,
            vencimento=vencimento,
            limite_de_inadimplencia=limite_de_inadimplencia,
            chave_pix=chave_pix,
            hoje=hoje,
        )
        auditoria.registrar(
            ator_id=ator_id,
            acao="COBRANCA_CRIADA",
            item_tipo=ITEM_AUDITORIA,
            item_id=cobranca.id,
            dados={
                "devedor_id": str(devedor_id),
                "valor": str(valor),
                "vencimento": vencimento.isoformat(),
                "lote": True,
            },
        )
        avisos.cobranca_criada(cobranca)
        criadas.append(cobranca)
    return criadas


@transaction.atomic
def cancelar(
    *,
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    motivo_id: uuid.UUID,
    texto: str = "",
) -> Cobranca:
    cobranca = Cobranca.objects.select_for_update().filter(pk=cobranca_id).first()
    if cobranca is None:
        exigir_permissao(ator_id, "cobrancas.cancelar")
        raise erro("NOT_FOUND")
    exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.CANCELAR)
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_COBRANCA_CANCELAR)
    cobranca.cancelar(
        por_id=ator_id,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        texto=texto,
        agora=timezone.now(),
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_CANCELADA",
        item_tipo=ITEM_AUDITORIA,
        item_id=cobranca.id,
        justificativa=texto.strip() or motivo_texto,
        dados={"motivo_id": str(motivo_id), "motivo_texto": motivo_texto},
    )
    return cobranca


@transaction.atomic
def isentar(*, ator_id: uuid.UUID, cobranca_id: uuid.UUID, justificativa: str) -> Cobranca:
    """Isenta cobrança aberta ou atrasada com justificativa obrigatória (CA-34)."""
    cobranca = Cobranca.objects.select_for_update().filter(pk=cobranca_id).first()
    if cobranca is None:
        exigir_permissao(ator_id, PERM_COBRANCAS_ISENTAR)
        raise erro("NOT_FOUND")
    exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.ISENTAR)
    limpo = justificativa.strip()
    cobranca.isentar(por_id=ator_id, justificativa=limpo, agora=timezone.now())
    auditoria.registrar(
        ator_id=ator_id,
        acao="COBRANCA_ISENTA",
        item_tipo=ITEM_AUDITORIA,
        item_id=cobranca.id,
        justificativa=limpo,
    )
    return cobranca
