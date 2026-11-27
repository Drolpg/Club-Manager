"""A prestação de contas das saídas com recurso enviado (RF-109)."""

from decimal import Decimal
from typing import Any

from financeiro import public as financeiro
from relatorios.domain.documento import Coluna, Documento, ItemDoResumo, Tabela, TipoDeColuna
from relatorios.relatorios import comum
from relatorios.tipos import Contexto

T = TipoDeColuna
_ZERO = Decimal("0.00")


_COLUNAS_DA_PRESTACAO = (
    Coluna("Solicitante", T.TEXTO),
    Coluna("Setor", T.TEXTO),
    Coluna("Categoria", T.TEXTO),
    Coluna("Descrição", T.TEXTO),
    Coluna("Aprovado", T.DINHEIRO),
    Coluna("Enviado", T.DINHEIRO),
    Coluna("Gasto informado", T.DINHEIRO),
    Coluna("Devolvido validado", T.DINHEIRO),
    Coluna("Não reembolsado", T.DINHEIRO),
    Coluna("Situação", T.TEXTO),
    Coluna("Primeiro envio", T.DATA),
    Coluna("Dias desde o envio", T.INTEIRO),
    Coluna("Em atraso", T.SIM_NAO),
    Coluna("Comprovante", T.SIM_NAO),
)


def prestacao_de_contas(parametros: dict[str, Any], contexto: Contexto) -> list[Documento]:
    """Pelo primeiro envio; o comprovante só como "tem" ou "não tem" (CA-20)."""
    de, ate = comum.periodo(parametros)
    so_pendentes = bool(parametros.get("so_pendentes", False))
    saidas = financeiro.prestacoes_de_contas(de, ate, so_pendentes=so_pendentes, hoje=contexto.hoje)
    texto = comum.texto_do_periodo(de, ate) + (", só pendentes" if so_pendentes else "")
    return [
        Documento(
            titulo="Prestação de contas",
            parametros=texto,
            resumo=(
                ItemDoResumo("Saídas", len(saidas), T.INTEIRO),
                ItemDoResumo("Aprovado", sum((s.aprovado for s in saidas), _ZERO), T.DINHEIRO),
                ItemDoResumo("Enviado", sum((s.enviado for s in saidas), _ZERO), T.DINHEIRO),
                ItemDoResumo("Gasto informado", sum((s.gasto_informado for s in saidas), _ZERO), T.DINHEIRO),
                ItemDoResumo("Devolvido", sum((s.devolvido_validado for s in saidas), _ZERO), T.DINHEIRO),
                ItemDoResumo("Em atraso", sum(1 for s in saidas if s.em_atraso), T.INTEIRO),
            ),
            tabelas=(
                Tabela(
                    "Saídas com recurso enviado",
                    _COLUNAS_DA_PRESTACAO,
                    tuple(
                        (
                            s.solicitante,
                            s.setor,
                            s.categoria,
                            s.descricao,
                            s.aprovado,
                            s.enviado,
                            s.gasto_informado,
                            s.devolvido_validado,
                            s.nao_reembolsado,
                            comum.legivel(s.situacao, comum.SITUACOES_DE_SAIDA),
                            s.primeiro_envio,
                            s.dias_desde_o_envio,
                            s.em_atraso,
                            s.tem_comprovante,
                        )
                        for s in saidas
                    ),
                ),
            ),
        )
    ]
