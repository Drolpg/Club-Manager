"""API pública do módulo `financeiro`.

É o único arquivo deste módulo que outros módulos podem importar (docs/sdd/02-plan.md):
- `obter_categoria_ativa` / `listar_categorias_ativas`: consulta de categorias sem expor ORM.
- `registrar_devolucao_de_saida`: registra devolução de saída de eventos (`TipoEntrada.DEVOLUCAO`).
- `resumo_entradas_validadas`: soma consolidada apenas das entradas com situação `VALIDADA`.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db import transaction

from auditoria import public as auditoria
from financeiro.erros import erro
from financeiro.models import CategoriaFinanceira, Entrada, Saida, TipoEntrada
from financeiro.services import avisos, gastos
from financeiro.services.consulta import (
    ResumoEntradasValidadas,
    VisaoDoCaixa,
    resumo_entradas_validadas,
    visao_do_caixa,
)
from financeiro.tipos import OrcamentoDeEventoMudou
from kernel.dinheiro import Dinheiro


@dataclass(frozen=True)
class CategoriaFinanceiraInfo:
    id: uuid.UUID
    nome: str
    natureza: str
    ativa: bool


def _para_info(categoria: CategoriaFinanceira) -> CategoriaFinanceiraInfo:
    return CategoriaFinanceiraInfo(
        id=categoria.id,
        nome=categoria.nome,
        natureza=categoria.natureza,
        ativa=categoria.ativa,
    )


def obter_categoria_ativa(
    categoria_id: uuid.UUID,
    *,
    natureza: str | None = None,
) -> CategoriaFinanceiraInfo:
    """Obtém uma categoria ativa; opcionalmente exige uma natureza (`ENTRADA` ou `SAIDA`)."""
    categoria = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND")
    if not categoria.ativa or (natureza is not None and categoria.natureza != natureza):
        raise erro("CATEGORIA_INATIVA")
    return _para_info(categoria)


def listar_categorias_ativas(*, natureza: str | None = None) -> list[CategoriaFinanceiraInfo]:
    """Lista categorias financeiras ativas, podendo filtrar por natureza."""
    qs = CategoriaFinanceira.objects.filter(ativa=True)
    if natureza is not None:
        qs = qs.filter(natureza=natureza)
    return [_para_info(c) for c in qs]


@transaction.atomic
def registrar_devolucao_de_saida(
    *,
    categoria_id: uuid.UUID,
    valor: Dinheiro,
    data: date,
    origem: str,
    referencia: str,
    registrada_por_id: uuid.UUID,
    saida_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Registra uma devolução financeira vinda de saída aguardando validação."""
    categoria = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND")
    saida: Saida | None = None
    if saida_id is not None:
        saida = Saida.objects.select_for_update().filter(pk=saida_id).first()
        if saida is None:
            raise erro("NOT_FOUND")
    entrada = Entrada.registrar(
        categoria=categoria,
        valor=valor,
        data=data,
        origem=origem,
        evidencia_texto=referencia,
        anexo=None,
        registrada_por_id=registrada_por_id,
        tipo=TipoEntrada.DEVOLUCAO,
        saida=saida,
    )
    dados_auditoria: dict[str, Any] = {
        "categoria_id": str(categoria.id),
        "valor": str(entrada.valor),
        "data": entrada.data.isoformat(),
        "origem": entrada.origem,
        "tipo": entrada.tipo,
    }
    if saida is not None:
        dados_auditoria["saida_id"] = str(saida.id)
    auditoria.registrar(
        ator_id=registrada_por_id,
        acao="ENTRADA_REGISTRADA",
        item_tipo="entrada",
        item_id=entrada.id,
        dados=dados_auditoria,
    )
    avisos.entrada_registrada(entrada)
    return entrada.id


def abrir_solicitacao_orcamentaria(
    *,
    solicitante_id: uuid.UUID,
    descricao: str,
    categoria_id: uuid.UUID,
    setor_id: uuid.UUID,
    itens: list[dict[str, Any]],
    evento_id: uuid.UUID,
    aprovador_indicado_id: uuid.UUID | None = None,
    cotacao_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Abre solicitação de gasto vinculada a um evento e devolve o ID da solicitação."""
    info = gastos.abrir_solicitacao(
        solicitante_id,
        descricao=descricao,
        categoria_id=categoria_id,
        setor_id=setor_id,
        itens=itens,
        cotacao_id=cotacao_id,
        aprovador_indicado_id=aprovador_indicado_id,
        evento_id=evento_id,
    )
    return info.id


__all__ = (
    "CategoriaFinanceiraInfo",
    "OrcamentoDeEventoMudou",
    "ResumoEntradasValidadas",
    "VisaoDoCaixa",
    "abrir_solicitacao_orcamentaria",
    "listar_categorias_ativas",
    "obter_categoria_ativa",
    "registrar_devolucao_de_saida",
    "resumo_entradas_validadas",
    "visao_do_caixa",
)
