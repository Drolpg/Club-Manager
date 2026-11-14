"""Consultas e leitura do módulo financeiro (isolamento de escopo, filtros e detalhe)."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from acesso import public as acesso
from auditoria import public as auditoria
from financeiro.domain.autorizacao import (
    PERM_PAGAMENTOS_VALIDAR,
    acoes_cobranca_disponiveis,
    pode_ver_comprovante_cobranca,
)
from financeiro.domain.qrcode_svg import gerar_qrcode_svg
from financeiro.erros import erro
from financeiro.models import Cobranca, Pagamento
from financeiro.services.autorizacao import (
    exigir_diretor_ativo,
    exigir_leitura_gestao,
    fatos_cobranca,
    permissao_ou_admin,
)


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


def _pessoa_dict(usuario_id: uuid.UUID, cache: dict[uuid.UUID, PessoaInfo]) -> dict[str, Any]:
    p = _pessoa(usuario_id, cache)
    return {"id": p.id, "nome": p.nome}


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
        "acoes": acoes_cobranca_disponiveis(fatos),
    }


def _paginar(qs: Any, *, antes: uuid.UUID | None, limite: int) -> PaginaDeCobrancas:
    if antes is not None:
        ancora = Cobranca.objects.filter(pk=antes).values("criada_em", "id").first()
        if ancora is None:
            raise erro("NOT_FOUND")
        qs = qs.exclude(pk=antes).filter(criada_em__lte=ancora["criada_em"])
        qs = qs.exclude(criada_em=ancora["criada_em"], id__gte=ancora["id"])
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
