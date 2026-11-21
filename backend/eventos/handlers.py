"""Como `eventos` reage ao motor e ao financeiro (ADR-003): na mesma transação de quem decidiu.

O tipo `eventos.evento` tem o próprio `preparar` e `ao_mudar`; o orçamento, que é um tipo do financeiro,
chega por `OrcamentoDeEventoMudou`. Os dois tratadores bloqueiam o evento, ignoram evento encerrado (é o que
acontece quando o próprio `eventos` cancela as solicitações ao cancelar o evento) e recalculam a situação.
"""

import uuid
from typing import Any

from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from eventos.erros import invalido
from eventos.models import Evento
from eventos.services import avisos, situacao
from financeiro import public as financeiro
from kernel import events


def _recusar(mensagem: str) -> Exception:
    return invalido({"evento_id": [mensagem]})


def preparar_solicitacao_do_evento(
    conteudo: dict[str, Any], solicitante_id: uuid.UUID
) -> aprovacoes.ConteudoPreparado:
    """O retrato canônico do evento: o conteúdo recebido só serve para achar o evento (spec técnica do M8)."""
    try:
        evento_id = uuid.UUID(str(conteudo.get("evento_id")))
    except ValueError:
        raise _recusar("Identificador de evento inválido.") from None
    evento = Evento.objects.filter(pk=evento_id).first()
    if evento is None:
        raise _recusar("Evento não encontrado.")
    if evento.proponente_id != solicitante_id:
        raise _recusar("A solicitação do evento é de quem o propôs.")
    return aprovacoes.ConteudoPreparado(
        conteudo={
            "evento_id": str(evento.id),
            "titulo": evento.titulo,
            "descricao": evento.descricao,
            "inicio": timezone.localtime(evento.inicio).isoformat(),
            "local": evento.local,
            "categoria_id": str(evento.categoria_id),
            "categoria_nome": evento.categoria_nome,
            "envolve_custo": evento.envolve_custo,
        },
        valor=None,
        resumo=evento.titulo,
    )


def _evento_aberto(**filtro: Any) -> Evento | None:
    evento = Evento.objects.select_for_update().filter(**filtro).first()
    if evento is None or evento.encerrado:
        return None
    return evento


def ao_mudar_solicitacao_do_evento(mudanca: aprovacoes.MudancaDeSolicitacao) -> None:
    evento = _evento_aberto(solicitacao_do_evento_id=mudanca.solicitacao_id)
    if evento is None:
        return
    situacao.recalcular(evento, ator_id=mudanca.ator_id)
    aprovada = mudanca.acontecimento == aprovacoes.Acontecimento.APROVADA
    if aprovada and evento.envolve_custo and evento.solicitacao_orcamentaria_id is None:
        avisos.montar_orcamento(evento, chave=f"evento-montar-orcamento:{evento.id}:{mudanca.versao}")


def ao_mudar_orcamento(mudanca: financeiro.OrcamentoDeEventoMudou) -> None:
    evento = _evento_aberto(pk=mudanca.evento_id)
    if evento is None or evento.solicitacao_orcamentaria_id != mudanca.solicitacao_id:
        return
    if mudanca.acontecimento == aprovacoes.Acontecimento.CANCELADA.value:
        # O orçamento cancelado por quem o abriu se desliga do evento (adendo 1 da funcional; Q1).
        evento.desvincular_orcamento(mudanca.solicitacao_id)
        auditoria.registrar(
            ator_id=mudanca.aprovador_id,
            acao="ORCAMENTO_DESVINCULADO",
            item_tipo="evento",
            item_id=evento.id,
            dados={"solicitacao_id": str(mudanca.solicitacao_id)},
        )
        avisos.montar_orcamento(
            evento, chave=f"evento-montar-orcamento:{evento.id}:desvinculo:{mudanca.solicitacao_id}"
        )
    situacao.recalcular(evento, ator_id=mudanca.aprovador_id)


def registrar() -> None:
    """Inscreve o tratador do orçamento no despachante em processo (ADR-003)."""
    events.subscribe(financeiro.OrcamentoDeEventoMudou, ao_mudar_orcamento)
