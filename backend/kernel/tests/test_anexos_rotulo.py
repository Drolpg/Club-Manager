"""Rótulo e campo dos erros de anexo: o padrão é o do comprovante; documentos pedem os seus (M9)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from kernel.anexos import TAMANHO_MAXIMO_ANEXO, resposta_anexo, validar_e_salvar_anexo
from kernel.errors import BusinessError

PDF_VALIDO = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PNG_VALIDO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _arquivo(nome: str, conteudo: bytes, mime: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, conteudo, content_type=mime)


def _erro_de_documento(arquivo: object) -> BusinessError:
    with pytest.raises(BusinessError) as exc:
        validar_e_salvar_anexo(arquivo, contexto="documentos", campo="arquivo", rotulo="documento")
    assert exc.value.code == "VALIDATION_ERROR"
    assert exc.value.status == 400
    return exc.value


def _mensagem(erro: BusinessError, campo: str) -> str:
    detalhes = erro.details
    assert detalhes is not None
    return str(detalhes[campo][0])


def test_aceita_o_contexto_documentos() -> None:
    salvo = validar_e_salvar_anexo(
        _arquivo("estatuto.pdf", PDF_VALIDO, "application/pdf"),
        contexto="documentos",
        campo="arquivo",
        rotulo="documento",
    )

    assert salvo.chave.startswith("documentos/")


def test_arquivo_vazio_fala_de_documento_no_campo_arquivo() -> None:
    erro = _erro_de_documento(_arquivo("vazio.pdf", b"", "application/pdf"))

    assert "comprovante" not in (erro.details or {})
    assert _mensagem(erro, "arquivo") == "O arquivo enviado está vazio."


def test_arquivo_grande_fala_de_documento() -> None:
    grande = PDF_VALIDO + b"0" * TAMANHO_MAXIMO_ANEXO
    erro = _erro_de_documento(_arquivo("grande.pdf", grande, "application/pdf"))

    assert _mensagem(erro, "arquivo") == "O documento excede o limite de 5 MB."


def test_formato_nao_permitido_nao_depende_do_rotulo() -> None:
    erro = _erro_de_documento(_arquivo("a.pdf", b"<html></html>", "application/pdf"))

    assert _mensagem(erro, "arquivo") == "Formato não permitido. Envie PDF, PNG, JPEG ou WebP."


def test_extensao_que_nao_bate_com_o_conteudo_e_recusada() -> None:
    erro = _erro_de_documento(_arquivo("a.png", PDF_VALIDO, "application/pdf"))

    assert "extensão" in _mensagem(erro, "arquivo")


def test_tipo_declarado_diferente_do_conteudo_e_recusado() -> None:
    erro = _erro_de_documento(_arquivo("a.png", PNG_VALIDO, "application/pdf"))

    assert "tipo declarado" in _mensagem(erro, "arquivo")


def test_sem_arquivo_pede_um_documento() -> None:
    with pytest.raises(BusinessError) as exc:
        validar_e_salvar_anexo(None, contexto="documentos", campo="arquivo", rotulo="documento")

    assert _mensagem(exc.value, "arquivo") == "Envie um arquivo de documento válido."


def test_sem_os_argumentos_novos_o_campo_e_o_texto_continuam_os_do_comprovante() -> None:
    with pytest.raises(BusinessError) as exc:
        validar_e_salvar_anexo(_arquivo("v.pdf", b"", "application/pdf"), contexto="pagamentos")
    with pytest.raises(BusinessError) as exc_grande:
        validar_e_salvar_anexo(
            _arquivo("g.pdf", PDF_VALIDO + b"0" * TAMANHO_MAXIMO_ANEXO, "application/pdf"),
            contexto="pagamentos",
        )
    with pytest.raises(BusinessError) as exc_nulo:
        validar_e_salvar_anexo(None, contexto="pagamentos")

    assert _mensagem(exc.value, "comprovante") == "O arquivo enviado está vazio."
    assert _mensagem(exc_grande.value, "comprovante") == "O comprovante excede o limite de 5 MB."
    assert _mensagem(exc_nulo.value, "comprovante") == "Envie um arquivo de comprovante válido."


def test_resposta_de_chave_inexistente_usa_o_rotulo() -> None:
    with pytest.raises(BusinessError) as exc:
        resposta_anexo(
            chave="documentos/nao-existe.pdf", nome="x.pdf", mime="application/pdf", rotulo="documento"
        )
    with pytest.raises(BusinessError) as exc_padrao:
        resposta_anexo(chave="comprovantes/nao-existe.pdf", nome="x.pdf", mime="application/pdf")

    assert exc.value.status == 404
    assert exc.value.message == "Documento não encontrado."
    assert exc_padrao.value.message == "Comprovante não encontrado."
