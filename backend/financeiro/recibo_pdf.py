"""Gerador determinístico de recibo de pagamento em PDF 1.4 sem dependências externas (CA-19)."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class DadosRecibo:
    """Dados imutáveis exibidos no recibo em PDF de uma cobrança paga."""

    cobranca_id: uuid.UUID
    devedor_nome: str
    categoria_nome: str
    descricao: str
    valor: Decimal
    data_pagamento: date
    data_validacao: date


def _reais(valor: Decimal) -> str:
    formatado = f"{valor:,.2f}"
    return "R$ " + formatado.replace(",", "_").replace(".", ",").replace("_", ".")


def _data_br(valor: date) -> str:
    return valor.strftime("%d/%m/%Y")


def _escapar_pdf(texto: str) -> bytes:
    """Codifica em Latin-1 (WinAnsi) e escapa parênteses e barra invertida para literais PDF."""
    codificado = texto.encode("latin-1", errors="replace").decode("latin-1")
    escapado = codificado.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escapado.encode("latin-1")


def _quebrar_linhas(texto: str, largura: int = 72) -> list[str]:
    palavras = texto.split()
    if not palavras:
        return ["-"]
    linhas: list[str] = []
    atual = palavras[0]
    for palavra in palavras[1:]:
        if len(atual) + 1 + len(palavra) <= largura:
            atual += f" {palavra}"
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)
    return linhas


def _montar_stream(dados: DadosRecibo) -> bytes:
    comandos: list[bytes] = [
        b"BT",
        b"/F2 16 Tf",
        b"56 760 Td",
        b"(RECIBO DE PAGAMENTO - CLUB MANAGER) Tj",
        b"/F1 11 Tf",
        b"0 -28 Td",
        b"(Situacao: PAGA) Tj",
    ]
    linhas = [
        f"Codigo da cobranca: {dados.cobranca_id}",
        f"Devedor: {dados.devedor_nome}",
        f"Categoria: {dados.categoria_nome}",
        f"Valor pago: {_reais(dados.valor)}",
        f"Data do pagamento: {_data_br(dados.data_pagamento)}",
        f"Data da validacao: {_data_br(dados.data_validacao)}",
    ]
    for idx, linha in enumerate(linhas):
        salto = -24 if idx == 0 else -20
        comandos.append(f"0 {salto} Td".encode("ascii"))
        comandos.append(b"(" + _escapar_pdf(linha) + b") Tj")

    comandos.append(b"0 -24 Td")
    comandos.append(b"/F2 11 Tf")
    comandos.append(b"(Descricao:) Tj")
    comandos.append(b"/F1 11 Tf")
    for trecho in _quebrar_linhas(dados.descricao):
        comandos.append(b"0 -18 Td")
        comandos.append(b"(" + _escapar_pdf(trecho) + b") Tj")

    comandos.append(b"ET")
    return b"\n".join(comandos) + b"\n"


def gerar_recibo_pdf(dados: DadosRecibo) -> bytes:
    """Gera um PDF 1.4 válido e byte-a-byte determinístico (sem timestamps variáveis)."""
    stream = _montar_stream(dados)
    objetos: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>\nendobj\n"
        ),
        (
            b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>\nendobj\n"
        ),
        (
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            b"/Encoding /WinAnsiEncoding >>\nendobj\n"
        ),
        (f"6 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream\nendobj\n"),
    ]

    partes: list[bytes] = [b"%PDF-1.4\n"]
    offsets: list[int] = [0]
    posicao = len(partes[0])
    for obj in objetos:
        offsets.append(posicao)
        partes.append(obj)
        posicao += len(obj)

    xref_inicio = posicao
    xref_linhas = [f"xref\n0 {len(objetos) + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref_linhas.append(f"{off:010d} 00000 n \n".encode("ascii"))
    trailer = (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref_inicio}\n%%EOF\n"
    ).encode("ascii")

    return b"".join(partes + xref_linhas + [trailer])
