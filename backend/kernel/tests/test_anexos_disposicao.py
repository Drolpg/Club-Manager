"""`resposta_anexo` com `disposicao` (D5 da spec `relatorios/relatorios-pdf-e-csv`): `inline` continua o
padrão das rotas de hoje; os relatórios baixam com `attachment`. Os cabeçalhos seguros não mudam.
"""

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from kernel.anexos import resposta_anexo

CHAVE = "testes/disposicao.pdf"


@pytest.fixture(autouse=True)
def _arquivo() -> object:
    default_storage.save(CHAVE, ContentFile(b"%PDF-1.4 teste"))
    yield
    default_storage.delete(CHAVE)


def test_o_padrao_continua_inline() -> None:
    resposta = resposta_anexo(chave=CHAVE, nome="doc.pdf", mime="application/pdf")

    assert resposta["Content-Disposition"] == 'inline; filename="doc.pdf"'


def test_attachment_para_baixar_com_os_mesmos_cabecalhos_seguros() -> None:
    resposta = resposta_anexo(
        chave=CHAVE, nome="extrato.pdf", mime="application/pdf", disposicao="attachment"
    )

    assert resposta["Content-Disposition"] == 'attachment; filename="extrato.pdf"'
    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert resposta["Cache-Control"] == "private, no-store"


def test_disposicao_desconhecida_e_recusada() -> None:
    with pytest.raises(ValueError, match="disposicao"):
        resposta_anexo(chave=CHAVE, nome="x.pdf", mime="application/pdf", disposicao="form-data")
