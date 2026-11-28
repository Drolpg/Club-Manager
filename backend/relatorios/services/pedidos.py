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
from django.db.models import Q
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
from relatorios.erros import (
    campo_invalido,
    erro,
    limite_invalido,
    pedido_nao_encontrado,
    pedidos_em_andamento,
)
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


# Consultas de quem pediu --------------------------------------------------------------------------------

LIMITE_PADRAO = 20
LIMITE_MAXIMO = 50


@dataclass(frozen=True)
class PaginaDePedidos:
    itens: list[PedidoDeRelatorio]
    tem_mais: bool


def _exigir_ativo(ator_id: uuid.UUID) -> None:
    ator = acesso.usuario_por_id(ator_id)
    if ator is None or not ator.ativo:
        raise erro("PERMISSION_DENIED")


def listar(
    ator_id: uuid.UUID, *, antes: uuid.UUID | None = None, limite: int = LIMITE_PADRAO
) -> PaginaDePedidos:
    """Os próprios pedidos, mais novos primeiro. O cursor é o ID do último da página anterior, e só vale um
    pedido do próprio ator; outro ou inexistente: 404 (CA-12).
    """
    _exigir_ativo(ator_id)
    if not 1 <= limite <= LIMITE_MAXIMO:
        raise limite_invalido(LIMITE_MAXIMO)
    meus = PedidoDeRelatorio.objects.filter(pedido_por_id=ator_id)
    if antes is not None:
        ancora = meus.filter(id=antes).values("pedido_em", "id").first()
        if ancora is None:
            raise pedido_nao_encontrado()
        meus = meus.filter(
            Q(pedido_em__lt=ancora["pedido_em"]) | Q(pedido_em=ancora["pedido_em"], id__lt=ancora["id"])
        )
    pedidos = list(meus.order_by("-pedido_em", "-id")[: limite + 1])
    return PaginaDePedidos(itens=pedidos[:limite], tem_mais=len(pedidos) > limite)


def obter(ator_id: uuid.UUID, pedido_id: uuid.UUID) -> PedidoDeRelatorio:
    """O próprio pedido. De outro ou inexistente: 403 nos dois casos, para não revelar o que existe (D4)."""
    _exigir_ativo(ator_id)
    pedido = PedidoDeRelatorio.objects.filter(id=pedido_id, pedido_por_id=ator_id).first()
    if pedido is None:
        raise erro("PERMISSION_DENIED")
    return pedido


def disponivel(pedido: PedidoDeRelatorio) -> bool:
    return (
        pedido.situacao == SituacaoDoPedido.PRONTO
        and pedido.expira_em is not None
        and pedido.expira_em > timezone.now()
    )


def nome_do_tipo(codigo: str) -> str:
    tipo = tipos.obter(codigo)
    return tipo.nome if tipo is not None else codigo
