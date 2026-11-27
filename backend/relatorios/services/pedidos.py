"""Pedir um relatório e as transições do pedido (spec técnica `relatorios/relatorios-pdf-e-csv`, "Pedir").

Quem pode gerar cada tipo é do catálogo. O pedido inválido não entra na fila (CA-03); o válido entra em
`NA_FILA`, fica na auditoria sem conteúdo e agenda a geração só depois do commit (CA-28). As transições
conferem a situação de novo, com o pedido travado: aplicar fora de ordem não muda nada.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from acesso import public as acesso
from auditoria import public as auditoria
from relatorios import tasks, tipos
from relatorios.domain.parametros import ParametroInvalido
from relatorios.domain.pedido import (
    EM_ANDAMENTO,
    MAXIMO_EM_ANDAMENTO,
    ComandoDoPedido,
    Formato,
    SituacaoDoPedido,
    TransicaoInvalida,
    expira_em,
    pode_pedir_mais,
    proxima_situacao,
)
from relatorios.erros import campo_invalido, erro, pedidos_em_andamento
from relatorios.models import PedidoDeRelatorio

ITEM_TIPO = "pedido_de_relatorio"


@dataclass(frozen=True)
class Arquivo:
    chave: str
    nome: str
    mime: str
    tamanho: int


def _tipo_e_formato(tipo: str, formato: str) -> tuple[tipos.TipoDeRelatorio, Formato]:
    encontrado = tipos.obter(tipo)
    if encontrado is None:
        raise campo_invalido("tipo", "Tipo de relatório desconhecido.")
    if formato not in {f.value for f in encontrado.formatos}:
        raise campo_invalido("formato", "Este relatório não sai neste formato.")
    return encontrado, Formato(formato)


def pedir(ator_id: uuid.UUID, *, tipo: str, formato: str, parametros: Mapping[str, Any]) -> PedidoDeRelatorio:
    ator = acesso.usuario_por_id(ator_id)
    if ator is None or not ator.ativo:
        raise erro("PERMISSION_DENIED")
    tipo_de_relatorio, formato_valido = _tipo_e_formato(tipo, formato)
    if not tipo_de_relatorio.pode_gerar(ator_id):
        raise erro("PERMISSION_DENIED")
    try:
        normalizados = tipo_de_relatorio.validar_parametros(parametros, timezone.localdate())
    except ParametroInvalido as invalido:
        raise campo_invalido(invalido.campo, invalido.mensagem) from None

    with transaction.atomic():
        # Sem trava: dois pedidos simultâneos podem passar juntos do limite (D6, R12).
        andamento = PedidoDeRelatorio.objects.filter(pedido_por_id=ator_id, situacao__in=EM_ANDAMENTO).count()
        if not pode_pedir_mais(andamento):
            raise pedidos_em_andamento(MAXIMO_EM_ANDAMENTO)
        pedido = PedidoDeRelatorio.objects.create(
            tipo=tipo_de_relatorio.codigo,
            formato=formato_valido,
            parametros=normalizados,
            pedido_por_id=ator_id,
            pedido_em=timezone.now(),
            situacao=SituacaoDoPedido.NA_FILA,
        )
        auditoria.registrar(
            ator_id=ator_id,
            acao="RELATORIO_PEDIDO",
            item_tipo=ITEM_TIPO,
            item_id=pedido.id,
            dados={"tipo": pedido.tipo, "formato": pedido.formato, "parametros": normalizados},
        )
        pedido_id = str(pedido.id)
        transaction.on_commit(lambda: tasks.gerar_relatorio.delay(pedido_id))
    return pedido


def _transicionar(pedido_id: uuid.UUID, comando: ComandoDoPedido, **campos: Any) -> PedidoDeRelatorio | None:
    """Aplica o comando se a situação atual o aceita; senão, não muda nada e devolve `None`."""
    with transaction.atomic():
        pedido = PedidoDeRelatorio.objects.select_for_update().filter(id=pedido_id).first()
        if pedido is None:
            return None
        try:
            pedido.situacao = proxima_situacao(SituacaoDoPedido(pedido.situacao), comando)
        except TransicaoInvalida:
            return None
        for campo, valor in campos.items():
            setattr(pedido, campo, valor)
        pedido.save(update_fields=["situacao", *campos])
        return pedido


def iniciar_geracao(pedido_id: uuid.UUID) -> PedidoDeRelatorio | None:
    return _transicionar(pedido_id, ComandoDoPedido.INICIAR_GERACAO, iniciado_em=timezone.now())


def concluir(pedido_id: uuid.UUID, arquivo: Arquivo) -> PedidoDeRelatorio | None:
    agora = timezone.now()
    return _transicionar(
        pedido_id,
        ComandoDoPedido.CONCLUIR,
        concluido_em=agora,
        expira_em=expira_em(agora),
        arquivo_chave=arquivo.chave,
        arquivo_nome=arquivo.nome,
        arquivo_mime=arquivo.mime,
        arquivo_tamanho=arquivo.tamanho,
    )


def falhar(pedido_id: uuid.UUID, codigo_da_falha: str) -> PedidoDeRelatorio | None:
    return _transicionar(
        pedido_id, ComandoDoPedido.FALHAR, concluido_em=timezone.now(), codigo_da_falha=codigo_da_falha
    )


def expirar(pedido_id: uuid.UUID) -> PedidoDeRelatorio | None:
    return _transicionar(pedido_id, ComandoDoPedido.EXPIRAR, expirado_em=timezone.now())
