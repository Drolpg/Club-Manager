"""Os códigos de erro de `eventos` (spec técnica do M8, tabela de erros). São contrato com os clientes."""

from kernel.errors import BusinessError

_MENSAGENS = {
    "PERMISSION_DENIED": (403, "Você não tem permissão para fazer isso."),
    "NOT_FOUND": (404, "Não encontrado."),
    "EVENTO_ENCERRADO": (422, "O evento já foi realizado ou cancelado e não muda mais."),
    "NAO_ESTA_RECUSADO": (422, "Só se reabre um evento recusado."),
    "EVENTO_SEM_CUSTO": (422, "Este evento não envolve custo: não tem orçamento."),
    "ORCAMENTO_JA_VINCULADO": (422, "Este evento já tem um orçamento."),
    "NAO_ESTA_PUBLICADO": (422, "O evento não está publicado."),
    "DATA_FUTURA": (422, "A data em que o evento aconteceu não pode estar no futuro."),
    "CATEGORIA_JA_EXISTE": (409, "Já existe uma categoria de evento com esse nome."),
}


def erro(codigo: str, mensagem: str | None = None) -> BusinessError:
    status, padrao = _MENSAGENS[codigo]
    return BusinessError(codigo, mensagem or padrao, status=status)


def invalido(erros: dict[str, list[str]]) -> BusinessError:
    return BusinessError("VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details=erros)
