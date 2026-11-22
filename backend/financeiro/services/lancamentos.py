"""A lista de lançamentos da aba Financeiro (RF-104; P10, P16, D5), só leitura.

Quatro tipos numa consulta só (`UNION ALL`), cada um já filtrado, ordenados por data de referência e ID, do
mais novo para o mais antigo. O cursor é `<tipo>:<uuid>` do último item da página anterior. O estado vem da
tabela pura `estado_comum`; o filtro de estado usa a inversa, para filtrar no banco.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Case, CharField, DateTimeField, F, Q, QuerySet, UUIDField, Value, When
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from acesso import public as acesso
from financeiro.domain.realizado import (
    EstadoDoLancamento,
    TipoDeLancamento,
    estado_comum,
    situacoes_do_estado,
)
from financeiro.domain.transicoes import SituacaoEntrada, SituacaoSaida
from financeiro.erros import erro
from financeiro.models import Cobranca, Entrada, Estorno, Saida
from financeiro.services import totais
from financeiro.services.autorizacao import exigir_leitura_gestao

T = TipoDeLancamento
_TEXTO = CharField()
_ID = UUIDField()
_INSTANTE = DateTimeField()
_COLUNAS = (
    "id",
    "l_tipo",
    "l_subtipo",
    "l_data",
    "l_descricao",
    "l_categoria_id",
    "l_categoria_nome",
    "l_pessoa_id",
    "l_texto",
    "l_valor",
    "l_situacao",
    "l_realizado_em",
    "l_original_tipo",
    "l_original_id",
)


@dataclass(frozen=True)
class Lancamento:
    tipo: str
    subtipo: str | None
    id: uuid.UUID
    data_referencia: date
    descricao: str
    categoria_id: uuid.UUID
    categoria_nome: str
    contraparte: str
    valor: Decimal
    valor_realizado: Decimal | None
    estado: str
    situacao: str
    realizado_em: date | None
    original_tipo: str | None
    original_id: uuid.UUID | None


@dataclass(frozen=True)
class PaginaDeLancamentos:
    itens: list[Lancamento]
    tem_mais: bool


def _nulo(campo: Any) -> Value:
    return Value(None, output_field=campo)


def _cobrancas() -> QuerySet[Any]:
    return Cobranca.objects.annotate(
        l_tipo=Value(T.COBRANCA.value, output_field=_TEXTO),
        l_subtipo=_nulo(_TEXTO),
        l_data=F("vencimento"),
        l_descricao=F("descricao"),
        l_categoria_id=F("categoria_id"),
        l_categoria_nome=F("categoria_nome"),
        l_pessoa_id=F("devedor_id"),
        l_texto=Value("", output_field=_TEXTO),
        l_valor=F("valor"),
        l_situacao=F("situacao"),
        l_realizado_em=F("paga_em"),
        l_original_tipo=_nulo(_TEXTO),
        l_original_id=_nulo(_ID),
    )


def _entradas() -> QuerySet[Any]:
    realizada = Q(situacao__in=(SituacaoEntrada.VALIDADA.value, SituacaoEntrada.ESTORNADA.value))
    return Entrada.objects.annotate(
        l_tipo=Value(T.ENTRADA.value, output_field=_TEXTO),
        l_subtipo=F("tipo"),
        l_data=F("data"),
        l_descricao=F("origem"),
        l_categoria_id=F("categoria_id"),
        l_categoria_nome=F("categoria_nome"),
        l_pessoa_id=_nulo(_ID),
        l_texto=F("origem"),
        l_valor=F("valor"),
        l_situacao=F("situacao"),
        l_realizado_em=Case(When(realizada, then=F("decidido_em")), default=_nulo(_INSTANTE)),
        l_original_tipo=Case(
            When(saida__isnull=False, then=Value(T.SAIDA.value)), default=_nulo(_TEXTO), output_field=_TEXTO
        ),
        l_original_id=F("saida_id"),
    )


def _saidas() -> QuerySet[Any]:
    return Saida.objects.annotate(
        l_tipo=Value(T.SAIDA.value, output_field=_TEXTO),
        l_subtipo=_nulo(_TEXTO),
        l_data=TruncDate("criada_em"),
        l_descricao=F("descricao"),
        l_categoria_id=F("categoria_id"),
        l_categoria_nome=F("categoria_nome"),
        l_pessoa_id=F("solicitante_id"),
        l_texto=F("setor_nome"),
        l_valor=F("valor_aprovado"),
        l_situacao=F("situacao"),
        l_realizado_em=F("liquidada_em"),
        l_original_tipo=_nulo(_TEXTO),
        l_original_id=_nulo(_ID),
    )


def _estornos() -> QuerySet[Any]:
    return Estorno.objects.annotate(
        l_tipo=Value(T.ESTORNO.value, output_field=_TEXTO),
        l_subtipo=F("alvo_tipo"),
        l_data=TruncDate("registrado_em"),
        l_descricao=Coalesce(F("cobranca__descricao"), F("entrada__origem"), F("saida__descricao")),
        l_categoria_id=Coalesce(
            F("cobranca__categoria_id"), F("entrada__categoria_id"), F("saida__categoria_id")
        ),
        l_categoria_nome=Coalesce(
            F("cobranca__categoria_nome"), F("entrada__categoria_nome"), F("saida__categoria_nome")
        ),
        l_pessoa_id=Coalesce(F("cobranca__devedor_id"), F("saida__solicitante_id")),
        l_texto=Coalesce(F("entrada__origem"), F("saida__setor_nome"), Value("", output_field=_TEXTO)),
        l_valor=F("valor"),
        l_situacao=Value("", output_field=_TEXTO),
        l_realizado_em=F("registrado_em"),
        l_original_tipo=F("alvo_tipo"),
        l_original_id=Coalesce(F("cobranca_id"), F("entrada_id"), F("saida_id")),
    )


_CONSULTAS = {T.COBRANCA: _cobrancas, T.ENTRADA: _entradas, T.SAIDA: _saidas, T.ESTORNO: _estornos}


def _filtrada(
    tipo: TipoDeLancamento,
    *,
    de: date | None,
    ate: date | None,
    categoria_id: uuid.UUID | None,
    estado: EstadoDoLancamento | None,
    ancora: dict[str, Any] | None,
) -> QuerySet[Any]:
    qs = _CONSULTAS[tipo]()
    if de is not None:
        qs = qs.filter(l_data__gte=de)
    if ate is not None:
        qs = qs.filter(l_data__lte=ate)
    if categoria_id is not None:
        qs = qs.filter(l_categoria_id=categoria_id)
    if estado is not None:
        situacoes = situacoes_do_estado(tipo, estado)
        if not situacoes:
            qs = qs.none()
        elif tipo != T.ESTORNO:
            qs = qs.filter(situacao__in=situacoes)
    if ancora is not None:
        qs = qs.filter(Q(l_data__lt=ancora["l_data"]) | Q(l_data=ancora["l_data"], id__lt=ancora["id"]))
    return qs.order_by().values(*_COLUNAS)


def _ancora(antes: str | None) -> dict[str, Any] | None:
    """O último item da página anterior, pelo cursor `<tipo>:<uuid>`; inexistente ou ilegível: 404."""
    if antes is None:
        return None
    tipo_texto, _, id_texto = antes.partition(":")
    try:
        tipo, item_id = TipoDeLancamento(tipo_texto), uuid.UUID(id_texto)
    except ValueError:
        raise erro("NOT_FOUND") from None
    ancora: dict[str, Any] | None = _CONSULTAS[tipo]().filter(pk=item_id).values("l_data", "id").first()
    if ancora is None:
        raise erro("NOT_FOUND")
    return ancora


def _contraparte(linha: dict[str, Any], nomes: dict[uuid.UUID, str]) -> str:
    pessoa_id, texto = linha["l_pessoa_id"], linha["l_texto"] or ""
    if pessoa_id is None:
        return texto
    if pessoa_id not in nomes:
        usuario = acesso.usuario_por_id(pessoa_id)
        nomes[pessoa_id] = usuario.nome if usuario else ""
    return f"{nomes[pessoa_id]} — {texto}" if texto else nomes[pessoa_id]


def _lancamento(
    linha: dict[str, Any], nomes: dict[uuid.UUID, str], realizados: dict[uuid.UUID, Decimal]
) -> Lancamento:
    tipo = TipoDeLancamento(linha["l_tipo"])
    estorno = tipo == T.ESTORNO
    realizado_em = linha["l_realizado_em"]
    return Lancamento(
        tipo=tipo.value,
        subtipo=linha["l_subtipo"],
        id=linha["id"],
        data_referencia=linha["l_data"],
        descricao=f"Estorno de: {linha['l_descricao']}" if estorno else linha["l_descricao"],
        categoria_id=linha["l_categoria_id"],
        categoria_nome=linha["l_categoria_nome"],
        contraparte=_contraparte(linha, nomes),
        valor=-linha["l_valor"] if estorno else linha["l_valor"],
        valor_realizado=realizados.get(linha["id"]) if tipo == T.SAIDA else None,
        estado=estado_comum(tipo, linha["l_situacao"]).value,
        situacao=linha["l_situacao"],
        realizado_em=timezone.localdate(realizado_em) if realizado_em else None,
        original_tipo=linha["l_original_tipo"],
        original_id=linha["l_original_id"],
    )


def listar(
    ator_id: uuid.UUID,
    *,
    de: date | None = None,
    ate: date | None = None,
    categoria_id: uuid.UUID | None = None,
    tipo: TipoDeLancamento | None = None,
    estado: EstadoDoLancamento | None = None,
    antes: str | None = None,
    limite: int = 20,
) -> PaginaDeLancamentos:
    """Uma página da lista, mais novos primeiro, para quem lê os dados de gestão (CA-14 a CA-17)."""
    exigir_leitura_gestao(ator_id)
    ancora = _ancora(antes)
    tipos = [tipo] if tipo is not None else list(TipoDeLancamento)
    partes = [
        _filtrada(t, de=de, ate=ate, categoria_id=categoria_id, estado=estado, ancora=ancora) for t in tipos
    ]
    uniao = partes[0].union(*partes[1:], all=True) if len(partes) > 1 else partes[0]
    linhas = list(uniao.order_by("-l_data", "-id")[: limite + 1])
    pagina = linhas[:limite]
    liquidadas = [
        linha["id"]
        for linha in pagina
        if linha["l_tipo"] == T.SAIDA.value
        and linha["l_situacao"] in (SituacaoSaida.LIQUIDADA.value, SituacaoSaida.ESTORNADA.value)
    ]
    realizados = totais.realizado_por_saida(liquidadas)
    nomes: dict[uuid.UUID, str] = {}
    return PaginaDeLancamentos(
        itens=[_lancamento(linha, nomes, realizados) for linha in pagina], tem_mais=len(linhas) > limite
    )
