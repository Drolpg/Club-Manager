"""Consultas e leitura do módulo financeiro (isolamento de escopo, filtros e detalhe)."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from acesso import public as acesso
from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro.domain.autorizacao import (
    PERM_ENTRADAS_VALIDAR,
    PERM_PAGAMENTOS_VALIDAR,
    acoes_cobranca_disponiveis,
    acoes_saida_disponiveis,
    pode_ver_anexos_saida,
    pode_ver_comprovante_cobranca,
    pode_ver_comprovante_entrada,
)
from financeiro.domain.qrcode_svg import gerar_qrcode_svg
from financeiro.domain.saidas import (
    PRAZO_VENCIMENTO_PRESTACAO_DIAS,
    calcular_valor_realizado_saida,
    prestacao_em_atraso,
)
from financeiro.domain.transicoes import SITUACOES_ATIVAS_SAIDA, SituacaoEntrada, SituacaoSaida
from financeiro.erros import erro
from financeiro.models import (
    Cobranca,
    Complemento,
    Entrada,
    Envio,
    Estorno,
    Pagamento,
    Saida,
    SituacaoComplemento,
)
from financeiro.services.autorizacao import (
    exigir_diretor_ativo,
    exigir_leitura_gestao,
    fatos_cobranca,
    fatos_saida,
    permissao_ou_admin,
)
from kernel.errors import BusinessError
from permissoes import public as permissoes


@dataclass(frozen=True)
class PessoaInfo:
    id: uuid.UUID
    nome: str


@dataclass(frozen=True)
class PaginaDeCobrancas:
    itens: list[dict[str, Any]]
    tem_mais: bool


def _pessoa(usuario_id: uuid.UUID, cache: dict[uuid.UUID, PessoaInfo]) -> PessoaInfo:
    if usuario_id not in cache:
        usuario = acesso.usuario_por_id(usuario_id)
        cache[usuario_id] = PessoaInfo(id=usuario_id, nome=usuario.nome if usuario else "Diretor removido")
    return cache[usuario_id]


def pessoa_dict(usuario_id: uuid.UUID, cache: dict[uuid.UUID, PessoaInfo]) -> dict[str, Any]:
    p = _pessoa(usuario_id, cache)
    return {"id": p.id, "nome": p.nome}


def _pessoa_dict(usuario_id: uuid.UUID, cache: dict[uuid.UUID, PessoaInfo]) -> dict[str, Any]:
    return pessoa_dict(usuario_id, cache)


def _serializar_item(cobranca: Cobranca, cache: dict[uuid.UUID, PessoaInfo]) -> dict[str, Any]:
    return {
        "id": cobranca.id,
        "devedor": _pessoa_dict(cobranca.devedor_id, cache),
        "categoria_id": cobranca.categoria_id,
        "categoria_nome": cobranca.categoria_nome,
        "descricao": cobranca.descricao,
        "valor": cobranca.valor,
        "vencimento": cobranca.vencimento,
        "situacao": cobranca.situacao,
        "tem_questionamento_aberto": cobranca.tem_questionamento_aberto,
        "tem_convocacao_aberta": cobranca.convocacao_aberta is not None,
        "recorrencia_id": cobranca.recorrencia_id,
        "competencia": cobranca.competencia,
        "cobranca_origem_id": cobranca.cobranca_origem_id,
        "criada_em": cobranca.criada_em,
    }


def _serializar_pagamento(
    pagamento: Pagamento, *, pode_ver_comprovante: bool, cache: dict[uuid.UUID, PessoaInfo]
) -> dict[str, Any]:
    return {
        "id": pagamento.id,
        "forma": pagamento.forma,
        "data_pagamento": pagamento.data_pagamento,
        "recebedor": _pessoa_dict(pagamento.recebedor_id, cache) if pagamento.recebedor_id else None,
        "comprovante_disponivel": bool(pagamento.comprovante_chave) and pode_ver_comprovante,
        "comprovante_nome": pagamento.comprovante_nome if pode_ver_comprovante else "",
        "situacao": pagamento.situacao,
        "decidido_por": (
            _pessoa_dict(pagamento.decidido_por_id, cache) if pagamento.decidido_por_id else None
        ),
        "motivo_texto": pagamento.motivo_texto,
        "decisao_texto": pagamento.decisao_texto,
        "registrado_em": pagamento.registrado_em,
        "decidido_em": pagamento.decidido_em,
    }


def serializar_estorno_resumo(alvo: Any, cache: dict[uuid.UUID, PessoaInfo]) -> dict[str, Any] | None:
    """Serializa o resumo de um estorno vinculado a saída, entrada ou cobrança."""
    estorno_obj: Estorno | None = getattr(alvo, "estorno", None)
    if estorno_obj is None:
        return None
    return {
        "id": estorno_obj.id,
        "valor": estorno_obj.valor,
        "motivo_texto": estorno_obj.motivo_texto,
        "justificativa": estorno_obj.justificativa,
        "registrado_por": _pessoa_dict(estorno_obj.registrado_por_id, cache),
        "registrado_em": estorno_obj.registrado_em,
    }


def serializar_detalhe(cobranca: Cobranca, *, ator_id: uuid.UUID) -> dict[str, Any]:
    usuario = exigir_diretor_ativo(ator_id)
    cache: dict[uuid.UUID, PessoaInfo] = {}
    pode_validar = permissao_ou_admin(usuario, PERM_PAGAMENTOS_VALIDAR)
    pode_comprovante = pode_ver_comprovante_cobranca(
        ator_id=ator_id,
        ator_admin=usuario.admin,
        tem_permissao_validar=pode_validar,
        devedor_id=cobranca.devedor_id,
    )
    fatos = fatos_cobranca(cobranca, ator_id)
    item = _serializar_item(cobranca, cache)

    conv = getattr(cobranca, "convocacao", None)
    reneg = getattr(cobranca, "renegociacao", None)
    return {
        **item,
        "limite_de_inadimplencia": cobranca.limite_de_inadimplencia,
        "chave_pix_id": cobranca.chave_pix_id,
        "pix_chave": cobranca.pix_chave,
        "pix_nome_recebedor": cobranca.pix_nome_recebedor,
        "pix_cidade": cobranca.pix_cidade,
        "pix_copia_e_cola": cobranca.pix_copia_e_cola,
        "qrcode_svg": gerar_qrcode_svg(cobranca.pix_copia_e_cola),
        "pausada_por_questionamento_em": cobranca.pausada_por_questionamento_em,
        "dias_pausados_inadimplencia": cobranca.dias_pausados_inadimplencia,
        "isencao": (
            {
                "por": _pessoa_dict(cobranca.isencao_por_id, cache),
                "justificativa": cobranca.isencao_justificativa,
            }
            if cobranca.isencao_por_id
            else None
        ),
        "cancelamento": (
            {
                "por": _pessoa_dict(cobranca.cancelamento_por_id, cache),
                "motivo_texto": cobranca.cancelamento_motivo_texto,
                "texto": cobranca.cancelamento_texto,
            }
            if cobranca.cancelamento_por_id
            else None
        ),
        "perdao": (
            {
                "por": _pessoa_dict(cobranca.perdao_por_id, cache),
                "motivo_texto": cobranca.perdao_motivo_texto,
                "texto": cobranca.perdao_texto,
            }
            if cobranca.perdao_por_id
            else None
        ),
        "paga_em": cobranca.paga_em,
        "encerrada_em": cobranca.encerrada_em,
        "atualizada_em": cobranca.atualizada_em,
        "pagamentos": [
            _serializar_pagamento(p, pode_ver_comprovante=pode_comprovante, cache=cache)
            for p in cobranca.pagamentos.all()
        ],
        "questionamentos": [
            {
                "id": q.id,
                "texto": q.texto,
                "situacao": q.situacao,
                "decisao": q.decisao or None,
                "decidido_por": _pessoa_dict(q.decidido_por_id, cache) if q.decidido_por_id else None,
                "motivo_texto": q.motivo_texto,
                "decisao_texto": q.decisao_texto,
                "aberto_em": q.aberto_em,
                "decidido_em": q.decidido_em,
            }
            for q in cobranca.questionamentos.all()
        ],
        "convocacao": (
            {
                "convocado_em": conv.convocado_em,
                "justificativa_do_devedor": conv.justificativa_do_devedor,
                "justificada_em": conv.justificada_em,
                "decisao": conv.decisao or None,
                "decidido_por": (_pessoa_dict(conv.decidido_por_id, cache) if conv.decidido_por_id else None),
                "motivo_texto": conv.motivo_texto,
                "decisao_texto": conv.decisao_texto,
                "decidido_em": conv.decidido_em,
            }
            if conv
            else None
        ),
        "renegociacao": (
            {
                "id": reneg.id,
                "valor_acordado": reneg.valor_acordado,
                "quantidade_parcelas": reneg.quantidade_parcelas,
                "decidido_por": _pessoa_dict(reneg.decidido_por_id, cache),
                "motivo_texto": reneg.motivo_texto,
                "decisao_texto": reneg.decisao_texto,
                "criada_em": reneg.criada_em,
            }
            if reneg
            else None
        ),
        "parcelas": [_serializar_item(p, cache) for p in cobranca.parcelas.all()],
        "estorno": serializar_estorno_resumo(cobranca, cache),
        "acoes": acoes_cobranca_disponiveis(fatos),
    }


def _depois_do_cursor(qs: Any, antes: uuid.UUID | None) -> Any:
    """As cobranças depois da âncora `antes`, na ordem de `criada_em` e `id`; cursor ruim: `NOT_FOUND`."""
    if antes is None:
        return qs
    ancora = Cobranca.objects.filter(pk=antes).values("criada_em", "id").first()
    if ancora is None:
        raise erro("NOT_FOUND")
    qs = qs.exclude(pk=antes).filter(criada_em__lte=ancora["criada_em"])
    return qs.exclude(criada_em=ancora["criada_em"], id__gte=ancora["id"])


def _paginar(qs: Any, *, antes: uuid.UUID | None, limite: int) -> PaginaDeCobrancas:
    qs = _depois_do_cursor(qs, antes)
    itens_bd = list(qs[: limite + 1])
    tem_mais = len(itens_bd) > limite
    cache: dict[uuid.UUID, PessoaInfo] = {}
    return PaginaDeCobrancas(
        itens=[_serializar_item(c, cache) for c in itens_bd[:limite]],
        tem_mais=tem_mais,
    )


def listar(
    ator_id: uuid.UUID,
    *,
    situacao: str | None = None,
    categoria_id: uuid.UUID | None = None,
    devedor_id: uuid.UUID | None = None,
    de: date | None = None,
    ate: date | None = None,
    inadimplentes: bool = False,
    antes: uuid.UUID | None = None,
    limite: int = 20,
) -> PaginaDeCobrancas:
    exigir_leitura_gestao(ator_id)
    qs = Cobranca.objects.all()
    if inadimplentes:
        qs = qs.filter(situacao="ATRASADA").exclude(questionamentos__situacao="ABERTO")
    elif situacao:
        qs = qs.filter(situacao=situacao)
    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)
    if devedor_id:
        qs = qs.filter(devedor_id=devedor_id)
    if de:
        qs = qs.filter(vencimento__gte=de)
    if ate:
        qs = qs.filter(vencimento__lte=ate)
    return _paginar(qs, antes=antes, limite=limite)


def minhas_cobrancas(
    ator_id: uuid.UUID,
    *,
    situacao: str | None = None,
    antes: uuid.UUID | None = None,
    limite: int = 20,
) -> PaginaDeCobrancas:
    exigir_diretor_ativo(ator_id)
    qs = Cobranca.objects.filter(devedor_id=ator_id)
    if situacao:
        qs = qs.filter(situacao=situacao)
    return _paginar(qs, antes=antes, limite=limite)


@dataclass(frozen=True)
class PagamentoDoDevedor:
    """Um pagamento no perfil: forma, data e situação. Nunca o comprovante."""

    forma: str
    data_pagamento: date
    situacao: str


@dataclass(frozen=True)
class CobrancaDoDevedor:
    id: uuid.UUID
    descricao: str
    categoria_nome: str
    valor: str
    vencimento: date
    situacao: str
    pagamentos: list[PagamentoDoDevedor]


@dataclass(frozen=True)
class PaginaDeCobrancasDoDevedor:
    itens: list[CobrancaDoDevedor]
    tem_mais: bool


def cobrancas_do_devedor(
    usuario_id: uuid.UUID, *, antes: uuid.UUID | None = None, limite: int = 10
) -> PaginaDeCobrancasDoDevedor:
    """As cobranças em que o usuário é o devedor, com os pagamentos, para o perfil (CA-02).

    Só leitura e sem conferir quem pergunta (isso é do serviço do perfil): o devedor pode estar desativado ou
    sem cargo. Os pagamentos vêm numa consulta só, e nenhum campo de comprovante sai daqui.
    """
    qs = _depois_do_cursor(Cobranca.objects.filter(devedor_id=usuario_id), antes)
    cobrancas = list(qs[: limite + 1])
    pagina = cobrancas[:limite]
    pagamentos: dict[uuid.UUID, list[PagamentoDoDevedor]] = {c.id: [] for c in pagina}
    registrados = Pagamento.objects.filter(cobranca_id__in=pagamentos).order_by("registrado_em", "id")
    for pagamento in registrados:
        pagamentos[pagamento.cobranca_id].append(
            PagamentoDoDevedor(
                forma=pagamento.forma, data_pagamento=pagamento.data_pagamento, situacao=pagamento.situacao
            )
        )
    itens = [
        CobrancaDoDevedor(
            id=c.id,
            descricao=c.descricao,
            categoria_nome=c.categoria_nome,
            valor=str(c.valor),
            vencimento=c.vencimento,
            situacao=c.situacao,
            pagamentos=pagamentos[c.id],
        )
        for c in pagina
    ]
    return PaginaDeCobrancasDoDevedor(itens=itens, tem_mais=len(cobrancas) > limite)


def obter_no_escopo(ator_id: uuid.UUID, cobranca_id: uuid.UUID) -> Cobranca:
    """Busca cobrança respeitando sigilo contra enumeração de IDs por quem não lê gestão."""
    usuario = exigir_diretor_ativo(ator_id)
    from permissoes import public as permissoes

    le_gestao = usuario.admin or permissoes.le_gestao(ator_id)
    cobranca = Cobranca.objects.filter(pk=cobranca_id).first()
    if not le_gestao:
        if cobranca is None or cobranca.devedor_id != ator_id:
            raise erro("PERMISSION_DENIED")
        return cobranca
    if cobranca is None:
        raise erro("NOT_FOUND")
    return cobranca


def detalhe(ator_id: uuid.UUID, cobranca_id: uuid.UUID) -> dict[str, Any]:
    cobranca = obter_no_escopo(ator_id, cobranca_id)
    return serializar_detalhe(cobranca, ator_id=ator_id)


def serializar_item(cobranca: Cobranca, cache: dict[uuid.UUID, PessoaInfo] | None = None) -> dict[str, Any]:
    pessoas = cache if cache is not None else {}
    return _serializar_item(cobranca, pessoas)


def serializar_historico(registros: list[auditoria.Registro]) -> list[dict[str, Any]]:
    cache: dict[uuid.UUID, PessoaInfo] = {}
    return [
        {
            "acao": r.acao,
            "ator": _pessoa_dict(r.ator_id, cache) if r.ator_id else None,
            "justificativa": r.justificativa,
            "dados": r.dados,
            "criado_em": r.criado_em,
        }
        for r in registros
    ]


def historico(ator_id: uuid.UUID, cobranca_id: uuid.UUID) -> list[dict[str, Any]]:
    cobranca = obter_no_escopo(ator_id, cobranca_id)
    return serializar_historico(auditoria.historico_do_item("cobranca", cobranca.id))


@dataclass(frozen=True)
class DadosRegistroHistorico:
    acao: str
    ator: PessoaInfo | None
    justificativa: str
    criado_em: datetime


@dataclass(frozen=True)
class ResumoEntradasValidadas:
    quantidade: int
    total: Decimal


def resumo_entradas_validadas(
    *,
    de: date | None = None,
    ate: date | None = None,
    categoria_id: uuid.UUID | None = None,
) -> ResumoEntradasValidadas:
    """Consolida quantidade e total apenas de entradas validadas no intervalo."""
    qs = Entrada.objects.filter(situacao=SituacaoEntrada.VALIDADA.value)
    if de:
        qs = qs.filter(data__gte=de)
    if ate:
        qs = qs.filter(data__lte=ate)
    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)
    agg = qs.aggregate(quantidade=Count("id"), total=Sum("valor"))
    return ResumoEntradasValidadas(
        quantidade=agg["quantidade"] or 0,
        total=agg["total"] or Decimal("0.00"),
    )


@dataclass(frozen=True)
class VisaoDoCaixa:
    """Consolidação financeira para decisão e painel (RF-127, CA-03, CA-32)."""

    total_entradas_validadas: Decimal
    total_saidas_liquidadas: Decimal
    total_comprometido: Decimal


def visao_do_caixa() -> VisaoDoCaixa:
    """Entradas validadas (sem duplicar devoluções), saídas realizadas e comprometido ativo."""
    entradas_total = Entrada.objects.filter(
        situacao=SituacaoEntrada.VALIDADA.value, saida__isnull=True
    ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    liquidadas = Saida.objects.filter(situacao=SituacaoSaida.LIQUIDADA.value).prefetch_related(
        "envios", "devolucoes"
    )
    saidas_total = Decimal("0.00")
    for s in liquidadas:
        env = sum((e.valor for e in s.envios.all()), Decimal("0.00"))
        dev = sum(
            (d.valor for d in s.devolucoes.all() if d.situacao == SituacaoEntrada.VALIDADA.value),
            Decimal("0.00"),
        )
        saidas_total += calcular_valor_realizado_saida(env, dev)

    ativas = Saida.objects.filter(
        situacao__in=[sit.value for sit in SITUACOES_ATIVAS_SAIDA]
    ).prefetch_related("complementos", "devolucoes")
    comprometido = Decimal("0.00")
    for s in ativas:
        comp = sum(
            (c.valor for c in s.complementos.all() if c.situacao == SituacaoComplemento.APROVADO),
            Decimal("0.00"),
        )
        dev = sum(
            (d.valor for d in s.devolucoes.all() if d.situacao == SituacaoEntrada.VALIDADA.value),
            Decimal("0.00"),
        )
        saldo_comp = (s.valor_aprovado + comp) - dev
        if saldo_comp > Decimal("0.00"):
            comprometido += saldo_comp

    return VisaoDoCaixa(
        total_entradas_validadas=entradas_total,
        total_saidas_liquidadas=saidas_total,
        total_comprometido=comprometido,
    )


def obter_visao_do_caixa(ator_id: uuid.UUID) -> VisaoDoCaixa:
    exigir_leitura_gestao(ator_id)
    return visao_do_caixa()


def _em_atraso(saida: Saida, hoje: date) -> bool:
    primeiro = timezone.localdate(saida.primeiro_envio_em) if saida.primeiro_envio_em else None
    return prestacao_em_atraso(
        situacao=SituacaoSaida(saida.situacao),
        primeiro_envio_em=primeiro,
        hoje=hoje,
    )


def _serializar_saida_item(saida: Saida, cache: dict[uuid.UUID, PessoaInfo], *, hoje: date) -> dict[str, Any]:
    prest = saida.prestacao_vigente()
    return {
        "id": saida.id,
        "solicitacao_id": saida.solicitacao_id,
        "versao_aprovada": saida.versao_aprovada,
        "solicitante": _pessoa_dict(saida.solicitante_id, cache),
        "categoria_id": saida.categoria_id,
        "categoria_nome": saida.categoria_nome,
        "setor_id": saida.setor_id,
        "setor_nome": saida.setor_nome,
        "evento_id": saida.evento_id,
        "descricao": saida.descricao,
        "valor_aprovado": saida.valor_aprovado,
        "valor_aprovado_total": saida.valor_aprovado_total(),
        "total_enviado": saida.total_enviado(),
        "total_gasto": prest.valor if prest is not None else None,
        "total_devolvido_validado": saida.total_devolvido_validado(),
        "total_devolvido_pendente": saida.total_devolvido_pendente(),
        "valor_nao_reembolsado": saida.valor_nao_reembolsado,
        "situacao": saida.situacao,
        "em_atraso": _em_atraso(saida, hoje),
        "tem_complemento_aprovado_para_enviar": saida.complemento_aprovado_pendente_envio() is not None,
        "tem_complemento_em_andamento": saida.complemento_em_andamento() is not None,
        "primeiro_envio_em": saida.primeiro_envio_em,
        "criada_em": saida.criada_em,
        "atualizada_em": saida.atualizada_em,
    }


def serializar_detalhe_saida(saida: Saida, *, ator_id: uuid.UUID) -> dict[str, Any]:
    usuario = exigir_leitura_gestao(ator_id)
    hoje = timezone.localdate()
    cache: dict[uuid.UUID, PessoaInfo] = {}
    base = _serializar_saida_item(saida, cache, hoje=hoje)
    pode_anexo = pode_ver_anexos_saida(ator_le_gestao=permissoes.le_gestao(ator_id), ator_admin=usuario.admin)
    pode_val_ent = permissao_ou_admin(usuario, PERM_ENTRADAS_VALIDAR)

    itens: list[dict[str, Any]] = []
    try:
        sol_info = aprovacoes.obter_solicitacao(saida.solicitacao_id)
        itens = list(sol_info.conteudo.get("itens", []))
    except BusinessError:
        itens = []

    return {
        **base,
        "itens": itens,
        "liquidacao_justificativa": saida.liquidacao_justificativa,
        "liquidada_por": _pessoa_dict(saida.liquidada_por_id, cache) if saida.liquidada_por_id else None,
        "liquidada_em": saida.liquidada_em,
        "cancelada_em": saida.cancelada_em,
        "cotacao": (
            {
                "id": saida.cotacao.id,
                "nome": saida.cotacao.nome,
                "disponivel": pode_anexo,
            }
            if saida.cotacao is not None
            else None
        ),
        "envios": [
            {
                "id": e.id,
                "valor": e.valor,
                "complemento_id": e.complemento_id,
                "enviado_por": _pessoa_dict(e.enviado_por_id, cache),
                "enviado_em": e.enviado_em,
                "comprovante_disponivel": bool(e.comprovante_chave) and pode_anexo,
                "comprovante_nome": e.comprovante_nome if pode_anexo else "",
            }
            for e in saida.envios.all()
        ],
        "prestacoes": [
            {
                "id": p.id,
                "valor": p.valor,
                "descricao": p.descricao,
                "registrada_por": _pessoa_dict(p.registrada_por_id, cache),
                "registrada_em": p.registrada_em,
                "situacao": p.situacao,
                "comprovante_disponivel": bool(p.comprovante_chave) and pode_anexo,
                "comprovante_nome": p.comprovante_nome if pode_anexo else "",
                "devolvida_por": _pessoa_dict(p.devolvida_por_id, cache) if p.devolvida_por_id else None,
                "motivo_devolucao_texto": p.motivo_devolucao_texto,
                "texto_devolucao": p.texto_devolucao,
                "devolvida_em": p.devolvida_em,
            }
            for p in saida.prestacoes.all()
        ],
        "devolucoes": [
            {
                "id": d.id,
                "valor": d.valor,
                "data": d.data,
                "origem": d.origem,
                "evidencia_texto": d.evidencia_texto,
                "situacao": d.situacao,
                "registrada_por": _pessoa_dict(d.registrada_por_id, cache),
                "registrada_em": d.registrada_em,
                "decidido_por": _pessoa_dict(d.decidido_por_id, cache) if d.decidido_por_id else None,
                "motivo_texto": d.motivo_texto,
                "decisao_texto": d.decisao_texto,
                "decidido_em": d.decidido_em,
                "comprovante_disponivel": bool(d.comprovante_chave)
                and pode_ver_comprovante_entrada(
                    ator_id=ator_id,
                    ator_admin=usuario.admin,
                    tem_permissao_validar=pode_val_ent,
                    registrada_por_id=d.registrada_por_id,
                ),
                "comprovante_nome": (
                    d.comprovante_nome
                    if pode_ver_comprovante_entrada(
                        ator_id=ator_id,
                        ator_admin=usuario.admin,
                        tem_permissao_validar=pode_val_ent,
                        registrada_por_id=d.registrada_por_id,
                    )
                    else ""
                ),
            }
            for d in saida.devolucoes.all()
        ],
        "complementos": [_serializar_complemento(c) for c in saida.complementos.all()],
        "estorno": serializar_estorno_resumo(saida, cache),
        "acoes": acoes_saida_disponiveis(fatos_saida(saida, ator_id)),
    }


def _serializar_complemento(comp: Complemento) -> dict[str, Any]:
    envio_obj: Envio | None = getattr(comp, "envio", None)
    return {
        "id": comp.id,
        "solicitacao_id": comp.solicitacao_id,
        "valor": comp.valor,
        "situacao": comp.situacao,
        "aprovado_em": comp.aprovado_em,
        "decidido_em": comp.decidido_em,
        "criado_em": comp.criado_em,
        "envio_id": envio_obj.id if envio_obj is not None else None,
    }


def listar_saidas(
    ator_id: uuid.UUID,
    *,
    situacao: str | None = None,
    categoria_id: uuid.UUID | None = None,
    setor_id: uuid.UUID | None = None,
    solicitante_id: uuid.UUID | None = None,
    evento_id: uuid.UUID | None = None,
    de: date | None = None,
    ate: date | None = None,
    pendentes_envio: bool = False,
    pendentes_prestacao: bool = False,
    atrasadas: bool = False,
    antes: uuid.UUID | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista saídas com paginação por cursor e filtros das filas operacionais (CA-30, CA-31)."""
    exigir_leitura_gestao(ator_id)
    hoje = timezone.localdate()
    qs = Saida.objects.select_related("cotacao").all()
    if situacao:
        qs = qs.filter(situacao=situacao)
    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)
    if setor_id:
        qs = qs.filter(setor_id=setor_id)
    if solicitante_id:
        qs = qs.filter(solicitante_id=solicitante_id)
    if evento_id:
        qs = qs.filter(evento_id=evento_id)
    if de:
        qs = qs.filter(criada_em__date__gte=de)
    if ate:
        qs = qs.filter(criada_em__date__lte=ate)
    if pendentes_envio:
        qs = qs.filter(
            Q(situacao=SituacaoSaida.AGUARDANDO_ENVIO.value)
            | Q(
                situacao__in=[SituacaoSaida.RECURSO_ENVIADO.value, SituacaoSaida.EM_CONFERENCIA.value],
                complementos__situacao=SituacaoComplemento.APROVADO,
                complementos__envio__isnull=True,
            )
        ).distinct()
    if pendentes_prestacao:
        qs = qs.filter(situacao=SituacaoSaida.RECURSO_ENVIADO.value)
    if atrasadas:
        limite_atraso = hoje - timedelta(days=PRAZO_VENCIMENTO_PRESTACAO_DIAS)
        qs = qs.filter(
            situacao=SituacaoSaida.RECURSO_ENVIADO.value,
            primeiro_envio_em__isnull=False,
            primeiro_envio_em__date__lte=limite_atraso,
        )
    if antes is not None:
        ancora = Saida.objects.filter(pk=antes).values("criada_em", "id").first()
        if ancora is None:
            raise erro("NOT_FOUND")
        qs = qs.exclude(pk=antes).filter(criada_em__lte=ancora["criada_em"])
        qs = qs.exclude(criada_em=ancora["criada_em"], id__gte=ancora["id"])

    itens_bd = list(qs[: limite + 1])
    tem_mais = len(itens_bd) > limite
    cache: dict[uuid.UUID, PessoaInfo] = {}
    return {
        "itens": [_serializar_saida_item(s, cache, hoje=hoje) for s in itens_bd[:limite]],
        "tem_mais": tem_mais,
    }


def detalhe_saida(ator_id: uuid.UUID, saida_id: uuid.UUID) -> dict[str, Any]:
    exigir_leitura_gestao(ator_id)
    saida = Saida.objects.select_related("cotacao").filter(pk=saida_id).first()
    if saida is None:
        raise erro("NOT_FOUND")
    return serializar_detalhe_saida(saida, ator_id=ator_id)


def historico_saida(ator_id: uuid.UUID, saida_id: uuid.UUID) -> list[dict[str, Any]]:
    exigir_leitura_gestao(ator_id)
    if not Saida.objects.filter(pk=saida_id).exists():
        raise erro("NOT_FOUND")
    return serializar_historico(auditoria.historico_do_item("saida", saida_id))
