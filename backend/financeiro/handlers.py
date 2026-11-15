"""Tratadores de eventos de integração de contextos inferiores para o módulo financeiro."""

import uuid
from datetime import datetime

from django.utils import timezone

from acesso import public as acesso
from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro.domain.transicoes import SituacaoCobranca, SituacaoSaida
from financeiro.models import (
    CategoriaFinanceira,
    Cobranca,
    Complemento,
    Cotacao,
    Saida,
    SituacaoSuspensao,
    Suspensao,
)
from financeiro.services import avisos
from financeiro.tipos import OrcamentoDeEventoMudou
from kernel import events
from kernel.dinheiro import Dinheiro


def ao_desativar_usuario(evento: acesso.UsuarioDesativado) -> None:
    """Encerra suspensões vigentes e avisa o financeiro sem apagar cobranças do diretor."""
    suspensoes = Suspensao.objects.filter(diretor_id=evento.usuario_id, situacao=SituacaoSuspensao.VIGENTE)
    for suspensao in suspensoes:
        suspensao.encerrar(por_id=None, agora=evento.desativado_em)
        auditoria.registrar(
            acao="SUSPENSAO_ENCERRADA_DESATIVACAO",
            ator_id=None,
            item_tipo="suspensao",
            item_id=suspensao.id,
            dados={"diretor_id": str(evento.usuario_id)},
        )

    cobrancas_abertas = Cobranca.objects.filter(
        devedor_id=evento.usuario_id,
        situacao__in=(
            SituacaoCobranca.ABERTA,
            SituacaoCobranca.EM_VALIDACAO,
            SituacaoCobranca.ATRASADA,
        ),
    ).count()
    if cobrancas_abertas > 0:
        avisos.diretor_desativado_com_cobrancas(
            evento.usuario_id,
            evento.desativado_em,
            cobrancas_abertas,
        )


def _tratar_complemento(mudanca: aprovacoes.MudancaDeSolicitacao, agora: datetime) -> None:
    comp = (
        Complemento.objects.select_for_update()
        .select_related("saida")
        .filter(solicitacao_id=mudanca.solicitacao_id)
        .first()
    )
    if comp is None:
        return
    if mudanca.acontecimento == aprovacoes.Acontecimento.APROVADA:
        comp.aprovar(agora, valor=mudanca.valor)
        auditoria.registrar(
            ator_id=mudanca.ator_id,
            acao="COMPLEMENTO_APROVADO",
            item_tipo="saida",
            item_id=comp.saida_id,
            dados={
                "complemento_id": str(comp.id),
                "solicitacao_id": str(mudanca.solicitacao_id),
                "valor": str(comp.valor),
            },
        )
        avisos.complemento_aprovado(comp.saida, comp)
    elif mudanca.acontecimento == aprovacoes.Acontecimento.RECUSADA:
        comp.recusar(agora)
        auditoria.registrar(
            ator_id=mudanca.ator_id,
            acao="COMPLEMENTO_RECUSADO",
            item_tipo="saida",
            item_id=comp.saida_id,
            dados={"complemento_id": str(comp.id), "solicitacao_id": str(mudanca.solicitacao_id)},
        )
    elif mudanca.acontecimento == aprovacoes.Acontecimento.CANCELADA:
        comp.cancelar(agora)
        auditoria.registrar(
            ator_id=mudanca.ator_id,
            acao="COMPLEMENTO_CANCELADO",
            item_tipo="saida",
            item_id=comp.saida_id,
            dados={"complemento_id": str(comp.id), "solicitacao_id": str(mudanca.solicitacao_id)},
        )


def _tratar_saida_inicial(
    mudanca: aprovacoes.MudancaDeSolicitacao,
    info: aprovacoes.SolicitacaoInfo,
    agora: datetime,
) -> None:
    conteudo = info.conteudo
    if mudanca.acontecimento == aprovacoes.Acontecimento.APROVADA:
        ja_existe = Saida.objects.filter(
            solicitacao_id=mudanca.solicitacao_id, versao_aprovada=mudanca.versao
        ).exists()
        if ja_existe:
            return
        valor = mudanca.valor or (Dinheiro(info.valor) if info.valor is not None else None)
        if valor is None:
            raise ValueError("Solicitação de gasto aprovada sem valor definido.")
        categoria = CategoriaFinanceira.objects.get(pk=uuid.UUID(str(conteudo["categoria_id"])))
        cot_raw = conteudo.get("cotacao_id")
        cotacao = Cotacao.objects.filter(pk=uuid.UUID(str(cot_raw))).first() if cot_raw else None
        ev_raw = conteudo.get("evento_id")
        evento_id = uuid.UUID(str(ev_raw)) if ev_raw else None
        saida = Saida.abrir(
            solicitacao_id=mudanca.solicitacao_id,
            versao_aprovada=mudanca.versao,
            solicitante_id=info.solicitante_id,
            categoria=categoria,
            setor_id=uuid.UUID(str(conteudo["setor_id"])),
            setor_nome=str(conteudo.get("setor_nome") or ""),
            descricao=str(conteudo["descricao"]),
            valor_aprovado=valor,
            evento_id=evento_id,
            cotacao=cotacao,
        )
        auditoria.registrar(
            ator_id=mudanca.ator_id,
            acao="SAIDA_ABERTA",
            item_tipo="saida",
            item_id=saida.id,
            dados={
                "solicitacao_id": str(mudanca.solicitacao_id),
                "versao": mudanca.versao,
                "valor": str(saida.valor_aprovado),
            },
        )
        avisos.saida_aguardando_envio(saida)
        return

    if mudanca.acontecimento in (
        aprovacoes.Acontecimento.CANCELADA,
        aprovacoes.Acontecimento.EDITADA,
        aprovacoes.Acontecimento.RETIRADA,
        aprovacoes.Acontecimento.RECUSADA,
        aprovacoes.Acontecimento.REABERTA,
        aprovacoes.Acontecimento.CONTESTADA,
    ):
        saida_ativa = (
            Saida.objects.select_for_update()
            .filter(solicitacao_id=mudanca.solicitacao_id)
            .exclude(situacao__in=[SituacaoSaida.CANCELADA.value, SituacaoSaida.ESTORNADA.value])
            .first()
        )
        if saida_ativa is not None:
            saida_ativa.cancelar(agora=agora)
            auditoria.registrar(
                ator_id=mudanca.ator_id,
                acao="SAIDA_CANCELADA",
                item_tipo="saida",
                item_id=saida_ativa.id,
                dados={
                    "solicitacao_id": str(mudanca.solicitacao_id),
                    "acontecimento": mudanca.acontecimento.value,
                },
            )


def ao_mudar_solicitacao_de_gasto(mudanca: aprovacoes.MudancaDeSolicitacao) -> None:
    """Reage às decisões/cancelamentos de solicitações `financeiro.gasto` na mesma transação."""
    info = aprovacoes.obter_solicitacao(mudanca.solicitacao_id)
    agora = timezone.now()
    if info.conteudo.get("saida_origem_id"):
        _tratar_complemento(mudanca, agora)
    else:
        _tratar_saida_inicial(mudanca, info, agora)

    ev_raw = info.conteudo.get("evento_id")
    if ev_raw:
        events.publish(
            OrcamentoDeEventoMudou(
                evento_id=uuid.UUID(str(ev_raw)),
                solicitacao_id=mudanca.solicitacao_id,
                acontecimento=mudanca.acontecimento.value,
                versao=mudanca.versao,
                valor=mudanca.valor.quantia if mudanca.valor is not None else None,
                aprovador_id=mudanca.ator_id,
            )
        )


def registrar() -> None:
    """Inscreve os tratadores de integração no barramento em processo (ADR-003)."""
    events.subscribe(acesso.UsuarioDesativado, ao_desativar_usuario)
