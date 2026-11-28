"""Escritor de PDF com a ReportLab (ADR-019): A4, tabelas que continuam nas páginas seguintes com o cabeçalho
repetido, e "página N de M".

Texto vindo de pessoa nunca entra como marcação do `Paragraph`, que interpreta tags (inclusive
`<img src=...>`, que leria um arquivo local, e atributos avaliados): todo texto é escapado antes de virar
parágrafo. O cabeçalho de página é neutro; o M11 o preenche com a marca (P24).
"""

import io
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from relatorios.domain.csv_seguro import formatar_para_leitura
from relatorios.domain.documento import Cabecalho, Documento, Tabela, TipoDeColuna, Valor

_MARGEM = 15 * mm
_TOPO = 32 * mm
_FONTE = "Helvetica"
_NEGRITO = "Helvetica-Bold"
_ESTILOS = getSampleStyleSheet()
_CELULA = ParagraphStyle("celula", parent=_ESTILOS["BodyText"], fontName=_FONTE, fontSize=8, leading=10)
_TITULO_DA_TABELA = ParagraphStyle("titulo_da_tabela", parent=_ESTILOS["Heading3"], fontName=_NEGRITO)
_RESUMO = ParagraphStyle("resumo", parent=_ESTILOS["BodyText"], fontName=_FONTE, fontSize=9, leading=12)


def _texto(valor: str, estilo: ParagraphStyle) -> Paragraph:
    """Um parágrafo com o texto escapado: nenhuma tag de quem escreveu é interpretada."""
    return Paragraph(escape(valor), estilo)


class _CanvasNumerado(canvas.Canvas):  # type: ignore[misc]
    """Guarda as páginas e, no fim, escreve "página N de M" em cada uma."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._paginas: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self.setFont(_FONTE, 8)
            self.drawRightString(
                self._pagesize[0] - _MARGEM, 10 * mm, f"página {self._pageNumber} de {total}"
            )
            super().showPage()
        super().save()


def _desenhar_cabecalho(documento: Documento, cabecalho: Cabecalho) -> Any:
    gerado = f"Gerado em {cabecalho.gerado_em.strftime('%d/%m/%Y %H:%M')} por {cabecalho.gerado_por}"

    def desenhar(tela: Any, _doc: Any) -> None:
        tela.saveState()
        topo = tela._pagesize[1] - _MARGEM
        tela.setFont(_NEGRITO, 9)
        tela.drawString(_MARGEM, topo, cabecalho.nome)
        tela.setFont(_NEGRITO, 13)
        tela.drawString(_MARGEM, topo - 6 * mm, documento.titulo)
        tela.setFont(_FONTE, 8)
        tela.drawString(_MARGEM, topo - 11 * mm, documento.parametros)
        tela.drawString(_MARGEM, topo - 15 * mm, gerado)
        tela.restoreState()

    return desenhar


_RECUO = 10  # o recuo da célula, 3 pontos de cada lado, e uma folga para o parágrafo não quebrar a palavra
_TEXTO_MINIMO = 60
_NUMERICAS = frozenset({TipoDeColuna.DINHEIRO, TipoDeColuna.INTEIRO})


def _medida(texto: str) -> float:
    return float(stringWidth(texto, _FONTE, _CELULA.fontSize)) + _RECUO


def _fixas(tabela: Tabela) -> dict[int, float]:
    """A largura das colunas que não são texto: a do maior valor, para nenhum valor quebrar em duas linhas."""
    return {
        i: max(
            [_medida(formatar_para_leitura(linha[i], coluna.tipo)) for linha in tabela.linhas]
            + [_medida(palavra) for palavra in coluna.nome.split()]
        )
        for i, coluna in enumerate(tabela.colunas)
        if coluna.tipo != TipoDeColuna.TEXTO
    }


def _pesos(tabela: Tabela, disponivel: float) -> list[float]:
    pesos = [3 if coluna.tipo == TipoDeColuna.TEXTO else 1.2 for coluna in tabela.colunas]
    return [disponivel * peso / sum(pesos) for peso in pesos]


def _cabe(tabela: Tabela, disponivel: float) -> bool:
    textos = sum(1 for coluna in tabela.colunas if coluna.tipo == TipoDeColuna.TEXTO)
    return sum(_fixas(tabela).values()) + textos * _TEXTO_MINIMO <= disponivel


def _larguras(tabela: Tabela, disponivel: float) -> list[float]:
    """Pelos pesos; a coluna que não é texto e não cabe ganha a largura medida, tirada das de texto."""
    larguras = _pesos(tabela, disponivel)
    fixas = {i: largura for i, largura in _fixas(tabela).items() if largura > larguras[i]}
    if not fixas:
        return larguras
    textos = [i for i, coluna in enumerate(tabela.colunas) if coluna.tipo == TipoDeColuna.TEXTO]
    sobra = disponivel - sum(fixas.get(i, larguras[i]) for i in range(len(larguras)) if i not in textos)
    peso_dos_textos = sum(larguras[i] for i in textos) or 1.0
    return [
        fixas.get(
            i, max(sobra * larguras[i] / peso_dos_textos, _TEXTO_MINIMO) if i in textos else larguras[i]
        )
        for i in range(len(larguras))
    ]


def _celula(valor: Valor, tipo: TipoDeColuna) -> Any:
    """Texto de pessoa vira parágrafo escapado, que quebra linha; o resto vai como `str`, sem marcação."""
    texto = formatar_para_leitura(valor, tipo)
    return _texto(texto, _CELULA) if tipo == TipoDeColuna.TEXTO else texto


def _tabela(tabela: Tabela, disponivel: float) -> Table:
    cabecalho = [_texto(coluna.nome, _CELULA) for coluna in tabela.colunas]
    linhas = [
        [_celula(valor, coluna.tipo) for valor, coluna in zip(linha, tabela.colunas, strict=True)]
        for linha in tabela.linhas
    ]
    resultado = Table([cabecalho, *linhas], colWidths=_larguras(tabela, disponivel), repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONT", (0, 1), (-1, -1), _FONTE, _CELULA.fontSize, _CELULA.leading),
    ]
    estilo += [
        ("ALIGN", (i, 1), (i, -1), "RIGHT")
        for i, coluna in enumerate(tabela.colunas)
        if coluna.tipo in _NUMERICAS
    ]
    resultado.setStyle(TableStyle(estilo))
    return resultado


def _pagina(documento: Documento) -> tuple[float, float]:
    """A4 em pé; deitado quando alguma tabela não cabe em pé."""
    em_pe = A4[0] - 2 * _MARGEM
    deitado: tuple[float, float] = landscape(A4)
    return A4 if all(_cabe(tabela, em_pe) for tabela in documento.tabelas) else deitado


def escrever_pdf(documento: Documento, cabecalho: Cabecalho, *, compactar: bool = True) -> bytes:
    """O PDF do documento. `invariant` deixa o arquivo igual para o mesmo conteúdo (sem data de criação)."""
    saida = io.BytesIO()
    pagina = _pagina(documento)
    pdf = SimpleDocTemplate(
        saida,
        pagesize=pagina,
        leftMargin=_MARGEM,
        rightMargin=_MARGEM,
        topMargin=_TOPO,
        bottomMargin=_MARGEM + 5 * mm,
        title=documento.titulo,
        author=cabecalho.nome,
        invariant=1,
        pageCompression=1 if compactar else 0,
    )
    disponivel = pagina[0] - 2 * _MARGEM
    historia: list[Any] = [
        _texto(f"{item.rotulo}: {formatar_para_leitura(item.valor, item.tipo)}", _RESUMO)
        for item in documento.resumo
    ]
    for tabela in documento.tabelas:
        historia += [Spacer(1, 4 * mm), _texto(tabela.titulo, _TITULO_DA_TABELA), _tabela(tabela, disponivel)]
    desenhar = _desenhar_cabecalho(documento, cabecalho)
    pdf.build(historia, onFirstPage=desenhar, onLaterPages=desenhar, canvasmaker=_CanvasNumerado)
    return saida.getvalue()
