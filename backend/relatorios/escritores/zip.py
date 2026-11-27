"""Escritor de ZIP, para "Meus dados" (três CSV num arquivo só)."""

import io
import zipfile


def escrever_zip(arquivos: list[tuple[str, bytes]]) -> bytes:
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", compression=zipfile.ZIP_DEFLATED) as pacote:
        for nome, conteudo in arquivos:
            pacote.writestr(nome, conteudo)
    return saida.getvalue()
