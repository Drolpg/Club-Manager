"""A rotina diária de `relatorios` (CA-08, CA-13, CA-14; ADR-020): expira os arquivos e dá como falha o
pedido que parou de gerar.

Idempotente: cada pedido é tratado na própria transação, travado e com a situação conferida de novo, e a
segunda execução no mesmo dia não muda nada. Só apaga do armazenamento a chave de um relatório, nunca outra.
O erro de um pedido vai para o log e não impede os outros.
"""

import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime

from django.core.files.storage import default_storage
from django.db import transaction

from auditoria import public as auditoria
from relatorios.domain.pedido import LIMITE_GERANDO, SituacaoDoPedido
from relatorios.models import PedidoDeRelatorio
from relatorios.services import avisos, pedidos

logger = logging.getLogger(__name__)

# Só o que a geração grava. Defesa em profundidade: uma chave de outro contexto nunca é apagada.
_CHAVE_DE_RELATORIO = re.compile(r"relatorios/[0-9a-f-]{36}\.(pdf|csv|zip)")


def _apagar_arquivo(chave: str) -> None:
    if _CHAVE_DE_RELATORIO.fullmatch(chave) and default_storage.exists(chave):
        default_storage.delete(chave)


def _expirar(pedido_id: uuid.UUID) -> int:
    with transaction.atomic():
        pedido = pedidos.expirar(pedido_id)
        if pedido is None:
            return 0
        _apagar_arquivo(pedido.arquivo_chave)
        auditoria.registrar(
            ator_id=None,
            acao="RELATORIO_EXPIRADO",
            item_tipo=pedidos.ITEM_TIPO,
            item_id=pedido.id,
            dados={"tipo": pedido.tipo},
        )
        return 1


def _falhar_parado(pedido_id: uuid.UUID) -> int:
    with transaction.atomic():
        pedido = pedidos.falhar(pedido_id, "PARADO")
        if pedido is None:
            return 0
        avisos.falhou(pedido)
        return 1


def _tratar(
    contagem: dict[str, int], etapa: str, ids: list[uuid.UUID], acao: Callable[[uuid.UUID], int]
) -> None:
    for pedido_id in ids:
        try:
            contagem[etapa] += acao(pedido_id)
        except Exception:
            logger.exception(
                "relatorios.rotina_diaria.falhou", extra={"etapa": etapa, "pedido_id": str(pedido_id)}
            )
            contagem["erros"] += 1


def executar(agora: datetime) -> dict[str, int]:
    contagem = {"expirados": 0, "parados": 0, "erros": 0}
    vencidos = PedidoDeRelatorio.objects.filter(situacao=SituacaoDoPedido.PRONTO, expira_em__lte=agora)
    _tratar(contagem, "expirados", list(vencidos.values_list("id", flat=True)), _expirar)
    parados = PedidoDeRelatorio.objects.filter(
        situacao=SituacaoDoPedido.GERANDO, iniciado_em__lt=agora - LIMITE_GERANDO
    )
    _tratar(contagem, "parados", list(parados.values_list("id", flat=True)), _falhar_parado)
    return contagem
