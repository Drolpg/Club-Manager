"""Documentos e atas: enviar, registrar a ata, nova versão, arquivar e desarquivar (RF-139 a RF-141).

O arquivo vai para o armazenamento por `kernel.anexos`, com o campo e o rótulo de "documento". Cada
versão fica (nunca se apaga o arquivo de uma substituída) e só a de `numero = versao_atual` é a vigente.
A auditoria leva a referência do arquivo, nunca o conteúdo.
"""

import uuid
from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from auditoria import public as auditoria
from comunicacao.domain.autorizacao import Comando, avaliar
from comunicacao.domain.regras import reuniao_no_futuro, validar_ata, validar_documento, validar_motivo
from comunicacao.domain.valores import SituacaoDoDocumento, TipoDeDocumento
from comunicacao.erros import erro, invalido
from comunicacao.models import CategoriaDeDocumento, Documento, VersaoDeDocumento
from comunicacao.services.autorizacao import Quem, exigir, exigir_leitura_de_gestao, quem
from kernel import anexos
from kernel.anexos import AnexoSalvo

ITEM = "documento"
_CONTEXTO = "documentos"


def _guardar_arquivo(arquivo: Any) -> AnexoSalvo:
    return anexos.validar_e_salvar_anexo(arquivo, contexto=_CONTEXTO, campo="arquivo", rotulo="documento")


def _referencia(anexo: AnexoSalvo, numero: int) -> dict[str, Any]:
    """O que a auditoria guarda do arquivo: a chave e os metadados, nunca o conteúdo."""
    return {
        "versao": numero,
        "chave": anexo.chave,
        "nome": anexo.nome,
        "mime": anexo.mime,
        "tamanho": anexo.tamanho,
    }


def _categoria_ativa(categoria_id: uuid.UUID | None) -> CategoriaDeDocumento:
    categoria = CategoriaDeDocumento.objects.filter(pk=categoria_id).first() if categoria_id else None
    if categoria is None:
        raise invalido({"categoria_id": ["Escolha uma categoria de documento."]})
    if not categoria.ativa:
        raise erro("CATEGORIA_INATIVA")
    return categoria


def _criar_versao(
    documento: Documento, anexo: AnexoSalvo, ator_id: uuid.UUID, numero: int, motivo: str = ""
) -> VersaoDeDocumento:
    return VersaoDeDocumento.objects.create(
        documento=documento,
        numero=numero,
        chave=anexo.chave,
        nome=anexo.nome,
        mime=anexo.mime,
        tamanho=anexo.tamanho,
        motivo=motivo,
        enviada_por_id=ator_id,
    )


@transaction.atomic
def enviar_documento(
    ator_id: uuid.UUID,
    *,
    titulo: str,
    descricao: str = "",
    categoria_id: uuid.UUID | None,
    arquivo: Any,
) -> Documento:
    ator = quem(ator_id)
    exigir(avaliar(Comando.ENVIAR_DOCUMENTO, ator.fatos()))
    erros = validar_documento(titulo, descricao)
    if erros:
        raise invalido(erros)
    categoria = _categoria_ativa(categoria_id)
    anexo = _guardar_arquivo(arquivo)

    documento = Documento.objects.create(
        tipo=TipoDeDocumento.DOCUMENTO.value,
        titulo=titulo,
        descricao=descricao,
        categoria=categoria,
        categoria_nome=categoria.nome,
        enviado_por_id=ator_id,
    )
    _criar_versao(documento, anexo, ator_id, 1)
    auditoria.registrar(
        ator_id=ator_id,
        acao="DOCUMENTO_ENVIADO",
        item_tipo=ITEM,
        item_id=documento.id,
        dados=_referencia(anexo, 1) | {"categoria_id": str(categoria.id)},
    )
    return documento


@transaction.atomic
def registrar_ata(
    ator_id: uuid.UUID,
    *,
    titulo: str,
    descricao: str = "",
    data_da_reuniao: date | None,
    arquivo: Any,
) -> Documento:
    ator = quem(ator_id)
    exigir(avaliar(Comando.REGISTRAR_ATA, ator.fatos()))
    erros = validar_ata(titulo, descricao, data_da_reuniao)
    if erros:
        raise invalido(erros)
    if data_da_reuniao is not None and reuniao_no_futuro(data_da_reuniao, timezone.localdate()):
        raise erro("DATA_FUTURA")
    anexo = _guardar_arquivo(arquivo)

    ata = Documento.objects.create(
        tipo=TipoDeDocumento.ATA.value,
        titulo=titulo,
        descricao=descricao,
        data_da_reuniao=data_da_reuniao,
        enviado_por_id=ator_id,
    )
    _criar_versao(ata, anexo, ator_id, 1)
    auditoria.registrar(
        ator_id=ator_id,
        acao="ATA_REGISTRADA",
        item_tipo=ITEM,
        item_id=ata.id,
        dados=_referencia(anexo, 1) | {"data_da_reuniao": str(data_da_reuniao)},
    )
    return ata


def _bloquear(documento_id: uuid.UUID) -> Documento:
    """O documento com a linha bloqueada; quem lê gestão vê todos, inclusive os arquivados."""
    documento = Documento.objects.select_for_update().filter(pk=documento_id).first()
    if documento is None:
        raise erro("NOT_FOUND")
    return documento


def _bloquear_e_avaliar(ator: Quem, documento_id: uuid.UUID, comando: Comando) -> Documento:
    documento = _bloquear(documento_id)
    exigir(avaliar(comando, ator.fatos(documento=documento)))
    return documento


@transaction.atomic
def nova_versao(ator_id: uuid.UUID, documento_id: uuid.UUID, *, arquivo: Any, motivo: str) -> Documento:
    """A nova versão vira a vigente e a anterior continua intacta; a data da ata não muda (P24)."""
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    documento = _bloquear_e_avaliar(ator, documento_id, Comando.NOVA_VERSAO)
    erros = validar_motivo(motivo)
    if erros:
        raise invalido(erros)
    anexo = _guardar_arquivo(arquivo)

    numero = documento.versao_atual + 1
    _criar_versao(documento, anexo, ator_id, numero, motivo)
    documento.versao_atual = numero
    documento.save()
    auditoria.registrar(
        ator_id=ator_id,
        acao="VERSAO_ENVIADA",
        item_tipo=ITEM,
        item_id=documento.id,
        justificativa=motivo,
        dados=_referencia(anexo, numero),
    )
    return documento


def _mudar_situacao(
    ator_id: uuid.UUID, documento_id: uuid.UUID, comando: Comando, situacao: SituacaoDoDocumento, acao: str
) -> Documento:
    exigir_leitura_de_gestao(ator_id)
    ator = quem(ator_id)
    documento = _bloquear_e_avaliar(ator, documento_id, comando)
    documento.situacao = situacao.value
    documento.save()
    auditoria.registrar(ator_id=ator_id, acao=acao, item_tipo=ITEM, item_id=documento.id)
    return documento


@transaction.atomic
def arquivar(ator_id: uuid.UUID, documento_id: uuid.UUID) -> Documento:
    """Sai da lista padrão; continua vinculado e baixável (P8)."""
    return _mudar_situacao(
        ator_id, documento_id, Comando.ARQUIVAR, SituacaoDoDocumento.ARQUIVADO, "DOCUMENTO_ARQUIVADO"
    )


@transaction.atomic
def desarquivar(ator_id: uuid.UUID, documento_id: uuid.UUID) -> Documento:
    return _mudar_situacao(
        ator_id, documento_id, Comando.DESARQUIVAR, SituacaoDoDocumento.VIGENTE, "DOCUMENTO_DESARQUIVADO"
    )
