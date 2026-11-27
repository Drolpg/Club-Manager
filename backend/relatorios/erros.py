"""Os códigos de erro de `relatorios` (spec técnica do perfil). São contrato com os clientes."""

from kernel.errors import BusinessError

_MENSAGENS = {
    "PERMISSION_DENIED": (403, "Você não tem permissão para fazer isso."),
    "NOT_FOUND": (404, "Usuário não encontrado."),
}


def erro(codigo: str) -> BusinessError:
    status, mensagem = _MENSAGENS[codigo]
    return BusinessError(codigo, mensagem, status=status)


def limite_invalido(maximo: int) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR",
        "Os dados enviados são inválidos.",
        status=400,
        details={"limite": [f"Use um número de 1 a {maximo}."]},
    )


def mes_invalido(mensagem: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details={"mes": [mensagem]}
    )


def campo_invalido(campo: str, mensagem: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details={campo: [mensagem]}
    )


def pedidos_em_andamento(maximo: int) -> BusinessError:
    return BusinessError(
        "PEDIDOS_EM_ANDAMENTO",
        f"Você já tem {maximo} relatórios na fila ou sendo gerados. Espere um terminar para pedir outro.",
        status=409,
    )
