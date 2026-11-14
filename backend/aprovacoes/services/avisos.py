"""As notificações do motor (RF-045, RF-121; tabela da spec funcional; adendo 1: A5, A6, A7 e A11).

Chamadas dentro da transação do caso de uso, pela API pública de `notificacoes`: o registro entra na
transação, e o e-mail só sai depois do commit. A chave identifica o fato (tipo, solicitação e número da
versão) e impede a duplicata. O texto é cortado para caber nos limites de `notificacoes` (título 120,
texto 500).
"""

import uuid
from decimal import Decimal

from acesso import public as acesso
from aprovacoes import tipos
from aprovacoes.domain.decisores import pode_decidir
from aprovacoes.models import Decisao, Solicitacao, TipoDaDecisao
from notificacoes import public as notificacoes
from permissoes import public as permissoes

PARA_DECIDIR = "aprovacoes.para_decidir"
DECIDIDA = "aprovacoes.decidida"
CONTESTADA = "aprovacoes.contestada"
APROVADOR_INDICADO = "aprovacoes.aprovador_indicado"
INDICACAO_FEITA = "aprovacoes.indicacao_feita"
APROVACAO_PROPRIA = "aprovacoes.aprovacao_propria"
LEMBRETE = "aprovacoes.lembrete"
PARADA = "aprovacoes.parada"
SAIU_DA_FILA = "aprovacoes.saiu_da_fila"

# Código → (pede ação, descrição).
TIPOS: dict[str, tuple[bool, str]] = {
    PARA_DECIDIR: (
        True,
        "Uma solicitação foi enviada, reenviada, reaberta ou editada e espera a sua decisão.",
    ),
    DECIDIDA: (False, "A sua solicitação foi aprovada ou recusada."),
    CONTESTADA: (True, "A sua solicitação foi contestada: corrija e reenvie."),
    APROVADOR_INDICADO: (True, "Indicação para decidir uma solicitação, no lugar de quem a enviou."),
    INDICACAO_FEITA: (False, "Um solicitante indicou outro diretor para decidir o próprio pedido."),
    APROVACAO_PROPRIA: (False, "Alguém decidiu a própria solicitação, com a permissão de auto-aprovação."),
    LEMBRETE: (True, "Uma solicitação está há 3 dias em análise, esperando decisão."),
    PARADA: (False, "Uma solicitação está há 7 dias em análise sem decisão."),
    SAIU_DA_FILA: (False, "Uma solicitação que você podia decidir foi retirada ou cancelada."),
}

_TITULO = 120
_TEXTO = 500


def registrar_tipos() -> None:
    for codigo, (pede_acao, descricao) in TIPOS.items():
        notificacoes.registrar_tipo(codigo, pede_acao=pede_acao, descricao=descricao)


def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _reais(valor: Decimal) -> str:
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _nome(usuario_id: uuid.UUID | None) -> str:
    usuario = acesso.usuario_por_id(usuario_id) if usuario_id else None
    return usuario.nome if usuario else "Alguém"


def _resumo(solicitacao: Solicitacao) -> str:
    return solicitacao.versao_atual.resumo


def _notificar(
    tipo: str, destinatarios: set[uuid.UUID], solicitacao: Solicitacao, *, titulo: str, texto: str
) -> None:
    if not destinatarios:
        return
    notificacoes.notificar(
        tipo=tipo,
        destinatarios=destinatarios,
        titulo=_cortar(titulo, _TITULO),
        texto=_cortar(texto, _TEXTO),
        item_tipo="solicitacao",
        item_id=solicitacao.id,
        caminho=f"/solicitacoes/{solicitacao.id}",
        chave=f"{tipo}:{solicitacao.id}:{solicitacao.numero_da_versao_atual}",
    )


def quem_pode_decidir(solicitacao: Solicitacao) -> set[uuid.UUID]:
    """Quem tem a permissão de aprovar o tipo, mais o indicado; só quem lê gestão (adendo 1, A2); e o
    solicitante só se pode decidir o próprio pedido (auto-aprovação). A mesma função pura da decisão.
    """
    definicao = tipos.obter_tipo(solicitacao.tipo)
    if definicao is None:
        return set()
    candidatos = set(permissoes.quem_pode(definicao.permissao_de_aprovar))
    if solicitacao.aprovador_indicado_id is not None:
        candidatos.add(solicitacao.aprovador_indicado_id)
    resultado = set()
    for usuario_id in candidatos:
        if not permissoes.le_gestao(usuario_id):
            continue
        do_usuario = permissoes.permissoes_de(usuario_id)
        avaliacao = pode_decidir(
            ator_id=usuario_id,
            solicitante_id=solicitacao.solicitante_id,
            aprovador_indicado_id=solicitacao.aprovador_indicado_id,
            tem_permissao_de_aprovar=definicao.permissao_de_aprovar in do_usuario,
            tem_auto_aprovacao=tipos.AUTO_APROVAR in do_usuario,
        )
        if avaliacao.pode:
            resultado.add(usuario_id)
    return resultado


def _admins(exceto: uuid.UUID | None = None) -> set[uuid.UUID]:
    return {admin.id for admin in acesso.admins_ativos() if admin.id != exceto}


_VERSAO_NOVA = {
    "enviada": "{nome} enviou a solicitação “{resumo}” ({tipo}).",
    "reenviada": "{nome} corrigiu e reenviou a solicitação “{resumo}” ({tipo}).",
    "reaberta": "{nome} reabriu a solicitação recusada “{resumo}” ({tipo}).",
    "editada": "{nome} editou a solicitação aprovada “{resumo}” ({tipo}), que voltou à análise.",
}


def para_decidir(
    solicitacao: Solicitacao, *, ator_id: uuid.UUID, fato: str, excluir: frozenset[uuid.UUID] = frozenset()
) -> None:
    """Linha 1 da tabela: enviada, reenviada, reaberta ou editada → quem pode decidir (pede ação)."""
    definicao = tipos.obter_tipo(solicitacao.tipo)
    texto = _VERSAO_NOVA[fato].format(
        nome=_nome(ator_id),
        resumo=_resumo(solicitacao),
        tipo=definicao.nome if definicao else solicitacao.tipo,
    )
    _notificar(
        PARA_DECIDIR,
        quem_pode_decidir(solicitacao) - excluir,
        solicitacao,
        titulo="Solicitação para decidir",
        texto=f"{texto} Ela espera a sua decisão.",
    )


def ao_enviar(solicitacao: Solicitacao, *, ator_id: uuid.UUID) -> None:
    """Envio. Com indicação, o indicado recebe só o aviso de indicação (A6), e os admins são informados."""
    indicado = solicitacao.aprovador_indicado_id
    para_decidir(
        solicitacao,
        ator_id=ator_id,
        fato="enviada",
        excluir=frozenset({indicado}) if indicado else frozenset(),
    )
    if indicado is None:
        return
    resumo, nome = _resumo(solicitacao), _nome(ator_id)
    _notificar(
        APROVADOR_INDICADO,
        {indicado},
        solicitacao,
        titulo="Indicação para decidir uma solicitação",
        texto=f"{nome} indicou você para decidir a solicitação “{resumo}”.",
    )
    _notificar(
        INDICACAO_FEITA,
        _admins(exceto=ator_id),
        solicitacao,
        titulo="Aprovador indicado",
        texto=f"{nome} indicou {_nome(indicado)} para decidir a solicitação “{resumo}”.",
    )


def decidida(solicitacao: Solicitacao, decisao: Decisao) -> None:
    """Linhas 2 e 3: aprovada ou recusada → o solicitante (informativa); contestada → o solicitante (ação)."""
    resumo = _resumo_da_versao(decisao)
    destino = {solicitacao.solicitante_id}
    if decisao.tipo == TipoDaDecisao.CONTESTAR:
        teto = (
            f" Teto sugerido: {_reais(decisao.teto_sugerido)}." if decisao.teto_sugerido is not None else ""
        )
        _notificar(
            CONTESTADA,
            destino,
            solicitacao,
            titulo="Solicitação contestada",
            texto=(
                f"Sua solicitação “{resumo}” foi contestada para ajustes: corrija e reenvie. "
                f"Motivo: {decisao.motivo_texto}.{teto} Mensagem: {decisao.mensagem}"
            ),
        )
        return
    palavra = "aprovada" if decisao.tipo == TipoDaDecisao.APROVAR else "recusada"
    complemento = f" {decisao.texto}" if decisao.texto else ""
    _notificar(
        DECIDIDA,
        destino,
        solicitacao,
        titulo=f"Solicitação {palavra}",
        texto=f"Sua solicitação “{resumo}” foi {palavra}. Motivo: {decisao.motivo_texto}.{complemento}",
    )


def aprovacao_propria(solicitacao: Solicitacao, decisao: Decisao) -> None:
    """Linha 5: os admins são informados; se quem decidiu é admin, os outros admins (A5)."""
    palavras = {TipoDaDecisao.APROVAR: "aprovou", TipoDaDecisao.CONTESTAR: "contestou"}
    verbo = palavras.get(TipoDaDecisao(decisao.tipo), "recusou")
    _notificar(
        APROVACAO_PROPRIA,
        _admins(exceto=decisao.aprovador_id),
        solicitacao,
        titulo="Aprovação própria",
        texto=(
            f"{_nome(decisao.aprovador_id)} {verbo} a própria solicitação “{_resumo_da_versao(decisao)}”, "
            f"com a permissão de auto-aprovação. Motivo: {decisao.motivo_texto}."
        ),
    )


def saiu_da_fila(solicitacao: Solicitacao, *, ator_id: uuid.UUID, como: str) -> None:
    """Linha 8: retirada ou cancelada em análise → quem podia decidir, menos quem agiu (A7: só em análise)."""
    resumo = _resumo(solicitacao)
    texto = (
        f"{_nome(ator_id)} retirou a solicitação “{resumo}” para corrigir. Ela volta à fila se for reenviada."
        if como == "retirada"
        else f"A solicitação “{resumo}” foi cancelada e saiu da fila."
    )
    _notificar(
        SAIU_DA_FILA,
        quem_pode_decidir(solicitacao) - {ator_id},
        solicitacao,
        titulo="Solicitação saiu da fila",
        texto=texto,
    )


def lembrete(solicitacao: Solicitacao) -> None:
    """Linha 6: 3 dias em análise → quem pode decidir (pede ação)."""
    _notificar(
        LEMBRETE,
        quem_pode_decidir(solicitacao),
        solicitacao,
        titulo="Solicitação esperando decisão",
        texto=f"A solicitação “{_resumo(solicitacao)}” está há 3 dias em análise, esperando decisão.",
    )


def parada(solicitacao: Solicitacao) -> None:
    """Linha 7: 7 dias em análise → os admins (informativa)."""
    _notificar(
        PARADA,
        _admins(),
        solicitacao,
        titulo="Solicitação parada há 7 dias",
        texto=f"A solicitação “{_resumo(solicitacao)}” está há 7 dias em análise sem decisão.",
    )


def _resumo_da_versao(decisao: Decisao) -> str:
    return decisao.versao.resumo
