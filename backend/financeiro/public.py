"""API pública do módulo `financeiro`.

É o único arquivo deste módulo que outros módulos podem importar (docs/sdd/02-plan.md):
- `obter_categoria_ativa` / `listar_categorias_ativas`: consulta de categorias sem expor ORM.
- `registrar_devolucao_de_saida`: registra devolução de saída de eventos (`TipoEntrada.DEVOLUCAO`).
- `resumo_entradas_validadas`: soma consolidada apenas das entradas com situação `VALIDADA`.
- `abrir_solicitacao_orcamentaria` e `cancelar_orcamento_de_evento`: o orçamento de evento (adendo 1 do M7).
- `cobrancas_do_devedor`: as cobranças de um devedor, com os pagamentos e sem comprovante, para o perfil.
- `totais_do_periodo`, `saldo_acumulado` e `primeira_data_de_realizacao`: o realizado de um período, só
  leitura (N1 a N8 da spec `relatorios/dashboard-e-lancamentos`), para o dashboard e os relatórios.
- `a_receber`, `resumo_da_inadimplencia`, `pendencias_de_validacao`, `prestacoes_pendentes` e
  `resumo_do_devedor`: as pendências e os resumos de hoje (N11 a N13, N15), só leitura.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db import transaction

from auditoria import public as auditoria
from financeiro.erros import erro
from financeiro.models import CategoriaFinanceira, Entrada, Saida, TipoEntrada
from financeiro.services import avisos, orcamentos
from financeiro.services.consulta import (
    CobrancaDoDevedor,
    PagamentoDoDevedor,
    PaginaDeCobrancasDoDevedor,
    ResumoEntradasValidadas,
    VisaoDoCaixa,
    cobrancas_do_devedor,
    resumo_entradas_validadas,
    visao_do_caixa,
)
from financeiro.services.totais import (
    PendenciasDeValidacao,
    PrestacoesPendentes,
    ProximaCobranca,
    Resumo,
    ResumoDaInadimplencia,
    ResumoDoDevedor,
    TotaisDoPeriodo,
    a_receber,
    pendencias_de_validacao,
    prestacoes_pendentes,
    primeira_data_de_realizacao,
    resumo_da_inadimplencia,
    resumo_do_devedor,
    saldo_acumulado,
    totais_do_periodo,
)
from financeiro.tipos import OrcamentoDeEventoMudou
from kernel.dinheiro import Dinheiro


@dataclass(frozen=True)
class CategoriaFinanceiraInfo:
    id: uuid.UUID
    nome: str
    natureza: str
    ativa: bool


def _para_info(categoria: CategoriaFinanceira) -> CategoriaFinanceiraInfo:
    return CategoriaFinanceiraInfo(
        id=categoria.id,
        nome=categoria.nome,
        natureza=categoria.natureza,
        ativa=categoria.ativa,
    )


def obter_categoria_ativa(
    categoria_id: uuid.UUID,
    *,
    natureza: str | None = None,
) -> CategoriaFinanceiraInfo:
    """Obtém uma categoria ativa; opcionalmente exige uma natureza (`ENTRADA` ou `SAIDA`)."""
    categoria = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND")
    if not categoria.ativa or (natureza is not None and categoria.natureza != natureza):
        raise erro("CATEGORIA_INATIVA")
    return _para_info(categoria)


def listar_categorias_ativas(*, natureza: str | None = None) -> list[CategoriaFinanceiraInfo]:
    """Lista categorias financeiras ativas, podendo filtrar por natureza."""
    qs = CategoriaFinanceira.objects.filter(ativa=True)
    if natureza is not None:
        qs = qs.filter(natureza=natureza)
    return [_para_info(c) for c in qs]


@transaction.atomic
def registrar_devolucao_de_saida(
    *,
    categoria_id: uuid.UUID,
    valor: Dinheiro,
    data: date,
    origem: str,
    referencia: str,
    registrada_por_id: uuid.UUID,
    saida_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Registra uma devolução financeira vinda de saída aguardando validação."""
    categoria = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND")
    saida: Saida | None = None
    if saida_id is not None:
        saida = Saida.objects.select_for_update().filter(pk=saida_id).first()
        if saida is None:
            raise erro("NOT_FOUND")
    entrada = Entrada.registrar(
        categoria=categoria,
        valor=valor,
        data=data,
        origem=origem,
        evidencia_texto=referencia,
        anexo=None,
        registrada_por_id=registrada_por_id,
        tipo=TipoEntrada.DEVOLUCAO,
        saida=saida,
    )
    dados_auditoria: dict[str, Any] = {
        "categoria_id": str(categoria.id),
        "valor": str(entrada.valor),
        "data": entrada.data.isoformat(),
        "origem": entrada.origem,
        "tipo": entrada.tipo,
    }
    if saida is not None:
        dados_auditoria["saida_id"] = str(saida.id)
    auditoria.registrar(
        ator_id=registrada_por_id,
        acao="ENTRADA_REGISTRADA",
        item_tipo="entrada",
        item_id=entrada.id,
        dados=dados_auditoria,
    )
    avisos.entrada_registrada(entrada)
    return entrada.id


def abrir_solicitacao_orcamentaria(
    *,
    solicitante_id: uuid.UUID,
    descricao: str,
    categoria_id: uuid.UUID,
    setor_id: uuid.UUID,
    itens: list[dict[str, Any]],
    evento_id: uuid.UUID,
    aprovador_indicado_id: uuid.UUID | None = None,
    cotacao_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Abre a solicitação de gasto do orçamento de um evento, com o vínculo, e devolve o ID dela.

    O vínculo é o registro `OrcamentoDeEvento`, e não o conteúdo (adendo 1). Quem pode abrir o orçamento é
    conferido por `eventos` antes de chamar.
    """
    return orcamentos.abrir(
        solicitante_id=solicitante_id,
        descricao=descricao,
        categoria_id=categoria_id,
        setor_id=setor_id,
        itens=itens,
        evento_id=evento_id,
        aprovador_indicado_id=aprovador_indicado_id,
        cotacao_id=cotacao_id,
    )


def cancelar_orcamento_de_evento(
    solicitacao_id: uuid.UUID,
    *,
    evento_id: uuid.UUID,
    titulo_do_evento: str,
    ator_id: uuid.UUID | None,
    motivo: str,
) -> None:
    """Chamada por `eventos` ao cancelar o evento (adendo 1). Em análise, contestado, retirado, recusado ou
    aprovado sem envio: cancela a solicitação (e a saída que aguardava envio). Com o recurso enviado: não
    cancela nada e avisa quem liquida. Já cancelado: nada. Vínculo de outro evento: `ValueError`.
    """
    orcamentos.cancelar_com_o_evento(
        solicitacao_id, evento_id=evento_id, titulo_do_evento=titulo_do_evento, ator_id=ator_id, motivo=motivo
    )


__all__ = (
    "CategoriaFinanceiraInfo",
    "CobrancaDoDevedor",
    "OrcamentoDeEventoMudou",
    "PagamentoDoDevedor",
    "PaginaDeCobrancasDoDevedor",
    "PendenciasDeValidacao",
    "PrestacoesPendentes",
    "ProximaCobranca",
    "Resumo",
    "ResumoDaInadimplencia",
    "ResumoDoDevedor",
    "ResumoEntradasValidadas",
    "TotaisDoPeriodo",
    "VisaoDoCaixa",
    "a_receber",
    "abrir_solicitacao_orcamentaria",
    "cancelar_orcamento_de_evento",
    "cobrancas_do_devedor",
    "listar_categorias_ativas",
    "obter_categoria_ativa",
    "pendencias_de_validacao",
    "prestacoes_pendentes",
    "primeira_data_de_realizacao",
    "registrar_devolucao_de_saida",
    "resumo_da_inadimplencia",
    "resumo_do_devedor",
    "resumo_entradas_validadas",
    "saldo_acumulado",
    "totais_do_periodo",
    "visao_do_caixa",
)
