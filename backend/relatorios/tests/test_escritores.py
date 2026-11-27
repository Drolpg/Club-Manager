"""Os escritores de PDF, CSV e ZIP (CA-23, CA-24): recebem o documento tabular e não conhecem o relatório."""

import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from relatorios.domain.documento import Cabecalho, Coluna, Documento, ItemDoResumo, Tabela, TipoDeColuna
from relatorios.escritores.csv import escrever_csv
from relatorios.escritores.pdf import escrever_pdf
from relatorios.escritores.zip import escrever_zip

T = TipoDeColuna
CABECALHO = Cabecalho(
    gerado_em=datetime(2026, 11, 27, 9, 30, tzinfo=ZoneInfo("America/Sao_Paulo")), gerado_por="Ana"
)


def _documento(linhas: int = 3, descricao: str = "Mensalidade de novembro") -> Documento:
    return Documento(
        titulo="Inadimplência",
        parametros="Período de 01/11/2026 a 30/11/2026",
        resumo=(
            ItemDoResumo("Total", Decimal("-150.00"), T.DINHEIRO),
            ItemDoResumo("Cobranças", 3, T.INTEIRO),
        ),
        tabelas=(
            Tabela(
                titulo="Cobranças em atraso",
                colunas=(
                    Coluna("Vencimento", T.DATA),
                    Coluna("Descrição", T.TEXTO),
                    Coluna("Valor", T.DINHEIRO),
                    Coluna("Convocado", T.SIM_NAO),
                ),
                linhas=tuple(
                    (date(2026, 11, 5), descricao, Decimal("-50.00"), n % 2 == 0) for n in range(linhas)
                ),
            ),
        ),
    )


# --- CSV ---------------------------------------------------------------------------------------------------


def test_csv_utf8_com_bom_ponto_e_virgula_e_crlf() -> None:
    conteudo = escrever_csv(_documento(), CABECALHO)

    assert conteudo.startswith("﻿".encode())
    texto = conteudo.decode("utf-8-sig")
    assert "\r\n" in texto
    linhas = texto.split("\r\n")
    assert linhas[0] == "Relatório;Inadimplência"
    assert "Gerado em;27/11/2026 09:30" in linhas
    assert "Gerado por;Ana" in linhas
    assert "Total;-150,00" in linhas
    assert "Vencimento;Descrição;Valor;Convocado" in linhas
    assert "05/11/2026;Mensalidade de novembro;-50,00;sim" in linhas


def test_csv_resumo_antes_da_tabela_com_linha_em_branco() -> None:
    linhas = escrever_csv(_documento(), CABECALHO).decode("utf-8-sig").split("\r\n")

    assert linhas.index("Total;-150,00") < linhas.index("Cobranças em atraso")
    assert linhas[linhas.index("Cobranças em atraso") - 1] == ""


def test_ca23_csv_escapa_formula_so_no_texto_e_nao_no_numero_negativo() -> None:
    texto = escrever_csv(_documento(descricao='=HIPERLINK("x")'), CABECALHO).decode("utf-8-sig")

    assert "'=HIPERLINK" in texto
    assert ";-50,00;" in texto
    assert ";'-50,00;" not in texto


def test_csv_escapa_formula_tambem_no_nome_de_quem_gerou() -> None:
    cabecalho = Cabecalho(gerado_em=CABECALHO.gerado_em, gerado_por="=CMD()")

    assert "Gerado por;'=CMD()" in escrever_csv(_documento(), cabecalho).decode("utf-8-sig")


# --- PDF ---------------------------------------------------------------------------------------------------


def _texto_do_pdf(pdf: bytes) -> str:
    """O conteúdo sem compactação, com os escapes octais das strings do PDF (`\\352` é "ê") desfeitos."""
    return re.sub(rb"\\([0-7]{3})", lambda m: bytes([int(m.group(1), 8)]), pdf).decode("latin-1")


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page\b", pdf))


def test_ca24_pdf_abre_com_cabecalho_e_acentos() -> None:
    pdf = escrever_pdf(_documento(), CABECALHO, compactar=False)

    assert pdf.startswith(b"%PDF-")
    texto = _texto_do_pdf(pdf)
    assert "Club Manager" in texto
    assert "Inadimpl\xeancia" in texto
    assert "Per\xedodo de 01/11/2026 a 30/11/2026" in texto
    assert "27/11/2026 09:30" in texto
    assert "n\xe3o" in texto
    assert "-R$ 50,00" in texto


def test_ca24_tabela_longa_quebra_pagina_repete_cabecalho_e_numera() -> None:
    pdf = escrever_pdf(_documento(linhas=120), CABECALHO, compactar=False)

    paginas = _paginas(pdf)
    assert paginas >= 2
    texto = _texto_do_pdf(pdf)
    assert texto.count("(Vencimento)") == paginas
    assert f"p\xe1gina 2 de {paginas}" in texto


def test_marcacao_vinda_de_pessoa_aparece_como_texto_e_nao_vira_imagem_nem_cor() -> None:
    descricao = '<img src="/etc/passwd" width="10" height="10"/> <font color="red">vermelho</font>'

    pdf = escrever_pdf(_documento(descricao=descricao), CABECALHO, compactar=False)

    assert b"/Subtype /Image" not in pdf
    texto = _texto_do_pdf(pdf)
    assert 'img src="/etc/passwd" width="10" height="10"/' in texto
    assert "(font)" in texto
    assert "(vermelho)" in texto
    assert "1 0 0 rg" not in texto


def test_pdf_deterministico_para_o_mesmo_documento() -> None:
    assert escrever_pdf(_documento(), CABECALHO, compactar=False) == escrever_pdf(
        _documento(), CABECALHO, compactar=False
    )


def test_pdf_compactado_tambem_abre() -> None:
    assert escrever_pdf(_documento(linhas=40), CABECALHO).startswith(b"%PDF-")


# --- ZIP ---------------------------------------------------------------------------------------------------


def test_zip_com_os_arquivos_pedidos() -> None:
    conteudo = escrever_zip([("dados.csv", b"a;b\r\n"), ("cobrancas.csv", b"c\r\n"), ("eventos.csv", b"")])

    with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivo:
        assert arquivo.namelist() == ["dados.csv", "cobrancas.csv", "eventos.csv"]
        assert arquivo.read("dados.csv") == b"a;b\r\n"
