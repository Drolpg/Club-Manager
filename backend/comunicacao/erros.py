"""Os códigos de erro de `comunicacao` (spec técnica do M9, tabela de erros). São contrato com os clientes."""

from kernel.errors import BusinessError

_MENSAGENS = {
    "PERMISSION_DENIED": (403, "Você não tem permissão para fazer isso."),
    "NOT_FOUND": (404, "Não encontrado."),
    "COMUNICADO_NAO_PUBLICADO": (422, "O comunicado não está publicado."),
    "COMUNICADO_JA_PUBLICADO": (422, "O comunicado já está publicado."),
    "COMUNICADO_JA_DESPUBLICADO": (422, "O comunicado já está despublicado."),
    "JA_ESTA_FIXADO": (422, "O comunicado já está fixado."),
    "NAO_ESTA_FIXADO": (422, "O comunicado não está fixado."),
    "SEM_REACAO": (422, "Você não tem uma reação neste comunicado."),
    "COMENTARIO_JA_OCULTO": (422, "O comentário já está oculto."),
    "COMENTARIO_NAO_ESTA_OCULTO": (422, "O comentário não está oculto."),
    "DOCUMENTO_ARQUIVADO": (422, "O documento está arquivado."),
    "DOCUMENTO_JA_ARQUIVADO": (422, "O documento já está arquivado."),
    "DOCUMENTO_NAO_ESTA_ARQUIVADO": (422, "O documento não está arquivado."),
    "CATEGORIA_INATIVA": (422, "A categoria de documento está inativa."),
    "DATA_FUTURA": (422, "A data da reunião não pode estar no futuro."),
    "CATEGORIA_JA_EXISTE": (409, "Já existe uma categoria de documento com esse nome."),
}


def erro(codigo: str, mensagem: str | None = None) -> BusinessError:
    status, padrao = _MENSAGENS[codigo]
    return BusinessError(codigo, mensagem or padrao, status=status)


def invalido(erros: dict[str, list[str]]) -> BusinessError:
    return BusinessError("VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details=erros)
