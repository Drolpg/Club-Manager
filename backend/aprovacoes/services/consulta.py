"""Consultas: tipos, lista, fila, detalhe e histórico (RF-043, RF-044, RF-122; adendo 1, A2 e A9).

Só leitura. Todas exigem a leitura de gestão (regra 18), conferida antes da existência. O campo `acoes` do
detalhe é calculado com as mesmas funções puras que os serviços usam para aceitar ou recusar cada comando.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db.models import F, OuterRef, Q, QuerySet, Subquery

from acesso import public as acesso
from aprovacoes import tipos
from aprovacoes.domain.decisores import acoes_disponiveis
from aprovacoes.domain.transicoes import Situacao
from aprovacoes.models import Decisao, Solicitacao, Versao
from aprovacoes.services.autorizacao import exigir_leitura_de_gestao, fatos_de
from kernel.errors import BusinessError
from permissoes import public as permissoes

LIMITE_PADRAO = 20
LIMITE_MAXIMO = 50


@dataclass(frozen=True)
class Pessoa:
    id: uuid.UUID
    nome: str


@dataclass(frozen=True)
class TipoInfo:
    codigo: str
    nome: str
    tem_valor: bool


@dataclass(frozen=True)
class ItemDaLista:
    id: uuid.UUID
    tipo: str
    tipo_nome: str
    situacao: str
    solicitante: Pessoa
    resumo: str
    valor: Decimal | None
    numero_da_versao_atual: int
    aguardando_desde: datetime
    criada_em: datetime
    atualizada_em: datetime


@dataclass(frozen=True)
class Pagina:
    itens: tuple[ItemDaLista, ...]
    tem_mais: bool


@dataclass(frozen=True)
class DecisaoInfo:
    tipo: str
    aprovador: Pessoa
    motivo_id: uuid.UUID
    motivo_texto: str
    texto: str
    mensagem: str
    teto_sugerido: Decimal | None
    aprovacao_propria: bool
    criada_em: datetime


@dataclass(frozen=True)
class VersaoInfo:
    numero: int
    conteudo: dict[str, Any]
    valor: Decimal | None
    resumo: str
    autor: Pessoa
    justificativa: str
    criada_em: datetime
    decisao: DecisaoInfo | None


@dataclass(frozen=True)
class Detalhe:
    id: uuid.UUID
    tipo: str
    tipo_nome: str
    tem_valor: bool
    situacao: str
    solicitante: Pessoa
    aprovador_indicado: Pessoa | None
    numero_da_versao_atual: int
    criada_em: datetime
    atualizada_em: datetime
    versoes: tuple[VersaoInfo, ...]
    acoes: tuple[str, ...]


class _Nomes:
    """Os nomes dos usuários de uma resposta, uma consulta por pessoa no máximo."""

    def __init__(self) -> None:
        self._nomes: dict[uuid.UUID, str] = {}

    def pessoa(self, usuario_id: uuid.UUID) -> Pessoa:
        if usuario_id not in self._nomes:
            usuario = acesso.usuario_por_id(usuario_id)
            self._nomes[usuario_id] = usuario.nome if usuario else ""
        return Pessoa(usuario_id, self._nomes[usuario_id])


def _invalido(campo: str, mensagem: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details={campo: [mensagem]}
    )


def _nome_do_tipo(codigo: str) -> str:
    definicao = tipos.obter_tipo(codigo)
    return definicao.nome if definicao else codigo


def _com_a_versao_atual(consulta: QuerySet[Solicitacao]) -> QuerySet[Solicitacao]:
    atual = Versao.objects.filter(solicitacao=OuterRef("pk"), numero=OuterRef("numero_da_versao_atual"))
    return consulta.annotate(
        resumo=Subquery(atual.values("resumo")[:1]),
        valor=Subquery(atual.values("valor")[:1]),
        aguardando_desde=Subquery(atual.values("criada_em")[:1]),
    )


def _item(solicitacao: Any, nomes: _Nomes) -> ItemDaLista:
    return ItemDaLista(
        id=solicitacao.id,
        tipo=solicitacao.tipo,
        tipo_nome=_nome_do_tipo(solicitacao.tipo),
        situacao=solicitacao.situacao,
        solicitante=nomes.pessoa(solicitacao.solicitante_id),
        resumo=solicitacao.resumo,
        valor=solicitacao.valor,
        numero_da_versao_atual=solicitacao.numero_da_versao_atual,
        aguardando_desde=solicitacao.aguardando_desde,
        criada_em=solicitacao.criada_em,
        atualizada_em=solicitacao.atualizada_em,
    )


def listar_tipos(ator_id: uuid.UUID) -> list[TipoInfo]:
    exigir_leitura_de_gestao(ator_id)
    return [TipoInfo(t.codigo, t.nome, t.tem_valor) for t in tipos.listar_tipos()]


def listar(
    ator_id: uuid.UUID,
    *,
    tipo: str | None = None,
    situacao: str | None = None,
    minhas: bool = False,
    antes: uuid.UUID | None = None,
    limite: int = LIMITE_PADRAO,
) -> Pagina:
    """Todas as solicitações, da mais recente para a mais antiga (A9), com os filtros da RF-122."""
    exigir_leitura_de_gestao(ator_id)
    consulta = Solicitacao.objects.all()
    if tipo:
        consulta = consulta.filter(tipo=tipo)
    if situacao:
        consulta = consulta.filter(situacao=situacao)
    if minhas:
        consulta = consulta.filter(solicitante_id=ator_id)
    if antes is not None:
        if not Solicitacao.objects.filter(pk=antes).exists():
            raise _invalido("antes", "Solicitação não encontrada.")
        # O ID é UUID 7: a ordem dele é a ordem de criação.
        consulta = consulta.filter(id__lt=antes)
    achadas = list(_com_a_versao_atual(consulta).order_by("-id")[: limite + 1])
    nomes = _Nomes()
    return Pagina(itens=tuple(_item(s, nomes) for s in achadas[:limite]), tem_mais=len(achadas) > limite)


def fila(ator_id: uuid.UUID) -> list[ItemDaLista]:
    """As em análise que o ator pode decidir, da que espera há mais tempo, contando da versão atual (A9).

    É a mesma regra de `pode_decidir`, em forma de consulta: os tipos que o ator aprova, ou as solicitações em
    que é o indicado; o próprio pedido só com a auto-aprovação e a permissão de aprovar o tipo (adendo 1, A2).
    """
    exigir_leitura_de_gestao(ator_id)
    do_ator = permissoes.permissoes_de(ator_id)
    aprova = [t.codigo for t in tipos.listar_tipos() if t.permissao_de_aprovar in do_ator]
    consulta = Solicitacao.objects.filter(situacao=Situacao.EM_ANALISE).filter(
        Q(tipo__in=aprova) | Q(aprovador_indicado_id=ator_id)
    )
    if tipos.AUTO_APROVAR in do_ator:
        consulta = consulta.exclude(Q(solicitante_id=ator_id) & ~Q(tipo__in=aprova))
    else:
        consulta = consulta.exclude(solicitante_id=ator_id)
    nomes = _Nomes()
    ordem = (F("aguardando_desde").asc(), F("id").asc())
    return [_item(s, nomes) for s in _com_a_versao_atual(consulta).order_by(*ordem)]


def _buscar(ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Solicitacao:
    exigir_leitura_de_gestao(ator_id)
    solicitacao = Solicitacao.objects.filter(pk=solicitacao_id).first()
    if solicitacao is None:
        raise BusinessError("NOT_FOUND", "Solicitação não encontrada.", status=404)
    return solicitacao


def _decisao(versao: Versao, nomes: _Nomes) -> DecisaoInfo | None:
    decisao: Decisao | None = getattr(versao, "decisao", None)
    if decisao is None:
        return None
    return DecisaoInfo(
        tipo=decisao.tipo,
        aprovador=nomes.pessoa(decisao.aprovador_id),
        motivo_id=decisao.motivo_id,
        motivo_texto=decisao.motivo_texto,
        texto=decisao.texto,
        mensagem=decisao.mensagem,
        teto_sugerido=decisao.teto_sugerido,
        aprovacao_propria=decisao.aprovacao_propria,
        criada_em=decisao.criada_em,
    )


def detalhe(ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Detalhe:
    """Todas as versões com o conteúdo, as decisões, a indicação e o que o ator pode fazer agora (CA-28)."""
    solicitacao = _buscar(ator_id, solicitacao_id)
    nomes = _Nomes()
    definicao = tipos.obter_tipo(solicitacao.tipo)
    versoes = solicitacao.versoes.select_related("decisao").order_by("numero")
    indicado = solicitacao.aprovador_indicado_id
    return Detalhe(
        id=solicitacao.id,
        tipo=solicitacao.tipo,
        tipo_nome=_nome_do_tipo(solicitacao.tipo),
        tem_valor=definicao.tem_valor if definicao else False,
        situacao=solicitacao.situacao,
        solicitante=nomes.pessoa(solicitacao.solicitante_id),
        aprovador_indicado=nomes.pessoa(indicado) if indicado else None,
        numero_da_versao_atual=solicitacao.numero_da_versao_atual,
        criada_em=solicitacao.criada_em,
        atualizada_em=solicitacao.atualizada_em,
        versoes=tuple(
            VersaoInfo(
                numero=v.numero,
                conteudo=v.conteudo,
                valor=v.valor,
                resumo=v.resumo,
                autor=nomes.pessoa(v.autor_id),
                justificativa=v.justificativa,
                criada_em=v.criada_em,
                decisao=_decisao(v, nomes),
            )
            for v in versoes
        ),
        # Sem o tipo registrado, nenhum comando funcionaria: nenhuma ação é oferecida.
        acoes=tuple(c.value.lower() for c in acoes_disponiveis(fatos_de(solicitacao, ator_id)))
        if definicao
        else (),
    )


def historico(ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> list[acesso.RegistroDoHistorico]:
    """O histórico da auditoria, do mais recente para o mais antigo, com o nome de quem agiu."""
    solicitacao = _buscar(ator_id, solicitacao_id)
    return acesso.historico_com_nomes("solicitacao", solicitacao.id)
