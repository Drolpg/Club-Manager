"""Consultas de `eventos`: referências, calendário, histórico, detalhe e histórico de auditoria. Só leitura.

Todas exigem a leitura de gestão, conferida antes da existência. O campo `acoes` do detalhe sai da mesma
função que as rotas usam (`domain/autorizacao`). As datas são as do fuso do sistema.
"""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from django.utils import timezone

from acesso import public as acesso
from aprovacoes import public as aprovacoes
from eventos.domain.autorizacao import PERM_APROVAR, acoes_disponiveis
from eventos.domain.situacao import SituacaoDoEvento
from eventos.erros import erro
from eventos.models import CategoriaDeEvento, Evento
from eventos.services.autorizacao import exigir_leitura_de_gestao, fatos
from eventos.services.presencas import quadro_do_evento
from permissoes import public as permissoes

S = SituacaoDoEvento
LIMITE_DO_CALENDARIO = 200
# Permissão do motor (catálogo): quem a tem decide o próprio pedido e não precisa indicar aprovador.
_AUTO_APROVAR = "solicitacoes.auto_aprovar"


def _inicio_do_dia(dia: date) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time.min))


def _pessoa(usuario_id: uuid.UUID | None) -> dict[str, Any] | None:
    if usuario_id is None:
        return None
    usuario = acesso.usuario_por_id(usuario_id)
    return {"id": usuario_id, "nome": usuario.nome if usuario else ""}


def _buscar(ator_id: uuid.UUID, evento_id: uuid.UUID) -> Evento:
    exigir_leitura_de_gestao(ator_id)
    evento = Evento.objects.filter(pk=evento_id).first()
    if evento is None:
        raise erro("NOT_FOUND", "Evento não encontrado.")
    return evento


def referencias(ator_id: uuid.UUID) -> dict[str, Any]:
    exigir_leitura_de_gestao(ator_id)
    do_ator = permissoes.permissoes_de(ator_id)
    aprovadores = [
        _pessoa(usuario_id)
        for usuario_id in permissoes.quem_pode(PERM_APROVAR)
        if permissoes.le_gestao(usuario_id)
    ]
    return {
        "categorias": [{"id": c.id, "nome": c.nome} for c in CategoriaDeEvento.objects.filter(ativa=True)],
        "aprovadores_eventos": sorted(aprovadores, key=lambda p: str(p["nome"]).lower() if p else ""),
        "precisa_indicar_aprovador": PERM_APROVAR in do_ator and _AUTO_APROVAR not in do_ator,
    }


def calendario(ator_id: uuid.UUID, *, ano: int, mes: int) -> list[Evento]:
    """CA-11: só publicados e realizados cuja data local cai no mês."""
    exigir_leitura_de_gestao(ator_id)
    primeiro = date(ano, mes, 1)
    seguinte = date(ano + (mes == 12), mes % 12 + 1, 1)
    return list(
        Evento.objects.filter(
            situacao__in=[S.PUBLICADO.value, S.REALIZADO.value],
            inicio__gte=_inicio_do_dia(primeiro),
            inicio__lt=_inicio_do_dia(seguinte),
        ).order_by("inicio", "id")[:LIMITE_DO_CALENDARIO]
    )


def historico(
    ator_id: uuid.UUID,
    *,
    situacao: str | None = None,
    categoria_id: uuid.UUID | None = None,
    de: date | None = None,
    ate: date | None = None,
    antes: uuid.UUID | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """CA-26: todos os eventos, em qualquer situação, do mais novo para o mais antigo, por cursor."""
    exigir_leitura_de_gestao(ator_id)
    consulta = Evento.objects.order_by("-inicio", "-id")
    if situacao:
        consulta = consulta.filter(situacao=situacao)
    if categoria_id:
        consulta = consulta.filter(categoria_id=categoria_id)
    if de:
        consulta = consulta.filter(inicio__gte=_inicio_do_dia(de))
    if ate:
        consulta = consulta.filter(inicio__lt=_inicio_do_dia(ate + timedelta(days=1)))
    if antes is not None:
        ancora = Evento.objects.filter(pk=antes).values("inicio", "id").first()
        if ancora is None:
            raise erro("NOT_FOUND", "Evento não encontrado.")
        consulta = consulta.filter(inicio__lte=ancora["inicio"]).exclude(
            inicio=ancora["inicio"], id__gte=ancora["id"]
        )
    itens = list(consulta[: limite + 1])
    return {"itens": itens[:limite], "tem_mais": len(itens) > limite}


def _situacao(solicitacao_id: uuid.UUID | None) -> str | None:
    return aprovacoes.situacao_de(solicitacao_id).value if solicitacao_id is not None else None


def detalhe_do_evento(evento: Evento, ator_id: uuid.UUID) -> dict[str, Any]:
    realizacao = None
    if evento.realizado_em_data is not None:
        realizacao = {
            "data": evento.realizado_em_data,
            "motivo": evento.realizacao_motivo,
            "por": _pessoa(evento.realizado_por_id),
            "em": evento.realizado_em,
        }
    cancelamento = None
    if evento.cancelado_em is not None:
        cancelamento = {
            "motivo": evento.cancelamento_motivo,
            "por": _pessoa(evento.cancelado_por_id),
            "pelo_sistema": evento.cancelado_pelo_sistema,
            "em": evento.cancelado_em,
        }
    orcamento = None
    if evento.solicitacao_orcamentaria_id is not None:
        orcamento = {
            "solicitacao_id": evento.solicitacao_orcamentaria_id,
            "situacao": _situacao(evento.solicitacao_orcamentaria_id),
        }
    return {
        "evento": evento,
        "proponente": _pessoa(evento.proponente_id),
        "solicitacao_do_evento": {
            "id": evento.solicitacao_do_evento_id,
            "situacao": _situacao(evento.solicitacao_do_evento_id),
        },
        "orcamento": orcamento,
        "presencas": quadro_do_evento(evento, ator_id),
        "realizacao": realizacao,
        "cancelamento": cancelamento,
        "acoes": [comando.value.lower() for comando in acoes_disponiveis(fatos(ator_id, evento))],
    }


def detalhe(ator_id: uuid.UUID, evento_id: uuid.UUID) -> dict[str, Any]:
    return detalhe_do_evento(_buscar(ator_id, evento_id), ator_id)


def historico_de_auditoria(ator_id: uuid.UUID, evento_id: uuid.UUID) -> list[acesso.RegistroDoHistorico]:
    evento = _buscar(ator_id, evento_id)
    return acesso.historico_com_nomes("evento", evento.id)
