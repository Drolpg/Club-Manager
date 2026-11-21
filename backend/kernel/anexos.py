"""Validação, gravação opaca e entrega segura de anexos via STORAGES["default"] (ADR-014, CA-20)."""

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse

from kernel.errors import BusinessError

TAMANHO_MAXIMO_ANEXO = 5 * 1024 * 1024

_CONTEXTO_VALIDO = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_EXT_PARA_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_MIME_PARA_EXT = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


@dataclass(frozen=True)
class AnexoSalvo:
    """Referência e metadados técnicos de um anexo gravado no armazenamento padrão."""

    chave: str
    nome: str
    mime: str
    tamanho: int


def _erro_anexo(mensagem: str, campo: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR",
        "Os dados enviados são inválidos.",
        status=400,
        details={campo: [mensagem]},
    )


def _detectar_mime_por_assinatura(dados: bytes) -> str | None:
    if dados.startswith(b"%PDF-"):
        return "application/pdf"
    if dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if dados.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(dados) >= 12 and dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


def _sanitizar_nome(nome_original: str | None, ext_padrao: str) -> str:
    bruto = (nome_original or "").replace("\\", "/")
    base = os.path.basename(bruto).strip()
    limpo = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    limpo = re.sub(r"_+", "_", limpo).strip("._")
    if not limpo:
        return f"anexo.{ext_padrao}"
    return limpo[:150]


def _conferir_declaracao(
    nome_original: str | None, content_type: str | None, mime_real: str, campo: str
) -> None:
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if ct and ct != "application/octet-stream" and ct != mime_real:
        raise _erro_anexo("O tipo declarado do arquivo não corresponde ao conteúdo enviado.", campo)
    if nome_original:
        ext = Path(nome_original).suffix.lower()
        if ext and _EXT_PARA_MIME.get(ext) != mime_real:
            raise _erro_anexo("A extensão do arquivo não é permitida ou não bate com o conteúdo.", campo)


def validar_e_salvar_anexo(
    arquivo: Any, *, contexto: str, campo: str = "comprovante", rotulo: str = "comprovante"
) -> AnexoSalvo:
    """Valida tamanho, assinatura de bytes e tipo do arquivo, salvando com chave opaca.

    `campo` é a chave dos erros e `rotulo` é como as mensagens chamam o arquivo. Os padrões são os do
    comprovante (M6 e M7); outros contextos, como os documentos, passam os seus.
    """
    if not _CONTEXTO_VALIDO.fullmatch(contexto):
        raise ValueError(f"Contexto de anexo inválido: {contexto!r}.")
    if arquivo is None or not hasattr(arquivo, "read"):
        raise _erro_anexo(f"Envie um arquivo de {rotulo} válido.", campo)

    tamanho_declarado = getattr(arquivo, "size", None)
    if isinstance(tamanho_declarado, int) and tamanho_declarado > TAMANHO_MAXIMO_ANEXO:
        raise _erro_anexo(f"O {rotulo} excede o limite de 5 MB.", campo)

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)
    conteudo: bytes = arquivo.read(TAMANHO_MAXIMO_ANEXO + 1)
    if not conteudo:
        raise _erro_anexo("O arquivo enviado está vazio.", campo)
    if len(conteudo) > TAMANHO_MAXIMO_ANEXO:
        raise _erro_anexo(f"O {rotulo} excede o limite de 5 MB.", campo)

    mime_real = _detectar_mime_por_assinatura(conteudo)
    if mime_real is None:
        raise _erro_anexo("Formato não permitido. Envie PDF, PNG, JPEG ou WebP.", campo)

    nome_original = getattr(arquivo, "name", None)
    content_type = getattr(arquivo, "content_type", None)
    _conferir_declaracao(nome_original, content_type, mime_real, campo)

    ext = _MIME_PARA_EXT[mime_real]
    nome_sanitizado = _sanitizar_nome(nome_original, ext)
    chave = f"{contexto}/{uuid.uuid7()}.{ext}"
    chave_salva = default_storage.save(chave, ContentFile(conteudo))
    return AnexoSalvo(chave=chave_salva, nome=nome_sanitizado, mime=mime_real, tamanho=len(conteudo))


def resposta_anexo(*, chave: str, nome: str, mime: str, rotulo: str = "comprovante") -> HttpResponse:
    """Lê o anexo pela chave interna e devolve HTTP segura sem execução no navegador."""
    if not chave or not default_storage.exists(chave):
        raise BusinessError("NOT_FOUND", f"{rotulo.capitalize()} não encontrado.", status=404)
    with default_storage.open(chave, "rb") as stream:
        dados = stream.read()
    nome_seguro = re.sub(r'["\r\n\\;/]', "_", nome)[:150] or rotulo
    resposta = HttpResponse(dados, content_type=mime)
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    resposta["Content-Disposition"] = f'inline; filename="{nome_seguro}"'
    return resposta
