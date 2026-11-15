"""Códigos de erro de negócio do módulo financeiro e seus status HTTP."""

from typing import Any

from kernel.errors import BusinessError

_MENSAGENS: dict[str, tuple[int, str]] = {
    "PERMISSION_DENIED": (403, "Você não tem permissão para esta ação."),
    "SO_O_DEVEDOR": (403, "Apenas o devedor da cobrança pode executar esta ação."),
    "DEVEDOR_NAO_VALIDA": (403, "O devedor não pode validar nem rejeitar o próprio pagamento."),
    "DEVEDOR_NAO_DECIDE": (403, "O devedor não pode decidir a própria cobrança ou dívida."),
    "REGISTRADOR_NAO_VALIDA": (403, "Quem registrou a entrada não pode validá-la nem rejeitá-la."),
    "NOT_FOUND": (404, "Registro financeiro não encontrado."),
    "CATEGORIA_JA_EXISTE": (
        409,
        "Já existe uma categoria financeira com esse nome nesta natureza. Se inativa, reative-a.",
    ),
    "CHAVE_PIX_PADRAO_NAO_CONFIGURADA": (
        422,
        "Nenhuma chave Pix padrão ativa está configurada para o clube.",
    ),
    "VALOR_INVALIDO": (422, "O valor precisa ser maior que zero."),
    "VENCIMENTO_NO_PASSADO": (422, "O vencimento não pode estar no passado."),
    "PARCELAS_INVALIDAS": (422, "Informe ao menos uma parcela válida para a renegociação."),
    "DEVEDOR_INATIVO": (422, "O diretor selecionado precisa estar ativo."),
    "RECEBEDOR_INVALIDO": (422, "O recebedor em mão precisa ser outro usuário ativo."),
    "CATEGORIA_INATIVA": (422, "A categoria financeira selecionada está inativa."),
    "CHAVE_PIX_INATIVA": (422, "A chave Pix selecionada está inativa."),
    "JA_ESTA_ATIVO": (422, "Este cadastro já está ativo."),
    "JA_ESTA_INATIVO": (422, "Este cadastro já está inativo."),
    "SUSPENSAO_JA_ENCERRADA": (422, "Esta suspensão já está encerrada."),
    "NAO_ACEITA_PAGAMENTO": (422, "Esta cobrança não aceita pagamento nesta situação."),
    "NAO_ESTA_EM_VALIDACAO": (422, "Não há pagamento ou entrada aguardando validação."),
    "NAO_ACEITA_QUESTIONAMENTO": (422, "Esta cobrança não aceita questionamento nesta situação."),
    "QUESTIONAMENTO_JA_ABERTO": (422, "Esta cobrança já possui um questionamento em aberto."),
    "SEM_QUESTIONAMENTO_ABERTO": (422, "Esta cobrança não possui questionamento em aberto."),
    "NAO_PODE_ISENTAR": (422, "Apenas cobranças abertas ou atrasadas podem ser isentas."),
    "NAO_PODE_CANCELAR": (422, "Apenas cobranças abertas ou atrasadas podem ser canceladas."),
    "SEM_CONVOCACAO_ABERTA": (422, "Esta cobrança não possui convocação aberta para decisão."),
    "NAO_ESTA_ATRASADA": (422, "Esta ação exige que a cobrança esteja atrasada."),
    "NAO_ESTA_PAGA": (422, "O recibo só fica disponível depois que a cobrança é paga."),
    "COBRANCA_JA_GERADA": (422, "A cobrança desta recorrência já foi gerada para esta competência."),
    "SO_O_SOLICITANTE": (403, "Apenas o solicitante da saída pode executar esta ação."),
    "SOLICITANTE_NAO_LIQUIDA": (403, "O solicitante não pode liquidar a própria saída."),
    "NAO_AGUARDA_ENVIO": (422, "Esta saída não aguarda envio de recurso no momento."),
    "VALOR_ACIMA_DO_APROVADO": (422, "O valor informado ultrapassa o limite aprovado para esta saída."),
    "NAO_AGUARDA_PRESTACAO": (422, "Esta saída não está aguardando prestação de contas."),
    "NAO_ESTA_EM_CONFERENCIA": (422, "Esta ação exige que a saída esteja em conferência."),
    "NAO_ACEITA_DEVOLUCAO": (422, "Esta saída não aceita devolução nesta situação."),
    "DEVOLUCAO_ACIMA_DO_ENVIADO": (422, "A soma das devoluções não pode ultrapassar o total enviado."),
    "COMPLEMENTO_JA_EM_ANDAMENTO": (422, "Já existe um pedido de complemento em andamento para esta saída."),
    "NAO_HA_EXCESSO_PARA_COMPLEMENTO": (
        422,
        "Só cabe complemento quando o gasto informado supera o total enviado.",
    ),
    "DEVOLUCAO_PENDENTE": (422, "Há devolução aguardando validação; conclua antes de liquidar."),
    "DIFERENCA_NAO_ACERTADA": (422, "A diferença da prestação ainda não está acertada para liquidação."),
    "NAO_PODE_ESTORNAR": (422, "Este registro não pode ser estornado nesta situação."),
}


def erro(codigo: str, *, details: Any = None, mensagem: str | None = None) -> BusinessError:
    status, padrao = _MENSAGENS[codigo]
    return BusinessError(codigo, mensagem or padrao, status=status, details=details)


def erro_validacao(campo: str, mensagem: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR",
        "Os dados enviados são inválidos.",
        status=400,
        details={campo: [mensagem]},
    )
