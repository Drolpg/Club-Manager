"""Quem pode o quê no feed e nos documentos (spec técnica do M9, "Quem pode" e "Depois de quem pode").

Uma função só responde à rota, ao serviço e ao campo `acoes` dos detalhes. A ordem é leitura de gestão → quem
pode → situação, como no M8. Não importa Django, DRF nem Celery.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from comunicacao.domain.valores import (
    SituacaoDoComentario,
    SituacaoDoComunicado,
    SituacaoDoDocumento,
    TipoDeDocumento,
)

PERM_PUBLICAR = "comunicacao.publicar"
PERM_GERENCIAR = "comunicacao.gerenciar"
PERM_ENVIAR_DOCUMENTOS = "comunicacao.enviar_documentos"
PERM_REGISTRAR_ATAS = "comunicacao.registrar_atas"

PERMISSION_DENIED = "PERMISSION_DENIED"


class Comando(StrEnum):
    PUBLICAR = "publicar"
    EDITAR_COMUNICADO = "editar_comunicado"
    DESPUBLICAR = "despublicar"
    REPUBLICAR = "republicar"
    FIXAR = "fixar"
    DESAFIXAR = "desafixar"
    REAGIR = "reagir"
    RETIRAR_REACAO = "retirar_reacao"
    COMENTAR = "comentar"
    EDITAR_COMENTARIO = "editar_comentario"
    OCULTAR_COMENTARIO = "ocultar_comentario"
    REEXIBIR_COMENTARIO = "reexibir_comentario"
    ENVIAR_DOCUMENTO = "enviar_documento"
    REGISTRAR_ATA = "registrar_ata"
    NOVA_VERSAO = "nova_versao"
    ARQUIVAR = "arquivar"
    DESARQUIVAR = "desarquivar"


C = Comando

# Os comandos de cada detalhe, na ordem em que as telas os mostram.
COMANDOS_DO_COMUNICADO: tuple[Comando, ...] = (
    C.EDITAR_COMUNICADO,
    C.DESPUBLICAR,
    C.REPUBLICAR,
    C.FIXAR,
    C.DESAFIXAR,
    C.REAGIR,
    C.RETIRAR_REACAO,
    C.COMENTAR,
)
COMANDOS_DO_COMENTARIO: tuple[Comando, ...] = (
    C.EDITAR_COMENTARIO,
    C.OCULTAR_COMENTARIO,
    C.REEXIBIR_COMENTARIO,
)
COMANDOS_DO_DOCUMENTO: tuple[Comando, ...] = (C.NOVA_VERSAO, C.ARQUIVAR, C.DESARQUIVAR)


@dataclass(frozen=True)
class Fatos:
    """O que se sabe de quem age e do item. O que não vale para o comando fica no padrão."""

    ator_id: uuid.UUID
    le_gestao: bool
    pode_publicar: bool
    pode_gerenciar: bool
    pode_enviar_documentos: bool
    pode_registrar_atas: bool
    autor_do_comunicado_id: uuid.UUID | None = None
    situacao_do_comunicado: SituacaoDoComunicado | None = None
    fixado: bool = False
    tem_reacao_ativa: bool = False
    autor_do_comentario_id: uuid.UUID | None = None
    situacao_do_comentario: SituacaoDoComentario | None = None
    oculto_pela_gerencia: bool = False
    enviado_por_id: uuid.UUID | None = None
    tipo_do_documento: TipoDeDocumento | None = None
    situacao_do_documento: SituacaoDoDocumento | None = None


@dataclass(frozen=True)
class Avaliacao:
    pode: bool
    erro: str | None = None


_PODE = Avaliacao(True)


def _nao(erro: str) -> Avaliacao:
    return Avaliacao(False, erro)


def _e_autor_do_comunicado(fatos: Fatos) -> bool:
    return fatos.autor_do_comunicado_id is not None and fatos.ator_id == fatos.autor_do_comunicado_id


def _e_autor_do_comentario(fatos: Fatos) -> bool:
    return fatos.autor_do_comentario_id is not None and fatos.ator_id == fatos.autor_do_comentario_id


def _enviou_o_documento(fatos: Fatos) -> bool:
    return fatos.enviado_por_id is not None and fatos.ator_id == fatos.enviado_por_id


def _permissao_do_tipo(fatos: Fatos) -> bool:
    if fatos.tipo_do_documento == TipoDeDocumento.ATA:
        return fatos.pode_registrar_atas
    return fatos.pode_enviar_documentos


def ocultar_pela_gerencia(fatos: Fatos) -> bool:
    """Ocultar o comentário de outra pessoa é pela gerência (com motivo); o do próprio, não."""
    return not _e_autor_do_comentario(fatos)


def _quem_pode(comando: Comando, fatos: Fatos) -> bool:
    if comando == C.PUBLICAR:
        return fatos.pode_publicar
    if comando in (C.EDITAR_COMUNICADO, C.DESPUBLICAR, C.REPUBLICAR):
        return (_e_autor_do_comunicado(fatos) and fatos.pode_publicar) or fatos.pode_gerenciar
    if comando in (C.FIXAR, C.DESAFIXAR):
        return fatos.pode_gerenciar
    if comando == C.EDITAR_COMENTARIO:
        return _e_autor_do_comentario(fatos)
    if comando == C.OCULTAR_COMENTARIO:
        return _e_autor_do_comentario(fatos) or fatos.pode_gerenciar
    if comando == C.REEXIBIR_COMENTARIO:
        proprio = _e_autor_do_comentario(fatos) and not fatos.oculto_pela_gerencia
        return proprio or fatos.pode_gerenciar
    if comando == C.ENVIAR_DOCUMENTO:
        return fatos.pode_enviar_documentos
    if comando == C.REGISTRAR_ATA:
        return fatos.pode_registrar_atas
    if comando in (C.NOVA_VERSAO, C.ARQUIVAR, C.DESARQUIVAR):
        return (_enviou_o_documento(fatos) and _permissao_do_tipo(fatos)) or fatos.pode_gerenciar
    return True  # reagir, retirar a reação e comentar: quem lê a gestão


def _situacao_do_comunicado(comando: Comando, fatos: Fatos) -> str | None:
    publicado = fatos.situacao_do_comunicado == SituacaoDoComunicado.PUBLICADO
    if comando == C.DESPUBLICAR:
        return None if publicado else "COMUNICADO_JA_DESPUBLICADO"
    if comando == C.REPUBLICAR:
        return "COMUNICADO_JA_PUBLICADO" if publicado else None
    if comando == C.DESAFIXAR:
        return None if fatos.fixado else "NAO_ESTA_FIXADO"
    if comando == C.OCULTAR_COMENTARIO and fatos.pode_gerenciar:
        return None  # a gerência modera em qualquer situação do comunicado
    if comando in (
        C.EDITAR_COMUNICADO,
        C.FIXAR,
        C.REAGIR,
        C.RETIRAR_REACAO,
        C.COMENTAR,
        C.EDITAR_COMENTARIO,
        C.OCULTAR_COMENTARIO,
    ):
        if not publicado:
            return "COMUNICADO_NAO_PUBLICADO"
        if comando == C.FIXAR and fatos.fixado:
            return "JA_ESTA_FIXADO"
    return None


def _outra_situacao(comando: Comando, fatos: Fatos) -> str | None:
    if comando == C.RETIRAR_REACAO and not fatos.tem_reacao_ativa:
        return "SEM_REACAO"
    oculto = fatos.situacao_do_comentario == SituacaoDoComentario.OCULTO
    if comando == C.OCULTAR_COMENTARIO and oculto:
        return "COMENTARIO_JA_OCULTO"
    if comando == C.REEXIBIR_COMENTARIO and not oculto:
        return "COMENTARIO_NAO_ESTA_OCULTO"
    arquivado = fatos.situacao_do_documento == SituacaoDoDocumento.ARQUIVADO
    if comando == C.NOVA_VERSAO and arquivado:
        return "DOCUMENTO_ARQUIVADO"
    if comando == C.ARQUIVAR and arquivado:
        return "DOCUMENTO_JA_ARQUIVADO"
    if comando == C.DESARQUIVAR and not arquivado:
        return "DOCUMENTO_NAO_ESTA_ARQUIVADO"
    return None


def avaliar(comando: Comando, fatos: Fatos) -> Avaliacao:
    """Se o ator pode executar o comando agora e, se não, o código do erro."""
    if not fatos.le_gestao or not _quem_pode(comando, fatos):
        return _nao(PERMISSION_DENIED)
    erro = _situacao_do_comunicado(comando, fatos) or _outra_situacao(comando, fatos)
    return _nao(erro) if erro else _PODE


def pode_ver_comunicado(situacao: SituacaoDoComunicado, fatos: Fatos) -> bool:
    if not fatos.le_gestao:
        return False
    if situacao == SituacaoDoComunicado.PUBLICADO:
        return True
    return _e_autor_do_comunicado(fatos) or fatos.pode_gerenciar


def pode_ver_comentario(situacao: SituacaoDoComentario, fatos: Fatos) -> bool:
    if not fatos.le_gestao:
        return False
    if situacao == SituacaoDoComentario.VISIVEL:
        return True
    return _e_autor_do_comentario(fatos) or fatos.pode_gerenciar


def _acoes(comandos: tuple[Comando, ...], fatos: Fatos) -> tuple[Comando, ...]:
    return tuple(comando for comando in comandos if avaliar(comando, fatos).pode)


def acoes_do_comunicado(fatos: Fatos) -> tuple[Comando, ...]:
    return _acoes(COMANDOS_DO_COMUNICADO, fatos)


def acoes_do_comentario(fatos: Fatos) -> tuple[Comando, ...]:
    return _acoes(COMANDOS_DO_COMENTARIO, fatos)


def acoes_do_documento(fatos: Fatos) -> tuple[Comando, ...]:
    return _acoes(COMANDOS_DO_DOCUMENTO, fatos)
