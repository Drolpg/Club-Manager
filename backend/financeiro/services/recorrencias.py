"""Casos de uso de cobranças recorrentes."""

import uuid
from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from acesso import public as acesso
from auditoria import public as auditoria
from financeiro.domain.autorizacao import PERM_COBRANCAS_CRIAR
from financeiro.domain.competencia import Periodicidade
from financeiro.erros import erro, erro_validacao
from financeiro.models import CategoriaFinanceira, ChavePix, NaturezaCategoria, Recorrencia
from financeiro.services import autorizacao
from kernel.dinheiro import Dinheiro


def _validar_agenda(periodicidade: Periodicidade, dia: int, mes: int | None) -> None:
    if periodicidade == Periodicidade.SEMANAL:
        if not 1 <= dia <= 7:
            raise erro_validacao("dia_vencimento", "Na recorrência semanal, informe um dia de 1 a 7.")
        if mes is not None:
            raise erro_validacao("mes_vencimento", "Mês de vencimento só se aplica à recorrência anual.")
        return
    if not 1 <= dia <= 31:
        raise erro_validacao("dia_vencimento", "Informe um dia de vencimento entre 1 e 31.")
    if periodicidade == Periodicidade.MENSAL:
        if mes is not None:
            raise erro_validacao("mes_vencimento", "Mês de vencimento só se aplica à recorrência anual.")
    elif mes is None or not 1 <= mes <= 12:
        raise erro_validacao("mes_vencimento", "Na recorrência anual, informe o mês entre 1 e 12.")


def _categoria_entrada_ativa(categoria_id: uuid.UUID) -> CategoriaFinanceira:
    categoria = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND")
    if not categoria.ativa or categoria.natureza != NaturezaCategoria.ENTRADA:
        raise erro("CATEGORIA_INATIVA")
    return categoria


def _chave_pix_ativa(chave_pix_id: uuid.UUID | None) -> ChavePix:
    if chave_pix_id is None:
        padrao = ChavePix.objects.filter(ativa=True, padrao=True).first()
        if padrao is None:
            raise erro("CHAVE_PIX_PADRAO_NAO_CONFIGURADA")
        return padrao
    chave = ChavePix.objects.filter(pk=chave_pix_id).first()
    if chave is None:
        raise erro("NOT_FOUND")
    if not chave.ativa:
        raise erro("CHAVE_PIX_INATIVA")
    return chave


def serializar_recorrencia(
    rec: Recorrencia,
    nomes: dict[uuid.UUID, str] | None = None,
) -> dict[str, Any]:
    """Serializa uma recorrência para resposta HTTP sem expor o ORM."""
    if nomes is not None and rec.devedor_id in nomes:
        devedor_nome = nomes[rec.devedor_id]
    else:
        usuario = acesso.usuario_por_id(rec.devedor_id)
        devedor_nome = usuario.nome if usuario else "Diretor"
        if nomes is not None:
            nomes[rec.devedor_id] = devedor_nome
    return {
        "id": rec.id,
        "devedor": {"id": rec.devedor_id, "nome": devedor_nome},
        "categoria_id": rec.categoria_id,
        "categoria_nome": rec.categoria.nome,
        "descricao": rec.descricao,
        "valor": rec.valor,
        "periodicidade": rec.periodicidade,
        "dia_vencimento": rec.dia_vencimento,
        "mes_vencimento": rec.mes_vencimento,
        "antecedencia_dias": rec.antecedencia_dias,
        "limite_de_inadimplencia": rec.limite_de_inadimplencia,
        "chave_pix_id": rec.chave_pix_id,
        "ativa": rec.ativa,
        "a_partir_de": rec.a_partir_de,
        "criada_em": rec.criada_em,
    }


def listar(
    ator_id: uuid.UUID,
    *,
    devedor_id: uuid.UUID | None = None,
    incluir_inativas: bool = False,
) -> list[dict[str, Any]]:
    """Lista recorrências para leitura da gestão."""
    autorizacao.exigir_leitura_gestao(ator_id)
    qs = Recorrencia.objects.select_related("categoria", "chave_pix").all()
    if not incluir_inativas:
        qs = qs.filter(ativa=True)
    if devedor_id is not None:
        qs = qs.filter(devedor_id=devedor_id)
    cache: dict[uuid.UUID, str] = {}
    return [serializar_recorrencia(rec, cache) for rec in qs]


@transaction.atomic
def criar(
    ator_id: uuid.UUID,
    *,
    devedor_id: uuid.UUID,
    categoria_id: uuid.UUID,
    descricao: str,
    valor: Dinheiro,
    periodicidade: str,
    dia_vencimento: int,
    mes_vencimento: int | None,
    antecedencia_dias: int,
    limite_de_inadimplencia: int,
    chave_pix_id: uuid.UUID | None,
    a_partir_de: date | None,
) -> dict[str, Any]:
    """Cria uma recorrência ativa para um diretor ativo."""
    autorizacao.exigir_permissao(ator_id, PERM_COBRANCAS_CRIAR)
    devedor = acesso.usuario_por_id(devedor_id)
    if devedor is None or not devedor.ativo:
        raise erro("DEVEDOR_INATIVO")
    periodo = Periodicidade(periodicidade)
    _validar_agenda(periodo, dia_vencimento, mes_vencimento)
    categoria = _categoria_entrada_ativa(categoria_id)
    chave_pix = _chave_pix_ativa(chave_pix_id)
    rec = Recorrencia.criar(
        devedor_id=devedor_id,
        categoria=categoria,
        descricao=descricao,
        valor=valor,
        periodicidade=periodo,
        dia_vencimento=dia_vencimento,
        mes_vencimento=mes_vencimento,
        antecedencia_dias=antecedencia_dias,
        limite_de_inadimplencia=limite_de_inadimplencia,
        chave_pix=chave_pix,
        a_partir_de=a_partir_de or timezone.localdate(),
    )
    auditoria.registrar(
        acao="RECORRENCIA_CRIADA",
        ator_id=ator_id,
        item_tipo="recorrencia",
        item_id=rec.id,
        dados={
            "devedor_id": str(devedor_id),
            "periodicidade": rec.periodicidade,
            "valor": str(rec.valor),
        },
    )
    return serializar_recorrencia(rec)


@transaction.atomic
def editar(
    ator_id: uuid.UUID,
    recorrencia_id: uuid.UUID,
    *,
    categoria_id: uuid.UUID,
    descricao: str,
    valor: Dinheiro,
    dia_vencimento: int,
    mes_vencimento: int | None,
    antecedencia_dias: int,
    limite_de_inadimplencia: int,
    chave_pix_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Altera parâmetros futuros da recorrência sem tocar em cobranças já emitidas (CA-24)."""
    autorizacao.exigir_permissao(ator_id, PERM_COBRANCAS_CRIAR)
    rec = (
        Recorrencia.objects.select_for_update().select_related("categoria").filter(pk=recorrencia_id).first()
    )
    if rec is None:
        raise erro("NOT_FOUND")
    _validar_agenda(Periodicidade(rec.periodicidade), dia_vencimento, mes_vencimento)
    categoria = _categoria_entrada_ativa(categoria_id)
    chave_pix = _chave_pix_ativa(chave_pix_id)
    rec.alterar(
        categoria=categoria,
        descricao=descricao,
        valor=valor,
        dia_vencimento=dia_vencimento,
        mes_vencimento=mes_vencimento,
        antecedencia_dias=antecedencia_dias,
        limite_de_inadimplencia=limite_de_inadimplencia,
        chave_pix=chave_pix,
    )
    auditoria.registrar(
        acao="RECORRENCIA_ALTERADA",
        ator_id=ator_id,
        item_tipo="recorrencia",
        item_id=rec.id,
        dados={"valor": str(rec.valor), "dia_vencimento": rec.dia_vencimento},
    )
    return serializar_recorrencia(rec)


@transaction.atomic
def desativar(ator_id: uuid.UUID, recorrencia_id: uuid.UUID) -> dict[str, Any]:
    """Desativa a recorrência mantendo histórico e cobranças existentes (CA-25)."""
    autorizacao.exigir_permissao(ator_id, PERM_COBRANCAS_CRIAR)
    rec = (
        Recorrencia.objects.select_for_update().select_related("categoria").filter(pk=recorrencia_id).first()
    )
    if rec is None:
        raise erro("NOT_FOUND")
    rec.desativar()
    auditoria.registrar(
        acao="RECORRENCIA_DESATIVADA",
        ator_id=ator_id,
        item_tipo="recorrencia",
        item_id=rec.id,
    )
    return serializar_recorrencia(rec)


def historico(ator_id: uuid.UUID, recorrencia_id: uuid.UUID) -> list[auditoria.Registro]:
    """Retorna histórico auditado da recorrência para usuários da gestão."""
    autorizacao.exigir_leitura_gestao(ator_id)
    if not Recorrencia.objects.filter(pk=recorrencia_id).exists():
        raise erro("NOT_FOUND")
    return auditoria.historico_do_item("recorrencia", recorrencia_id)
