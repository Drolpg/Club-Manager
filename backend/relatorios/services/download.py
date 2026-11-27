"""Baixar o arquivo de um pedido (spec técnica, "Baixar"; CA-09 a CA-11).

Ordem: sessão, dono, permissão do tipo de novo, situação. O pedido de outro ou inexistente dá 403 nos dois
casos, nem o admin baixa o de outro (D4). O download não é auditado (P20).
"""

import uuid

from relatorios import tipos
from relatorios.domain.pedido import SituacaoDoPedido
from relatorios.erros import erro, relatorio_nao_disponivel
from relatorios.services import pedidos


def baixar(ator_id: uuid.UUID, pedido_id: uuid.UUID) -> pedidos.Arquivo:
    pedido = pedidos.obter(ator_id, pedido_id)
    tipo = tipos.obter(pedido.tipo)
    if tipo is None or not tipo.pode_gerar(ator_id):
        raise erro("PERMISSION_DENIED")
    if pedido.situacao != SituacaoDoPedido.PRONTO or not pedidos.disponivel(pedido):
        raise relatorio_nao_disponivel(pedido.situacao)
    return pedidos.Arquivo(
        chave=pedido.arquivo_chave,
        nome=pedido.arquivo_nome,
        mime=pedido.arquivo_mime,
        tamanho=pedido.arquivo_tamanho or 0,
    )
