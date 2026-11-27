"""Gerar o arquivo de um pedido de relatório, chamado só pela tarefa (spec técnica, "Gerar"; ADR-006).

Idempotente: só o pedido na fila começa a gerar, e só o que ainda está gerando fica pronto (CA-06). A chave do
arquivo é a do pedido, então uma nova tentativa sobrescreve em vez de deixar órfão (D1). Qualquer erro vira
`FALHOU` com aviso, e o log leva só o ID do pedido e a classe do erro, nunca a mensagem (CA-07).
"""

import importlib
import logging
import re
import time
import unicodedata
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection, transaction
from django.utils import timezone

from acesso import public as acesso
from relatorios import tipos
from relatorios.domain.documento import Cabecalho, Documento
from relatorios.domain.pedido import Formato
from relatorios.escritores.csv import escrever_csv
from relatorios.escritores.pdf import escrever_pdf
from relatorios.escritores.zip import escrever_zip
from relatorios.models import PedidoDeRelatorio
from relatorios.services import avisos, pedidos

logger = logging.getLogger(__name__)

PREFIXO = "relatorios/"
_MIME = {"pdf": "application/pdf", "csv": "text/csv; charset=utf-8", "zip": "application/zip"}


@contextmanager
def _leitura_do_mesmo_instante() -> Iterator[None]:
    """Todos os números do arquivo do mesmo instante (D2, R9).

    O PostgreSQL só aceita mudar o nível como primeiro comando da transação; dentro de um bloco atômico (os
    testes), a leitura segue nele.
    """
    if connection.in_atomic_block:
        yield
        return
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        yield


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "relatorio"


def montar_documentos(
    tipo: tipos.TipoDeRelatorio, pedido: PedidoDeRelatorio, contexto: tipos.Contexto
) -> list[Documento]:
    return tipo.montar(dict(pedido.parametros), contexto)


def _nomes_no_zip(documentos: list[Documento]) -> list[str]:
    nomes: list[str] = []
    for documento in documentos:
        base = _slug(documento.titulo)
        nomes.append(base if base not in nomes else f"{base}-{len(nomes) + 1}")
    return [f"{nome}.csv" for nome in nomes]


def _escrever(documentos: list[Documento], formato: Formato, cabecalho: Cabecalho) -> tuple[bytes, str]:
    """Um documento sai no formato pedido; mais de um ("Meus dados") sai num ZIP de CSV."""
    if len(documentos) > 1:
        arquivos = [
            (nome, escrever_csv(documento, cabecalho))
            for nome, documento in zip(_nomes_no_zip(documentos), documentos, strict=True)
        ]
        return escrever_zip(arquivos), "zip"
    [documento] = documentos
    if formato == Formato.PDF:
        return escrever_pdf(documento, cabecalho), "pdf"
    return escrever_csv(documento, cabecalho), "csv"


def _gravar(chave: str, conteudo: bytes) -> None:
    """Sobrescreve: o armazenamento daria outro nome em vez de substituir uma chave que já existe."""
    if default_storage.exists(chave):
        default_storage.delete(chave)
    if default_storage.save(chave, ContentFile(conteudo)) != chave:
        raise RuntimeError("O armazenamento gravou o relatório noutra chave.")


def _descartar(chave: str | None) -> None:
    if chave is not None and default_storage.exists(chave):
        default_storage.delete(chave)


def _memoria_max_kb() -> int | None:
    """O pico de memória do processo (risco 6). Só existe no Linux, onde o worker roda."""
    try:
        resource = importlib.import_module("resource")
    except ImportError:
        return None
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def _falhar(pedido_id: uuid.UUID, erro: Exception) -> None:
    with transaction.atomic():
        falhou = pedidos.falhar(pedido_id, "ERRO_NA_GERACAO")
        if falhou is not None:
            avisos.falhou(falhou)
    logger.warning(
        "relatorios.geracao.falhou", extra={"pedido_id": str(pedido_id), "erro": type(erro).__name__}
    )


def gerar(pedido_id: uuid.UUID) -> None:
    pedido = pedidos.iniciar_geracao(pedido_id)
    if pedido is None:
        return
    inicio = time.monotonic()
    chave: str | None = None
    try:
        tipo = tipos.obter(pedido.tipo)
        if tipo is None:
            raise LookupError("Tipo de relatório não registrado.")
        agora = timezone.now()
        contexto = tipos.Contexto(
            hoje=timezone.localdate(agora), agora=agora, usuario_id=pedido.pedido_por_id
        )
        with _leitura_do_mesmo_instante():
            documentos = montar_documentos(tipo, pedido, contexto)
            quem = acesso.usuario_por_id(pedido.pedido_por_id)
        cabecalho = Cabecalho(
            gerado_em=timezone.localtime(agora), gerado_por=quem.nome if quem is not None else "—"
        )
        conteudo, extensao = _escrever(documentos, Formato(pedido.formato), cabecalho)
        chave = f"{PREFIXO}{pedido.id}.{extensao}"
        _gravar(chave, conteudo)
    except Exception as erro:
        _descartar(chave)
        _falhar(pedido.id, erro)
        return

    arquivo = pedidos.Arquivo(
        chave=chave,
        nome=f"{_slug(tipo.nome)}-{timezone.localtime(pedido.pedido_em):%Y%m%d-%H%M}.{extensao}",
        mime=_MIME[extensao],
        tamanho=len(conteudo),
    )
    with transaction.atomic():
        pronto = pedidos.concluir(pedido.id, arquivo)
        if pronto is not None:
            avisos.pronto(pronto)
    if pronto is None:
        # Deixou de estar gerando no meio (a rotina o deu como parado): o arquivo não fica.
        _descartar(chave)
        return
    logger.info(
        "relatorios.geracao.concluida",
        extra={
            "pedido_id": str(pedido.id),
            "tipo": pedido.tipo,
            "formato": pedido.formato,
            "duracao_ms": int((time.monotonic() - inicio) * 1000),
            "linhas": sum(len(tabela.linhas) for documento in documentos for tabela in documento.tabelas),
            "memoria_max_kb": _memoria_max_kb(),
        },
    )
