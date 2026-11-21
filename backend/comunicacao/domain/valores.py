"""Os valores fixos de `comunicacao`: tipos, situações e reações. Não importam framework."""

from enum import StrEnum


class TipoDeComunicado(StrEnum):
    COMUNICADO = "COMUNICADO"
    PAUTA = "PAUTA"


class SituacaoDoComunicado(StrEnum):
    PUBLICADO = "PUBLICADO"
    DESPUBLICADO = "DESPUBLICADO"


class SituacaoDoComentario(StrEnum):
    VISIVEL = "VISIVEL"
    OCULTO = "OCULTO"


class TipoDeReacao(StrEnum):
    CIENTE = "CIENTE"
    DE_ACORDO = "DE_ACORDO"
    DUVIDA = "DUVIDA"
    COMEMORACAO = "COMEMORACAO"


class TipoDeDocumento(StrEnum):
    DOCUMENTO = "DOCUMENTO"
    ATA = "ATA"


class SituacaoDoDocumento(StrEnum):
    VIGENTE = "VIGENTE"
    ARQUIVADO = "ARQUIVADO"
