"""Notificações do módulo financeiro usando chaves idempotentes e limites de tamanho."""

import uuid
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal

from acesso import public as acesso
from financeiro import tipos
from financeiro.domain.autorizacao import (
    PERM_COBRANCAS_CRIAR,
    PERM_DIVIDAS_DECIDIR,
    PERM_ENTRADAS_VALIDAR,
    PERM_PAGAMENTOS_VALIDAR,
    PERM_QUESTIONAMENTOS_DECIDIR,
)
from financeiro.models import Cobranca, Entrada, Pagamento, Questionamento
from notificacoes import public as notificacoes
from permissoes import public as permissoes

_TITULO = 120
_TEXTO = 500


def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _reais(valor: Decimal) -> str:
    formatado = f"{valor:,.2f}"
    return "R$ " + formatado.replace(",", "_").replace(".", ",").replace("_", ".")


def _data_br(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def _nome(usuario_id: uuid.UUID | None) -> str:
    usuario = acesso.usuario_por_id(usuario_id) if usuario_id else None
    return usuario.nome if usuario else "Diretoria"


def _destinatarios_permissao(codigo: str, *, exceto: uuid.UUID | None = None) -> set[uuid.UUID]:
    ids = set(permissoes.quem_pode(codigo))
    if exceto is not None:
        ids.discard(exceto)
    return ids


def _notificar(
    *,
    tipo: str,
    destinatarios: Iterable[uuid.UUID],
    titulo: str,
    texto: str,
    item_tipo: str,
    item_id: uuid.UUID,
    caminho: str,
    chave: str,
) -> None:
    lista = set(destinatarios)
    if not lista:
        return
    notificacoes.notificar(
        tipo=tipo,
        destinatarios=lista,
        titulo=_cortar(titulo, _TITULO),
        texto=_cortar(texto, _TEXTO),
        item_tipo=item_tipo,
        item_id=item_id,
        caminho=caminho,
        chave=chave,
    )


def _enviar_cobranca(
    cobranca: Cobranca, *, tipo: str, destinatarios: Iterable[uuid.UUID], titulo: str, texto: str, chave: str
) -> None:
    _notificar(
        tipo=tipo,
        destinatarios=destinatarios,
        titulo=titulo,
        texto=texto,
        item_tipo="cobranca",
        item_id=cobranca.id,
        caminho=f"/cobrancas/{cobranca.id}",
        chave=chave,
    )


def cobranca_criada(cobranca: Cobranca) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_COBRANCA_CRIADA,
        destinatarios={cobranca.devedor_id},
        titulo="Nova cobrança disponível",
        texto=(
            f"Cobrança “{cobranca.descricao}” ({_reais(cobranca.valor)}) com vencimento em "
            f"{_data_br(cobranca.vencimento)}."
        ),
        chave=f"cobranca-criada:{cobranca.id}",
    )


def lembrete_3_dias(cobranca: Cobranca) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_LEMBRETE_3_DIAS,
        destinatarios={cobranca.devedor_id},
        titulo="Cobrança vence em 3 dias",
        texto=(
            f"A cobrança “{cobranca.descricao}” ({_reais(cobranca.valor)}) vence em "
            f"{_data_br(cobranca.vencimento)}."
        ),
        chave=f"cobranca-lembrete-3d:{cobranca.id}",
    )


def lembrete_vencimento(cobranca: Cobranca) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_VENCIMENTO_HOJE,
        destinatarios={cobranca.devedor_id},
        titulo="Cobrança vence hoje",
        texto=f"A cobrança “{cobranca.descricao}” ({_reais(cobranca.valor)}) vence hoje.",
        chave=f"cobranca-vencimento:{cobranca.id}",
    )


def pagamento_registrado(cobranca: Cobranca, pagamento: Pagamento) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_PAGAMENTO_REGISTRADO,
        destinatarios=_destinatarios_permissao(PERM_PAGAMENTOS_VALIDAR, exceto=cobranca.devedor_id),
        titulo="Pagamento aguardando validação",
        texto=(
            f"{_nome(cobranca.devedor_id)} registrou pagamento de “{cobranca.descricao}” "
            f"({_reais(cobranca.valor)})."
        ),
        chave=f"pagamento-registrado:{pagamento.id}",
    )


def pagamento_validado(cobranca: Cobranca, pagamento: Pagamento) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_PAGAMENTO_VALIDADO,
        destinatarios={cobranca.devedor_id},
        titulo="Pagamento validado",
        texto=f"Seu pagamento de “{cobranca.descricao}” ({_reais(cobranca.valor)}) foi validado.",
        chave=f"pagamento-validado:{pagamento.id}",
    )


def pagamento_rejeitado(cobranca: Cobranca, pagamento: Pagamento) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_PAGAMENTO_REJEITADO,
        destinatarios={cobranca.devedor_id},
        titulo="Pagamento rejeitado",
        texto=(
            f"Seu pagamento de “{cobranca.descricao}” foi rejeitado ({pagamento.motivo_texto}). "
            "Registre novamente."
        ),
        chave=f"pagamento-rejeitado:{pagamento.id}",
    )


def cobranca_atrasada(cobranca: Cobranca) -> None:
    nome_devedor = _nome(cobranca.devedor_id)
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_ATRASADA_DEVEDOR,
        destinatarios={cobranca.devedor_id},
        titulo="Cobrança em atraso",
        texto=(
            f"A cobrança “{cobranca.descricao}” ({_reais(cobranca.valor)}) venceu em "
            f"{_data_br(cobranca.vencimento)} e está atrasada."
        ),
        chave=f"cobranca-atrasada-dev:{cobranca.id}",
    )
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_ATRASADA_FINANCEIRO,
        destinatarios=_destinatarios_permissao(PERM_COBRANCAS_CRIAR, exceto=cobranca.devedor_id),
        titulo="Cobrança atrasada no clube",
        texto=(
            f"A cobrança “{cobranca.descricao}” de {nome_devedor} ({_reais(cobranca.valor)}) "
            f"venceu em {_data_br(cobranca.vencimento)}."
        ),
        chave=f"cobranca-atrasada-fin:{cobranca.id}",
    )


def cobranca_questionada(cobranca: Cobranca, questionamento: Questionamento) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_QUESTIONADA,
        destinatarios=_destinatarios_permissao(PERM_QUESTIONAMENTOS_DECIDIR, exceto=cobranca.devedor_id),
        titulo="Cobrança questionada",
        texto=f"{_nome(cobranca.devedor_id)} questionou “{cobranca.descricao}”: {questionamento.texto}",
        chave=f"cobranca-questionada:{questionamento.id}",
    )


def questionamento_decidido(cobranca: Cobranca, questionamento: Questionamento) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_QUESTIONAMENTO_DECIDIDO,
        destinatarios={cobranca.devedor_id},
        titulo="Questionamento decidido",
        texto=(
            f"Seu questionamento sobre “{cobranca.descricao}” recebeu a decisão "
            f"{questionamento.decisao} ({questionamento.motivo_texto})."
        ),
        chave=f"questionamento-decidido:{questionamento.id}",
    )


def devedor_convocado(cobranca: Cobranca) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_DEVEDOR_CONVOCADO,
        destinatarios={cobranca.devedor_id},
        titulo="Convocação de inadimplência",
        texto=(
            f"O prazo da cobrança atrasada “{cobranca.descricao}” terminou. Registre sua "
            "justificativa ou regularize o pagamento."
        ),
        chave=f"devedor-convocado:{cobranca.id}",
    )
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_CONVOCACAO_FINANCEIRO,
        destinatarios=_destinatarios_permissao(PERM_DIVIDAS_DECIDIR, exceto=cobranca.devedor_id),
        titulo="Devedor convocado para decisão",
        texto=f"{_nome(cobranca.devedor_id)} foi convocado pela cobrança “{cobranca.descricao}”.",
        chave=f"convocacao-fin:{cobranca.id}",
    )


def divida_justificada(cobranca: Cobranca) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_DIVIDA_JUSTIFICADA,
        destinatarios=_destinatarios_permissao(PERM_DIVIDAS_DECIDIR, exceto=cobranca.devedor_id),
        titulo="Justificativa de dívida registrada",
        texto=f"{_nome(cobranca.devedor_id)} justificou a cobrança “{cobranca.descricao}”.",
        chave=f"divida-justificada:{cobranca.id}",
    )


def divida_decidida(cobranca: Cobranca, *, decisao: str, motivo_texto: str) -> None:
    _enviar_cobranca(
        cobranca,
        tipo=tipos.NOTIF_DIVIDA_DECIDIDA,
        destinatarios={cobranca.devedor_id},
        titulo="Decisão sobre dívida",
        texto=f"Sua dívida “{cobranca.descricao}” teve decisão {decisao} ({motivo_texto}).",
        chave=f"divida-decidida:{cobranca.id}:{decisao}",
    )


def entrada_registrada(entrada: Entrada) -> None:
    nome_reg = _nome(entrada.registrada_por_id)
    _notificar(
        tipo=tipos.NOTIF_ENTRADA_REGISTRADA,
        destinatarios=_destinatarios_permissao(PERM_ENTRADAS_VALIDAR, exceto=entrada.registrada_por_id),
        titulo="Entrada aguardando validação",
        texto=f"{entrada.origem} ({_reais(entrada.valor)}) registrada por {nome_reg}.",
        item_tipo="entrada",
        item_id=entrada.id,
        caminho="/entradas",
        chave=f"entrada-registrada:{entrada.id}",
    )


def entrada_decidida(entrada: Entrada) -> None:
    estado = "validada" if entrada.situacao == "VALIDADA" else "rejeitada"
    resumo = f"{entrada.origem} ({_reais(entrada.valor)})"
    _notificar(
        tipo=tipos.NOTIF_ENTRADA_DECIDIDA,
        destinatarios={entrada.registrada_por_id},
        titulo=f"Entrada {estado}",
        texto=f"A entrada “{resumo}” foi {estado} ({entrada.motivo_texto}).",
        item_tipo="entrada",
        item_id=entrada.id,
        caminho="/entradas",
        chave=f"entrada-decidida:{entrada.id}:{entrada.situacao}",
    )


def diretor_desativado_com_cobrancas(usuario_id: uuid.UUID, desativado_em: datetime, quantidade: int) -> None:
    _notificar(
        tipo=tipos.NOTIF_DIRETOR_DESATIVADO,
        destinatarios=_destinatarios_permissao(PERM_COBRANCAS_CRIAR, exceto=usuario_id),
        titulo="Diretor desativado com cobranças em aberto",
        texto=(
            f"{_nome(usuario_id)} foi desativado e possui {quantidade} cobrança(s) não encerrada(s) "
            "para decisão do financeiro."
        ),
        item_tipo="usuario",
        item_id=usuario_id,
        caminho="/cobrancas",
        chave=f"diretor-desativado:{usuario_id}:{desativado_em.isoformat()}",
    )
