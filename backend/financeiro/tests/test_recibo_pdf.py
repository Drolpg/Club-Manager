"""Testes do gerador determinístico de recibo em PDF (CA-19)."""

import uuid
from datetime import date
from decimal import Decimal

from financeiro.recibo_pdf import DadosRecibo, gerar_recibo_pdf


def test_CA19_gera_pdf_deterministico_com_campos_obrigatorios() -> None:
    dados = DadosRecibo(
        cobranca_id=uuid.UUID("01932e50-1234-7000-8000-000000000099"),
        devedor_nome="João Antônio da Silva",
        categoria_nome="Mensalidade",
        descricao="Mensalidade Novembro 2026",
        valor=Decimal("150.00"),
        data_pagamento=date(2026, 11, 10),
        data_validacao=date(2026, 11, 11),
    )

    pdf1 = gerar_recibo_pdf(dados)
    pdf2 = gerar_recibo_pdf(dados)

    assert pdf1 == pdf2
    assert pdf1.startswith(b"%PDF-1.4\n")
    assert pdf1.endswith(b"%%EOF\n")
    assert b"RECIBO DE PAGAMENTO" in pdf1
    assert "João Antônio da Silva".encode("latin-1") in pdf1
    assert b"Mensalidade" in pdf1
    assert b"Mensalidade Novembro 2026" in pdf1
    assert b"R$ 150,00" in pdf1
    assert b"10/11/2026" in pdf1
    assert b"11/11/2026" in pdf1
