"""API pública do módulo `financeiro`.

É o único arquivo deste módulo que outros módulos podem importar (docs/sdd/02-plan.md):
- `obter_categoria_ativa` / `listar_categorias_ativas`: consulta de categorias sem expor ORM.
- `registrar_devolucao_de_saida`: registra devolução de saída de eventos (`TipoEntrada.DEVOLUCAO`).
- `resumo_entradas_validadas`: soma consolidada apenas das entradas com situação `VALIDADA`.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from django.db import transaction

from auditoria import public as auditoria
from financeiro.erros import erro
from financeiro.models import CategoriaFinanceira, Entrada, TipoEntrada
from financeiro.services import avisos
from financeiro.services.consulta import ResumoEntradasValidadas, resumo_entradas_validadas
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
) -> uuid.UUID:
    """Registra uma devolução financeira vinda de saída de evento aguardando validação."""
    categoria = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
    if categoria is None:
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
    )
    auditoria.registrar(
        ator_id=registrada_por_id,
        acao="ENTRADA_REGISTRADA",
        item_tipo="entrada",
        item_id=entrada.id,
        dados={
            "categoria_id": str(categoria.id),
            "valor": str(entrada.valor),
            "data": entrada.data.isoformat(),
            "origem": entrada.origem,
            "tipo": entrada.tipo,
        },
    )
    avisos.entrada_registrada(entrada)
    return entrada.id


__all__ = (
    "CategoriaFinanceiraInfo",
    "ResumoEntradasValidadas",
    "listar_categorias_ativas",
    "obter_categoria_ativa",
    "registrar_devolucao_de_saida",
    "resumo_entradas_validadas",
)
