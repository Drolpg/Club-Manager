"""Regras puras de cálculo, envio, prestação de contas, liquidação e lembretes de saídas."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from financeiro.domain.transicoes import SituacaoSaida
from kernel.dinheiro import Dinheiro

PRAZO_LEMBRETE_PRESTACAO_DIAS = 5
PRAZO_VENCIMENTO_PRESTACAO_DIAS = 7
MAX_TAMANHO_DESCRICAO_ITEM = 160
_ZERO = Decimal("0.00")


class ErroDeRegraSaida(ValueError):
    """Violação pura de invariante ou validação de domínio de gastos e saídas."""

    def __init__(self, codigo: str, mensagem: str, *, campo: str | None = None) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.campo = campo


@dataclass(frozen=True)
class ItemDeGastoNormalizado:
    descricao: str
    valor: Decimal


@dataclass(frozen=True)
class LiquidacaoResultado:
    valor_nao_reembolsado: Decimal
    sobra: Decimal


@dataclass(frozen=True)
class LembretePrestacao:
    enviar_lembrete_5_dias: bool
    enviar_aviso_7_dias: bool


def validar_itens_de_gasto(
    itens: Sequence[object],
) -> tuple[list[ItemDeGastoNormalizado], Decimal]:
    """Valida itens estruturados de gasto e devolve a lista normalizada com a soma decimal exata."""
    if isinstance(itens, str | bytes) or not itens:
        raise ErroDeRegraSaida("VALIDATION_ERROR", "Informe ao menos um item de gasto.", campo="itens")

    normalizados: list[ItemDeGastoNormalizado] = []
    total = _ZERO

    for item in itens:
        if not isinstance(item, Mapping):
            raise ErroDeRegraSaida(
                "VALIDATION_ERROR",
                "Cada item precisa informar descrição e valor.",
                campo="itens",
            )
        descricao_bruta = item.get("descricao")
        if not isinstance(descricao_bruta, str):
            raise ErroDeRegraSaida(
                "VALIDATION_ERROR",
                "A descrição de cada item precisa ser texto.",
                campo="itens",
            )
        descricao = descricao_bruta.strip()
        if not descricao:
            raise ErroDeRegraSaida(
                "VALIDATION_ERROR",
                "A descrição do item não pode ficar vazia.",
                campo="itens",
            )
        if len(descricao) > MAX_TAMANHO_DESCRICAO_ITEM:
            raise ErroDeRegraSaida(
                "VALIDATION_ERROR",
                f"A descrição do item deve ter no máximo {MAX_TAMANHO_DESCRICAO_ITEM} caracteres.",
                campo="itens",
            )
        valor_bruto = item.get("valor")
        try:
            valor = Dinheiro(valor_bruto).quantia  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ErroDeRegraSaida("VALIDATION_ERROR", str(exc), campo="itens") from exc
        if valor <= _ZERO:
            raise ErroDeRegraSaida(
                "VALIDATION_ERROR",
                "Cada item precisa ter valor maior que zero.",
                campo="itens",
            )
        normalizados.append(ItemDeGastoNormalizado(descricao=descricao, valor=valor))
        total += valor

    return normalizados, total


def _validar_valor_e_comprovante_envio(valor: Decimal, *, tem_comprovante: bool) -> None:
    if not tem_comprovante:
        raise ErroDeRegraSaida(
            "VALIDATION_ERROR",
            "Anexe o comprovante da transferência realizada.",
            campo="comprovante",
        )
    if valor <= _ZERO:
        raise ErroDeRegraSaida("VALOR_INVALIDO", "O valor do envio precisa ser maior que zero.")


def validar_envio_inicial(
    *,
    situacao: SituacaoSaida,
    valor: Decimal,
    valor_aprovado: Decimal,
    tem_comprovante: bool,
) -> None:
    """Valida a remessa inicial da saída (D-15: envio único até o valor aprovado)."""
    if situacao != SituacaoSaida.AGUARDANDO_ENVIO:
        raise ErroDeRegraSaida(
            "NAO_AGUARDA_ENVIO",
            "Esta saída já teve recurso enviado e não aceita novo envio fora de complemento.",
        )
    _validar_valor_e_comprovante_envio(valor, tem_comprovante=tem_comprovante)
    if valor > valor_aprovado:
        raise ErroDeRegraSaida(
            "VALOR_ACIMA_DO_APROVADO",
            "O valor enviado não pode ultrapassar o valor aprovado para a saída.",
        )


def validar_envio_complemento(
    *,
    situacao: SituacaoSaida,
    valor: Decimal,
    valor_aprovado: Decimal,
    complementos_aprovados: Decimal,
    total_ja_enviado: Decimal,
    tem_complemento_aprovado_pendente: bool,
    tem_comprovante: bool,
) -> None:
    """Valida o envio vinculado a um complemento aprovado (INV-SAI-02, P1)."""
    if (
        situacao not in (SituacaoSaida.RECURSO_ENVIADO, SituacaoSaida.EM_CONFERENCIA)
        or not tem_complemento_aprovado_pendente
    ):
        raise ErroDeRegraSaida(
            "NAO_AGUARDA_ENVIO",
            "Não há complemento aprovado aguardando envio nesta saída.",
        )
    _validar_valor_e_comprovante_envio(valor, tem_comprovante=tem_comprovante)
    saldo_disponivel = (valor_aprovado + complementos_aprovados) - total_ja_enviado
    if valor > saldo_disponivel:
        raise ErroDeRegraSaida(
            "VALOR_ACIMA_DO_APROVADO",
            "O total enviado ultrapassaria o limite aprovado com os complementos.",
        )


def validar_devolucao_de_sobra(
    *,
    situacao: SituacaoSaida,
    valor: Decimal,
    total_enviado: Decimal,
    total_devolvido_ativo: Decimal,
) -> None:
    """Garante que devoluções ativas (validadas ou em validação) nunca passem do enviado (INV-ENT-03)."""
    if situacao not in (SituacaoSaida.RECURSO_ENVIADO, SituacaoSaida.EM_CONFERENCIA):
        raise ErroDeRegraSaida(
            "NAO_ACEITA_DEVOLUCAO",
            "Só é possível devolver sobra depois do envio do recurso e antes da liquidação.",
        )
    if valor <= _ZERO:
        raise ErroDeRegraSaida("VALOR_INVALIDO", "O valor da devolução precisa ser maior que zero.")
    if total_devolvido_ativo + valor > total_enviado:
        raise ErroDeRegraSaida(
            "DEVOLUCAO_ACIMA_DO_ENVIADO",
            "A soma das devoluções ultrapassaria o total enviado para esta saída.",
        )


def validar_pedido_complemento(
    *,
    situacao: SituacaoSaida,
    valor_prestacao: Decimal | None,
    total_enviado: Decimal,
    tem_complemento_em_andamento: bool,
) -> None:
    """Garante no máximo um complemento em andamento por vez e apenas com gasto acima do enviado (P12)."""
    if situacao != SituacaoSaida.EM_CONFERENCIA:
        raise ErroDeRegraSaida(
            "NAO_ESTA_EM_CONFERENCIA",
            "O complemento só pode ser pedido enquanto a saída está em conferência.",
        )
    if tem_complemento_em_andamento:
        raise ErroDeRegraSaida(
            "COMPLEMENTO_JA_EM_ANDAMENTO",
            "Já existe um pedido de complemento em andamento para esta saída.",
        )
    if valor_prestacao is None or valor_prestacao <= total_enviado:
        raise ErroDeRegraSaida(
            "NAO_HA_EXCESSO_PARA_COMPLEMENTO",
            "O valor gasto informado precisa superar o total enviado para pedir complemento.",
        )


def avaliar_liquidacao(
    *,
    situacao: SituacaoSaida,
    valor_prestacao: Decimal,
    total_enviado: Decimal,
    total_devolvido_validado: Decimal,
    tem_devolucao_em_validacao: bool,
    tem_complemento_em_andamento: bool,
    tem_complemento_aprovado_sem_envio: bool,
    justificativa: str,
) -> LiquidacaoResultado:
    """Valida invariantes de fechamento e calcula valor não reembolsado (INV-SAI-05, Decisão 2)."""
    if situacao != SituacaoSaida.EM_CONFERENCIA:
        raise ErroDeRegraSaida(
            "NAO_ESTA_EM_CONFERENCIA",
            "Apenas saídas em conferência podem ser liquidadas.",
        )
    if tem_devolucao_em_validacao:
        raise ErroDeRegraSaida(
            "DEVOLUCAO_PENDENTE",
            "Há devolução aguardando validação; conclua a validação antes de liquidar.",
        )
    if tem_complemento_em_andamento or tem_complemento_aprovado_sem_envio:
        raise ErroDeRegraSaida(
            "DIFERENCA_NAO_ACERTADA",
            "Há complemento pendente de decisão ou envio antes da liquidação.",
        )

    sobra = total_enviado - valor_prestacao
    if sobra > _ZERO:
        if total_devolvido_validado != sobra:
            raise ErroDeRegraSaida(
                "DIFERENCA_NAO_ACERTADA",
                "A diferença não utilizada precisa estar devolvida e validada para liquidar.",
            )
        return LiquidacaoResultado(valor_nao_reembolsado=_ZERO, sobra=sobra)

    if sobra == _ZERO:
        if total_devolvido_validado != _ZERO:
            raise ErroDeRegraSaida(
                "DIFERENCA_NAO_ACERTADA",
                "Há devolução validada incompatível com o valor gasto informado.",
            )
        return LiquidacaoResultado(valor_nao_reembolsado=_ZERO, sobra=_ZERO)

    # Gasto maior que o enviado (`sobra < 0`): sem sobra a devolver; excesso vira não reembolsado.
    if total_devolvido_validado != _ZERO:
        raise ErroDeRegraSaida(
            "DIFERENCA_NAO_ACERTADA",
            "Estorne a devolução incompatível antes de liquidar gasto acima do enviado.",
        )
    if not justificativa.strip():
        raise ErroDeRegraSaida(
            "VALIDATION_ERROR",
            "Informe a justificativa para liquidar com diferença não reembolsada.",
            campo="justificativa",
        )
    return LiquidacaoResultado(valor_nao_reembolsado=-sobra, sobra=sobra)


def calcular_valor_realizado_saida(total_enviado: Decimal, total_devolvido_validado: Decimal) -> Decimal:
    """Valor efetivamente desembolsado pelo clube nesta saída (CA-32)."""
    realizado = total_enviado - total_devolvido_validado
    return realizado if realizado > _ZERO else _ZERO


def prestacao_em_atraso(*, situacao: SituacaoSaida, primeiro_envio_em: date | None, hoje: date) -> bool:
    """Indica se a saída aguardando prestação já atingiu o vencimento de 7 dias (RF-126)."""
    if situacao != SituacaoSaida.RECURSO_ENVIADO or primeiro_envio_em is None:
        return False
    return hoje >= primeiro_envio_em + timedelta(days=PRAZO_VENCIMENTO_PRESTACAO_DIAS)


def avaliar_lembretes_prestacao(
    *,
    situacao: SituacaoSaida,
    primeiro_envio_em: date | None,
    hoje: date,
    lembrete_5_dias_em: date | None,
    aviso_7_dias_em: date | None,
) -> LembretePrestacao:
    """Decide de forma idempotente se os avisos de 5 e 7 dias devem ser disparados hoje."""
    if situacao != SituacaoSaida.RECURSO_ENVIADO or primeiro_envio_em is None:
        return LembretePrestacao(enviar_lembrete_5_dias=False, enviar_aviso_7_dias=False)

    enviar_5 = (
        hoje >= primeiro_envio_em + timedelta(days=PRAZO_LEMBRETE_PRESTACAO_DIAS)
        and lembrete_5_dias_em is None
    )
    enviar_7 = (
        hoje >= primeiro_envio_em + timedelta(days=PRAZO_VENCIMENTO_PRESTACAO_DIAS)
        and aviso_7_dias_em is None
    )
    return LembretePrestacao(enviar_lembrete_5_dias=enviar_5, enviar_aviso_7_dias=enviar_7)
