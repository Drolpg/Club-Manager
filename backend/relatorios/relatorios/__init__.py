"""Os sete tipos de relatório, registrados no catálogo ao iniciar (P22).

Os seis do clube são de quem lê os dados de gestão; "Meus dados" é de todo usuário ativo, só dos próprios.
"""

from relatorios import tipos
from relatorios.domain import parametros
from relatorios.domain.pedido import Formato
from relatorios.relatorios import (
    balancete,
    comum,
    eventos,
    extrato,
    fluxo_de_caixa,
    inadimplencia,
    meus_dados,
    prestacao_de_contas,
)

_PDF_E_CSV = (Formato.PDF, Formato.CSV)

TIPOS = (
    tipos.TipoDeRelatorio(
        "EXTRATO", "Extrato", _PDF_E_CSV, comum.le_gestao, parametros.periodo, extrato.extrato
    ),
    tipos.TipoDeRelatorio(
        "BALANCETE", "Balancete", _PDF_E_CSV, comum.le_gestao, parametros.periodo, balancete.balancete
    ),
    tipos.TipoDeRelatorio(
        "INADIMPLENCIA",
        "Inadimplência",
        _PDF_E_CSV,
        comum.le_gestao,
        parametros.nenhum,
        inadimplencia.inadimplencia,
    ),
    tipos.TipoDeRelatorio(
        "EVENTOS", "Eventos", _PDF_E_CSV, comum.le_gestao, parametros.periodo, eventos.eventos_do_periodo
    ),
    tipos.TipoDeRelatorio(
        "PRESTACAO_DE_CONTAS",
        "Prestação de contas",
        _PDF_E_CSV,
        comum.le_gestao,
        parametros.periodo_com_pendentes,
        prestacao_de_contas.prestacao_de_contas,
    ),
    tipos.TipoDeRelatorio(
        "FLUXO_DE_CAIXA",
        "Fluxo de caixa",
        _PDF_E_CSV,
        comum.le_gestao,
        parametros.meses,
        fluxo_de_caixa.fluxo_de_caixa,
    ),
    tipos.TipoDeRelatorio(
        "MEUS_DADOS", "Meus dados", (Formato.CSV,), comum.ativo, parametros.nenhum, meus_dados.meus_dados
    ),
)


def registrar_todos() -> None:
    for tipo in TIPOS:
        tipos.registrar_tipo_de_relatorio(tipo)
