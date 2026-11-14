"""Testes unitários de armazenamento e validação de anexos (ADR-014, CA-20)."""

import io

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from kernel.anexos import TAMANHO_MAXIMO_ANEXO, resposta_anexo, validar_e_salvar_anexo
from kernel.errors import BusinessError


def _arquivo(nome: str, conteudo: bytes, mime: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, conteudo, content_type=mime)


PDF_VALIDO = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PNG_VALIDO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_VALIDO = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP_VALIDO = b"RIFF\x24\x00\x00\x00WEBP" + b"\x00" * 24


@pytest.mark.parametrize(
    ("nome", "conteudo", "mime", "mime_esperado", "ext_esperada"),
    [
        ("comprovante.pdf", PDF_VALIDO, "application/pdf", "application/pdf", ".pdf"),
        ("foto.png", PNG_VALIDO, "image/png", "image/png", ".png"),
        ("foto.jpeg", JPEG_VALIDO, "image/jpeg", "image/jpeg", ".jpg"),
        ("foto.webp", WEBP_VALIDO, "image/webp", "image/webp", ".webp"),
    ],
)
def test_aceita_tipos_permitidos_e_gera_chave_opaca(
    nome: str,
    conteudo: bytes,
    mime: str,
    mime_esperado: str,
    ext_esperada: str,
) -> None:
    salvo = validar_e_salvar_anexo(_arquivo(nome, conteudo, mime), contexto="pagamentos")

    assert salvo.chave.startswith("pagamentos/")
    assert salvo.chave.endswith(ext_esperada)
    assert salvo.mime == mime_esperado
    assert salvo.tamanho == len(conteudo)
    assert default_storage.exists(salvo.chave)

    resposta = resposta_anexo(chave=salvo.chave, nome=salvo.nome, mime=salvo.mime)
    assert resposta.status_code == 200
    assert resposta.content == conteudo
    assert resposta["Content-Type"] == mime_esperado
    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert resposta["Cache-Control"] == "private, no-store"
    assert "inline;" in resposta["Content-Disposition"]


def test_sanitiza_nome_contra_travessia_de_diretorio() -> None:
    salvo = validar_e_salvar_anexo(
        _arquivo("../../etc/passwd.pdf", PDF_VALIDO, "application/pdf"),
        contexto="entradas",
    )

    assert ".." not in salvo.chave
    assert "/" not in salvo.nome
    assert "\\" not in salvo.nome
    assert salvo.nome == "passwd.pdf"


def test_recusa_arquivo_vazio() -> None:
    with pytest.raises(BusinessError) as exc:
        validar_e_salvar_anexo(_arquivo("vazio.pdf", b"", "application/pdf"), contexto="pagamentos")

    assert exc.value.status == 400
    assert exc.value.code == "VALIDATION_ERROR"


def test_CA20_recusa_arquivo_maior_que_5mb() -> None:
    grande = PDF_VALIDO + (b"0" * TAMANHO_MAXIMO_ANEXO)
    with pytest.raises(BusinessError) as exc:
        validar_e_salvar_anexo(_arquivo("grande.pdf", grande, "application/pdf"), contexto="pagamentos")

    assert exc.value.status == 400
    assert exc.value.code == "VALIDATION_ERROR"


def test_CA20_aceita_arquivo_exatamente_no_limite_de_5mb() -> None:
    exato = PDF_VALIDO + (b"0" * (TAMANHO_MAXIMO_ANEXO - len(PDF_VALIDO)))
    salvo = validar_e_salvar_anexo(_arquivo("limite.pdf", exato, "application/pdf"), contexto="pagamentos")

    assert salvo.tamanho == TAMANHO_MAXIMO_ANEXO


@pytest.mark.parametrize(
    ("nome", "conteudo", "mime"),
    [
        ("malicioso.svg", b"<svg><script>alert(1)</script></svg>", "image/svg+xml"),
        ("pagina.html", b"<html><body>ola</body></html>", "text/html"),
        ("script.exe", b"MZ\x90\x00", "application/octet-stream"),
        ("disfarcado.pdf", b"<html>nao e pdf</html>", "application/pdf"),
        ("falso.png", PDF_VALIDO, "image/png"),
        ("mime_divergente.pdf", PDF_VALIDO, "image/png"),
    ],
)
def test_CA20_recusa_tipo_proibido_ou_assinatura_falsificada(nome: str, conteudo: bytes, mime: str) -> None:
    with pytest.raises(BusinessError) as exc:
        validar_e_salvar_anexo(_arquivo(nome, conteudo, mime), contexto="pagamentos")

    assert exc.value.status == 400
    assert exc.value.code == "VALIDATION_ERROR"


def test_recusa_arquivo_ausente() -> None:
    with pytest.raises(BusinessError) as exc:
        validar_e_salvar_anexo(io.BytesIO(b""), contexto="pagamentos")

    assert exc.value.status == 400
    assert exc.value.code == "VALIDATION_ERROR"

    with pytest.raises(BusinessError) as exc_none:
        validar_e_salvar_anexo(None, contexto="pagamentos")

    assert exc_none.value.status == 400
    assert exc_none.value.code == "VALIDATION_ERROR"


def test_resposta_anexo_inexistente_retorna_404() -> None:
    with pytest.raises(BusinessError) as exc:
        resposta_anexo(chave="pagamentos/inexistente.pdf", nome="doc.pdf", mime="application/pdf")

    assert exc.value.status == 404
    assert exc.value.code == "NOT_FOUND"
