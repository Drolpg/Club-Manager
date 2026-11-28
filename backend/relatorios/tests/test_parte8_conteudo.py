"""Parte 8: o conteúdo dos sete relatórios (spec `relatorios/relatorios-pdf-e-csv`, "Os relatórios"; CA-16 a
CA-22, CA-25, CA-27).

Uma massa fixa, montada pelas rotas, com o relógio em 20/11/2026: cobranças pagas, entrada estornada, saída
liquidada, cobrança atrasada com convocação e justificativa, cobrança questionada e saída aguardando
prestação. Os números são comparados com as consultas dos módulos donos e com o dashboard do mesmo mês.
"""

import csv
import io
import uuid
import zipfile
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest

from eventos import public as eventos
from financeiro import public as financeiro
from relatorios import tipos
from relatorios.domain.csv_seguro import formatar_para_leitura
from relatorios.domain.documento import Cabecalho, Documento, TipoDeColuna
from relatorios.domain.parametros import ParametroInvalido
from relatorios.domain.pedido import Formato
from relatorios.escritores.csv import escrever_csv
from relatorios.escritores.pdf import escrever_pdf
from relatorios.services import dashboard, geracao
from relatorios.tests.apoio_conteudo import (
    AGORA,
    HOJE,
    OUT,
    SEGREDO_DA_JUSTIFICATIVA,
    SEGREDO_DO_QUESTIONAMENTO,
    Massa,
    coluna,
    relogio_fixo,
    resumo,
    tabela,
    texto_do_pdf,
)
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

ZERO = Decimal("0.00")
CLUBE = ("EXTRATO", "BALANCETE", "INADIMPLENCIA", "EVENTOS", "PRESTACAO_DE_CONTAS", "FLUXO_DE_CAIXA")
CABECALHO = Cabecalho(gerado_em=AGORA, gerado_por="Quem pediu")


@pytest.fixture(autouse=True)
def _relogio() -> Iterator[None]:
    with relogio_fixo():
        yield


@pytest.fixture
def massa(db: None) -> Massa:
    return Massa()


def _montar(codigo: str, parametros: dict[str, Any], usuario: Usuario) -> list[Documento]:
    tipo = tipos.obter(codigo)
    assert tipo is not None
    normalizados = tipo.validar_parametros(parametros, HOJE)
    return tipo.montar(normalizados, tipos.Contexto(hoje=HOJE, agora=AGORA, usuario_id=usuario.id))


def _um(codigo: str, parametros: dict[str, Any], usuario: Usuario) -> Documento:
    [documento] = _montar(codigo, parametros, usuario)
    return documento


# O catálogo ----------------------------------------------------------------------------------------------


def test_os_sete_tipos_estao_registrados_com_os_formatos() -> None:
    for codigo in CLUBE:
        tipo = tipos.obter(codigo)
        assert tipo is not None, codigo
        assert [f.value for f in tipo.formatos] == ["PDF", "CSV"]
    meus_dados = tipos.obter("MEUS_DADOS")
    assert meus_dados is not None
    assert [f.value for f in meus_dados.formatos] == ["CSV"]


def test_quem_pode_gerar_cada_tipo(admin: Usuario) -> None:
    gestor = apoio.criar_diretor("gestor.conteudo")
    apoio.dar_cargo(gestor)
    sem_cargo = apoio.criar_diretor("sem.cargo.conteudo")

    assert [t.codigo for t in tipos.disponiveis_para(sem_cargo.id)] == ["MEUS_DADOS"]
    for usuario in (gestor, admin):
        assert {t.codigo for t in tipos.disponiveis_para(usuario.id)} >= {*CLUBE, "MEUS_DADOS"}


# Extrato (CA-16) -----------------------------------------------------------------------------------------


def test_ca16_extrato_do_mes_bate_com_os_totais_e_com_o_dashboard(massa: Massa) -> None:
    extrato = _um("EXTRATO", {"mes": "2026-10"}, massa.fin)

    numeros = resumo(extrato)
    totais = financeiro.totais_do_periodo(date(2026, 10, 1), date(2026, 10, 31))
    painel = dashboard.dashboard(massa.fin.id, "2026-10")
    assert isinstance(painel, dashboard.DashboardCompleto)
    assert (numeros["Entradas"], numeros["Saídas"], numeros["Resultado"]) == (
        totais.entradas,
        totais.saidas,
        totais.resultado,
    )
    assert (numeros["Entradas"], numeros["Saídas"], numeros["Resultado"]) == (
        painel.do_mes.entradas,
        painel.do_mes.saidas,
        painel.do_mes.resultado,
    )
    assert numeros["Saldo no fim"] == painel.do_mes.saldo_acumulado
    assert numeros["Saldo no início"] + numeros["Resultado"] == numeros["Saldo no fim"]


def test_ca16_extrato_tem_os_realizados_em_ordem_com_o_estorno_negativo(massa: Massa) -> None:
    lancamentos = tabela(_um("EXTRATO", OUT, massa.fin), "Lançamentos")

    assert coluna(lancamentos, "Tipo") == ["Cobrança", "Entrada", "Saída", "Estorno"]
    assert coluna(lancamentos, "Realizado em") == [
        date(2026, 10, 5),
        date(2026, 10, 6),
        date(2026, 10, 9),
        date(2026, 10, 25),
    ]
    assert coluna(lancamentos, "Valor") == [
        Decimal("100.00"),
        Decimal("1000.00"),
        Decimal("-300.00"),
        Decimal("-1000.00"),
    ]
    assert all(isinstance(d, date) for d in coluna(lancamentos, "Data do fato"))
    assert coluna(lancamentos, "Contraparte")[0] == massa.devedor.nome


# Balancete (CA-17) ---------------------------------------------------------------------------------------


def test_ca17_balancete_fecha_com_o_extrato_e_poe_o_estorno_na_categoria_do_original(massa: Massa) -> None:
    balancete = _um("BALANCETE", OUT, massa.fin)
    extrato = resumo(_um("EXTRATO", OUT, massa.fin))

    entradas = tabela(balancete, "Entradas por categoria")
    por_categoria = dict(zip(coluna(entradas, "Categoria"), coluna(entradas, "Estornos"), strict=True))
    assert por_categoria["Patrocínio"] == Decimal("1000.00")
    assert sum(coluna(entradas, "Líquido"), ZERO) == extrato["Entradas"]
    assert sum(coluna(tabela(balancete, "Saídas por categoria"), "Líquido"), ZERO) == extrato["Saídas"]
    assert sum(coluna(tabela(balancete, "Saídas por setor"), "Líquido"), ZERO) == extrato["Saídas"]
    assert {k: resumo(balancete)[k] for k in extrato} == extrato


# Inadimplência (CA-18) -----------------------------------------------------------------------------------


def test_ca18_inadimplencia_e_a_do_dashboard_por_devedor_com_os_totais(massa: Massa) -> None:
    inadimplencia = _um("INADIMPLENCIA", {}, massa.fin)

    numeros = resumo(inadimplencia)
    do_painel = financeiro.resumo_da_inadimplencia()
    assert (numeros["Cobranças"], numeros["Devedores"], numeros["Total"]) == (
        do_painel.cobrancas,
        do_painel.devedores,
        do_painel.total,
    )
    cobrancas = tabela(inadimplencia, "Cobranças inadimplentes")
    assert coluna(cobrancas, "Devedor") == [massa.devedor.nome]
    assert (coluna(cobrancas, "Convocado"), coluna(cobrancas, "Justificou")) == ([True], [True])
    por_devedor = tabela(inadimplencia, "Total por devedor")
    assert sum(coluna(por_devedor, "Total"), ZERO) == numeros["Total"]


def test_ca18_nenhum_contato_nem_texto_livre_no_arquivo(massa: Massa) -> None:
    inadimplencia = _um("INADIMPLENCIA", {}, massa.fin)

    arquivos = [
        escrever_csv(inadimplencia, CABECALHO).decode("utf-8-sig"),
        texto_do_pdf(escrever_pdf(inadimplencia, CABECALHO, compactar=False)),
    ]
    proibidos = [
        massa.devedor.email,
        massa.devedor.telefone,
        massa.devedor2.email,
        SEGREDO_DA_JUSTIFICATIVA,
        SEGREDO_DO_QUESTIONAMENTO,
    ]
    for conteudo in arquivos:
        assert massa.devedor.nome in conteudo
        for proibido in proibidos:
            assert proibido not in conteudo


# Eventos (CA-19) -----------------------------------------------------------------------------------------


def _evento(titulo: str, **mudar: Any) -> eventos.EventoDoPeriodo:
    dados: dict[str, Any] = {
        "id": uuid.uuid7(),
        "titulo": titulo,
        "categoria": "Jogo",
        "inicio": datetime(2026, 10, 10, 18, tzinfo=AGORA.tzinfo),
        "local": "Campo",
        "situacao": "PUBLICADO",
        "proponente": "Diretor prop",
        "envolve_custo": False,
        "motivo": "",
        "vou": 0,
        "nao_vou": 0,
    }
    dados.update(mudar)
    return eventos.EventoDoPeriodo(**dados)


def test_ca19_eventos_junta_o_orcamento_e_as_presencas(massa: Massa) -> None:
    com_custo = _evento('<img src="/etc/passwd"> Amistoso', envolve_custo=True, vou=3, nao_vou=1)
    recusado = _evento("Festa", situacao="RECUSADO", motivo="Fora das prioridades")
    orcamento = financeiro.OrcamentoDoEvento(aprovado=Decimal("400.00"), realizado=Decimal("350.00"))
    with (
        mock.patch.object(eventos, "eventos_do_periodo", return_value=[com_custo, recusado]) as do_periodo,
        mock.patch.object(financeiro, "orcamentos_de_eventos", return_value={com_custo.id: orcamento}),
    ):
        documento = _um("EVENTOS", OUT, massa.fin)

    do_periodo.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 31))
    linhas = tabela(documento, "Eventos")
    assert coluna(linhas, "Orçamento aprovado") == [Decimal("400.00"), None]
    assert coluna(linhas, "Realizado") == [Decimal("350.00"), None]
    assert (coluna(linhas, "Vou"), coluna(linhas, "Não vou")) == ([3, 0], [1, 0])
    assert coluna(linhas, "Motivo") == ["", "Fora das prioridades"]
    assert resumo(documento)["Orçamento aprovado"] == Decimal("400.00")
    pdf = texto_do_pdf(escrever_pdf(documento, CABECALHO, compactar=False))
    assert 'src="/etc/passwd"' in pdf
    assert "/Subtype /Image" not in pdf


# Prestação de contas (CA-20) -----------------------------------------------------------------------------


def test_ca20_prestacao_de_contas_do_periodo_e_so_pendentes(massa: Massa) -> None:
    novembro = {"mes": "2026-11"}
    todas = tabela(_um("PRESTACAO_DE_CONTAS", novembro, massa.fin), "Saídas com recurso enviado")
    pendentes = tabela(
        _um("PRESTACAO_DE_CONTAS", {**novembro, "so_pendentes": True}, massa.fin),
        "Saídas com recurso enviado",
    )

    assert coluna(pendentes, "Aprovado") == [Decimal("80.00")]
    assert coluna(pendentes, "Comprovante") == [False]
    assert len(todas.linhas) >= len(pendentes.linhas)
    assert all(isinstance(v, bool) for v in coluna(todas, "Comprovante"))


def test_ca20_so_pendentes_tem_que_ser_sim_ou_nao(massa: Massa) -> None:
    with pytest.raises(ParametroInvalido) as erro:
        _montar("PRESTACAO_DE_CONTAS", {"mes": "2026-11", "so_pendentes": "talvez"}, massa.fin)
    assert erro.value.campo == "so_pendentes"


# Fluxo de caixa (CA-21) ----------------------------------------------------------------------------------


def test_ca21_fluxo_de_caixa_realizado_igual_ao_extrato_e_comprometido_igual_ao_dashboard(
    massa: Massa,
) -> None:
    fluxo = _um("FLUXO_DE_CAIXA", {"de": "2026-10", "ate": "2026-11"}, massa.fin)

    realizado = tabela(fluxo, "Realizado")
    assert coluna(realizado, "Mês") == ["10/2026", "11/2026"]
    extrato = resumo(_um("EXTRATO", OUT, massa.fin))
    outubro = dict(zip([c.nome for c in realizado.colunas], realizado.linhas[0], strict=True))
    assert (outubro["Entradas"], outubro["Saídas"], outubro["Resultado"]) == (
        extrato["Entradas"],
        extrato["Saídas"],
        extrato["Resultado"],
    )
    assert outubro["Saldo no fim do mês"] == extrato["Saldo no fim"]
    painel = dashboard.dashboard(massa.fin.id)
    assert isinstance(painel, dashboard.DashboardCompleto)
    assert resumo(fluxo)["Comprometido hoje"] == painel.hoje.comprometido
    previsto = tabela(fluxo, "Previsto pelo vencimento")
    esperado = financeiro.fluxo_previsto(date(2026, 10, 1), date(2026, 11, 30), hoje=HOJE)
    assert coluna(previsto, "Previsto") == [m.previsto for m in esperado]


# Meus dados (CA-22) --------------------------------------------------------------------------------------


def test_ca22_meus_dados_sao_tres_csv_so_de_quem_pede(massa: Massa) -> None:
    documentos = _montar("MEUS_DADOS", {}, massa.devedor)

    assert [d.titulo for d in documentos] == ["Dados", "Cobranças", "Eventos"]
    textos = [escrever_csv(d, CABECALHO).decode("utf-8-sig") for d in documentos]
    assert massa.devedor.email in textos[0]
    assert all(massa.devedor2.email not in texto and massa.devedor2.nome not in texto for texto in textos)
    cobrancas = tabela(documentos[1], "Cobranças")
    assert len(cobrancas.linhas) == 3
    assert "Mensalidade" in coluna(cobrancas, "Descrição")


def test_ca22_meus_dados_nao_aceita_parametro_de_outro_usuario(massa: Massa) -> None:
    with pytest.raises(ParametroInvalido) as erro:
        _montar("MEUS_DADOS", {"usuario_id": str(massa.devedor2.id)}, massa.devedor)
    assert erro.value.campo == "usuario_id"


def test_ca22_meus_dados_sai_em_zip_com_os_tres_nomes(massa: Massa) -> None:
    conteudo, extensao = geracao._escrever(_montar("MEUS_DADOS", {}, massa.devedor), Formato.CSV, CABECALHO)

    assert extensao == "zip"
    assert sorted(zipfile.ZipFile(io.BytesIO(conteudo)).namelist()) == [
        "cobrancas.csv",
        "dados.csv",
        "eventos.csv",
    ]


# PDF e CSV com os mesmos números, e totais iguais à soma das linhas (CA-25) ------------------------------


def _dinheiro(documento: Documento) -> list[Decimal]:
    valores = [item.valor for item in documento.resumo if item.tipo == TipoDeColuna.DINHEIRO]
    for t in documento.tabelas:
        indices = [i for i, c in enumerate(t.colunas) if c.tipo == TipoDeColuna.DINHEIRO]
        valores += [linha[i] for linha in t.linhas for i in indices]
    return [v for v in valores if isinstance(v, Decimal)]


@pytest.mark.parametrize(
    ("codigo", "parametros"),
    [
        ("EXTRATO", OUT),
        ("BALANCETE", OUT),
        ("INADIMPLENCIA", {}),
        ("PRESTACAO_DE_CONTAS", {"mes": "2026-11"}),
        ("FLUXO_DE_CAIXA", {"de": "2026-10", "ate": "2026-11"}),
    ],
)
def test_ca25_pdf_e_csv_trazem_os_mesmos_numeros(
    massa: Massa, codigo: str, parametros: dict[str, Any]
) -> None:
    documento = _um(codigo, parametros, massa.fin)

    pdf = texto_do_pdf(escrever_pdf(documento, CABECALHO, compactar=False))
    linhas_do_csv = list(
        csv.reader(io.StringIO(escrever_csv(documento, CABECALHO).decode("utf-8-sig")), delimiter=";")
    )
    celulas = {celula for linha in linhas_do_csv for celula in linha}
    for valor in _dinheiro(documento):
        assert formatar_para_leitura(valor, TipoDeColuna.DINHEIRO) in pdf, (codigo, valor)
        assert f"{valor:.2f}".replace(".", ",") in celulas, (codigo, valor)


def test_ca25_totais_sao_a_soma_das_linhas(massa: Massa) -> None:
    extrato = _um("EXTRATO", OUT, massa.fin)
    assert sum(coluna(tabela(extrato, "Lançamentos"), "Valor"), ZERO) == resumo(extrato)["Resultado"]

    inadimplencia = _um("INADIMPLENCIA", {}, massa.fin)
    assert (
        sum(coluna(tabela(inadimplencia, "Cobranças inadimplentes"), "Valor"), ZERO)
        == resumo(inadimplencia)["Total"]
    )

    prestacao = _um("PRESTACAO_DE_CONTAS", {"mes": "2026-11"}, massa.fin)
    linhas = tabela(prestacao, "Saídas com recurso enviado")
    for rotulo, nome in (
        ("Aprovado", "Aprovado"),
        ("Enviado", "Enviado"),
        ("Devolvido", "Devolvido validado"),
    ):
        assert sum(coluna(linhas, nome), ZERO) == resumo(prestacao)[rotulo]

    fluxo = _um("FLUXO_DE_CAIXA", {"de": "2026-10", "ate": "2026-11"}, massa.fin)
    previsto = tabela(fluxo, "Previsto pelo vencimento")
    assert sum(coluna(previsto, "Previsto"), ZERO) == resumo(fluxo)["Previsto"]
    assert sum(coluna(tabela(fluxo, "Realizado"), "Resultado"), ZERO) == resumo(fluxo)["Resultado"]
