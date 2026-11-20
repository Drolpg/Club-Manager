"""Os casos de uso do evento. Cada um abre a transação, confere quem age com `domain/autorizacao.avaliar`,
bloqueia o evento, chama o método do aggregate, audita e notifica na mesma transação.
"""

import uuid
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from eventos import tipos
from eventos.domain.autorizacao import avaliar
from eventos.domain.regras import DadosInvalidos, validar_proposta
from eventos.domain.transicoes import ComandoDoEvento
from eventos.erros import erro, invalido
from eventos.models import CategoriaDeEvento, Evento
from eventos.services import situacao
from eventos.services.autorizacao import exigir, exigir_leitura_de_gestao, fatos
from financeiro import public as financeiro

C = ComandoDoEvento


def _auditar(
    ator_id: uuid.UUID | None, evento: Evento, acao: str, *, justificativa: str = "", **dados: Any
) -> None:
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao,
        item_tipo="evento",
        item_id=evento.id,
        justificativa=justificativa,
        dados=dados,
    )


def bloquear(ator_id: uuid.UUID, evento_id: uuid.UUID) -> Evento:
    """Leitura de gestão (403) antes da existência (404); a linha fica bloqueada até o fim da transação."""
    exigir_leitura_de_gestao(ator_id)
    evento = Evento.objects.select_for_update().filter(pk=evento_id).first()
    if evento is None:
        raise erro("NOT_FOUND", "Evento não encontrado.")
    return evento


def _conteudo(evento: Evento) -> dict[str, Any]:
    """O motor só leva o ID: o retrato é montado pelo `preparar` a partir do evento (fonte dos dados)."""
    return {"evento_id": str(evento.id)}


def _dados_validos(
    *,
    titulo: str,
    descricao: str,
    inicio: datetime,
    local: str,
    categoria_id: uuid.UUID,
    categoria_atual_id: uuid.UUID | None = None,
) -> tuple[Any, CategoriaDeEvento]:
    """Na edição, a categoria atual do evento continua aceita mesmo que tenha sido desativada depois."""
    erros: dict[str, list[str]] = {}
    dados = None
    try:
        dados = validar_proposta(
            titulo=titulo, descricao=descricao, local=local, inicio=inicio, agora=timezone.now()
        )
    except DadosInvalidos as invalidos:
        erros.update(invalidos.erros)
    categoria = CategoriaDeEvento.objects.filter(pk=categoria_id).first()
    if categoria is not None and not categoria.ativa and categoria.id != categoria_atual_id:
        categoria = None
    if categoria is None:
        erros["categoria_id"] = ["Escolha uma categoria de evento ativa."]
    if erros or dados is None or categoria is None:
        raise invalido(erros)
    return dados, categoria


@transaction.atomic
def propor(
    ator_id: uuid.UUID,
    *,
    titulo: str,
    descricao: str,
    inicio: datetime,
    local: str,
    categoria_id: uuid.UUID,
    envolve_custo: bool,
    aprovador_indicado_id: uuid.UUID | None = None,
) -> Evento:
    """RF-085, CA-02, CA-03. O motor avisa quem decide e exige a indicação quando quem propõe aprovaria o
    próprio evento sem auto-aprovação (INV-SOL-10).
    """
    exigir(avaliar(C.PROPOR, fatos(ator_id)))
    dados, categoria = _dados_validos(
        titulo=titulo, descricao=descricao, inicio=inicio, local=local, categoria_id=categoria_id
    )
    evento = Evento.propor(
        dados=dados, categoria=categoria, proponente_id=ator_id, envolve_custo=envolve_custo
    )
    solicitacao_id = aprovacoes.enviar(
        tipo=tipos.TIPO_EVENTO,
        conteudo=_conteudo(evento),
        solicitante_id=ator_id,
        aprovador_indicado_id=aprovador_indicado_id,
    )
    evento.ligar_solicitacao_do_evento(solicitacao_id)
    _auditar(
        ator_id, evento, "EVENTO_PROPOSTO", solicitacao_id=str(solicitacao_id), envolve_custo=envolve_custo
    )
    return evento


@transaction.atomic
def reabrir(ator_id: uuid.UUID, evento_id: uuid.UUID, *, justificativa: str) -> Evento:
    """CA-09: o evento recusado volta à aprovação; o motor reabre a solicitação com a justificativa."""
    evento = bloquear(ator_id, evento_id)
    exigir(avaliar(C.REABRIR, fatos(ator_id, evento)))
    aprovacoes.nova_versao_pelo_dono(
        evento.id_da_solicitacao_do_evento,
        tipo=tipos.TIPO_EVENTO,
        ator_id=ator_id,
        conteudo=_conteudo(evento),
        justificativa=justificativa,
    )
    # O `ao_mudar` do motor já recalculou, noutra instância do mesmo evento: relê antes de seguir.
    evento.refresh_from_db()
    situacao.recalcular(evento, ator_id=ator_id)
    _auditar(ator_id, evento, "EVENTO_REABERTO", justificativa=justificativa.strip())
    return evento


@transaction.atomic
def abrir_orcamento(
    ator_id: uuid.UUID,
    evento_id: uuid.UUID,
    *,
    descricao: str,
    categoria_id: uuid.UUID,
    setor_id: uuid.UUID,
    itens: list[dict[str, Any]],
    cotacao_id: uuid.UUID | None = None,
    aprovador_indicado_id: uuid.UUID | None = None,
) -> Evento:
    """RF-086, CA-06: quem aprova eventos abre o orçamento, uma solicitação de gasto ligada ao evento."""
    evento = bloquear(ator_id, evento_id)
    exigir(avaliar(C.VINCULAR_ORCAMENTO, fatos(ator_id, evento)))
    solicitacao_id = financeiro.abrir_solicitacao_orcamentaria(
        solicitante_id=ator_id,
        descricao=descricao,
        categoria_id=categoria_id,
        setor_id=setor_id,
        itens=itens,
        evento_id=evento.id,
        aprovador_indicado_id=aprovador_indicado_id,
        cotacao_id=cotacao_id,
    )
    evento.refresh_from_db()
    evento.vincular_orcamento(solicitacao_id)
    situacao.recalcular(evento, ator_id=ator_id)
    _auditar(ator_id, evento, "ORCAMENTO_VINCULADO", solicitacao_id=str(solicitacao_id))
    return evento


_CAMPOS_EDITAVEIS = ("titulo", "descricao", "inicio", "local", "categoria_id", "envolve_custo")


@transaction.atomic
def editar(
    ator_id: uuid.UUID,
    evento_id: uuid.UUID,
    *,
    titulo: str,
    descricao: str,
    inicio: datetime,
    local: str,
    categoria_id: uuid.UUID,
    envolve_custo: bool,
    justificativa: str = "",
) -> Evento:
    """RF-089, CA-15 a CA-17. Os dados novos são gravados no evento antes de pedir a versão nova ao motor,
    porque o `preparar` monta o retrato a partir do evento gravado. Mudar a data zera as presenças (P3).
    """
    evento = bloquear(ator_id, evento_id)
    exigir(avaliar(C.EDITAR, fatos(ator_id, evento)))
    dados, categoria = _dados_validos(
        titulo=titulo,
        descricao=descricao,
        inicio=inicio,
        local=local,
        categoria_id=categoria_id,
        categoria_atual_id=evento.categoria_id,
    )
    antes = {campo: getattr(evento, campo) for campo in _CAMPOS_EDITAVEIS}
    data_mudou = evento.editar(dados, categoria=categoria, envolve_custo=envolve_custo)
    campos = [campo for campo in _CAMPOS_EDITAVEIS if getattr(evento, campo) != antes[campo]]
    aprovacoes.nova_versao_pelo_dono(
        evento.id_da_solicitacao_do_evento,
        tipo=tipos.TIPO_EVENTO,
        ator_id=ator_id,
        conteudo=_conteudo(evento),
        justificativa=justificativa,
    )
    # O `ao_mudar` já recalculou (e avisou quem disse que vai) noutra instância: relê antes de seguir.
    evento.refresh_from_db()
    situacao.recalcular(evento, ator_id=ator_id)
    if data_mudou:
        evento.zerar_presencas()
    _auditar(
        ator_id,
        evento,
        "EVENTO_EDITADO",
        justificativa=justificativa.strip(),
        campos=campos,
        data_mudou=data_mudou,
    )
    return evento
