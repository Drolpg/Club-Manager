"""Os avisos de `relatorios`: o relatório ficou pronto ou não pôde ser gerado (CA-05, CA-07, CA-08).

Só para quem pediu. O texto diz o tipo e o período, e nunca leva o arquivo, link para ele nem valores; o
e-mail segue as preferências de notificação. A `chave` impede o aviso repetido (CA-06).
"""

from datetime import date

from notificacoes import public as notificacoes
from relatorios import tipos
from relatorios.models import PedidoDeRelatorio
from relatorios.services.pedidos import ITEM_TIPO

NOTIF_PRONTO = "relatorios.pronto"
NOTIF_FALHOU = "relatorios.falhou"
CAMINHO = "/relatorios"

# Código → descrição. Nenhum dos dois pede ação.
TIPOS_DE_NOTIFICACAO: dict[str, str] = {
    NOTIF_PRONTO: "Um relatório que você pediu ficou pronto para baixar.",
    NOTIF_FALHOU: "Um relatório que você pediu não pôde ser gerado.",
}


def registrar_tipos() -> None:
    for codigo, descricao in TIPOS_DE_NOTIFICACAO.items():
        notificacoes.registrar_tipo(codigo, pede_acao=False, descricao=descricao)


def _data(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _texto(pedido: PedidoDeRelatorio) -> str:
    tipo = tipos.obter(pedido.tipo)
    nome = tipo.nome if tipo is not None else pedido.tipo
    de, ate = pedido.parametros.get("de"), pedido.parametros.get("ate")
    if de and ate:
        return f"{nome}, de {_data(de)} a {_data(ate)}, em {pedido.formato}."
    return f"{nome}, em {pedido.formato}."


def _avisar(pedido: PedidoDeRelatorio, tipo: str, titulo: str) -> None:
    notificacoes.notificar(
        tipo=tipo,
        destinatarios=[pedido.pedido_por_id],
        titulo=titulo,
        texto=_texto(pedido),
        item_tipo=ITEM_TIPO,
        item_id=pedido.id,
        caminho=CAMINHO,
        chave=f"{tipo}:{pedido.id}",
    )


def pronto(pedido: PedidoDeRelatorio) -> None:
    _avisar(pedido, NOTIF_PRONTO, "Relatório pronto")


def falhou(pedido: PedidoDeRelatorio) -> None:
    _avisar(pedido, NOTIF_FALHOU, "Não foi possível gerar o relatório")
