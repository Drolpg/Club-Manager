"""Regras puras de autorização sobre cobranças, entradas e sigilo de comprovantes."""

import uuid
from dataclasses import dataclass

from financeiro.domain.transicoes import (
    ComandoCobranca,
    ComandoEntrada,
    SituacaoCobranca,
    SituacaoEntrada,
    transicao_cobranca_permitida,
    transicao_entrada_permitida,
)

PERM_COBRANCAS_CRIAR = "cobrancas.criar"
PERM_PAGAMENTOS_VALIDAR = "pagamentos.validar"
PERM_ENTRADAS_REGISTRAR = "entradas.registrar"
PERM_ENTRADAS_VALIDAR = "entradas.validar"
PERM_COBRANCAS_CANCELAR = "cobrancas.cancelar"
PERM_COBRANCAS_ISENTAR = "cobrancas.isentar"
PERM_QUESTIONAMENTOS_DECIDIR = "questionamentos.decidir"
PERM_DIVIDAS_DECIDIR = "dividas.decidir"
PERM_COBRANCAS_SUSPENDER = "cobrancas.suspender"


@dataclass(frozen=True)
class DecisaoAutorizacao:
    pode: bool
    codigo_erro: str | None = None
    http_status: int = 403
    mensagem: str = ""


_OK = DecisaoAutorizacao(pode=True)


def _negado(codigo: str, mensagem: str) -> DecisaoAutorizacao:
    return DecisaoAutorizacao(pode=False, codigo_erro=codigo, http_status=403, mensagem=mensagem)


@dataclass(frozen=True)
class FatosCobranca:
    ator_id: uuid.UUID
    ator_admin: bool
    ator_le_gestao: bool
    permissoes_ator: frozenset[str]
    devedor_id: uuid.UUID
    situacao: SituacaoCobranca
    tem_questionamento_aberto: bool
    tem_convocacao_aberta: bool


_COMANDOS_EXCLUSIVOS_DEVEDOR = frozenset(
    {
        ComandoCobranca.REGISTRAR_PAGAMENTO,
        ComandoCobranca.QUESTIONAR,
        ComandoCobranca.JUSTIFICAR_DIVIDA,
    }
)

_PERMISSAO_DO_COMANDO: dict[ComandoCobranca, str] = {
    ComandoCobranca.VALIDAR_PAGAMENTO: PERM_PAGAMENTOS_VALIDAR,
    ComandoCobranca.REJEITAR_PAGAMENTO: PERM_PAGAMENTOS_VALIDAR,
    ComandoCobranca.DECIDIR_QUESTIONAMENTO: PERM_QUESTIONAMENTOS_DECIDIR,
    ComandoCobranca.ISENTAR: PERM_COBRANCAS_ISENTAR,
    ComandoCobranca.CANCELAR: PERM_COBRANCAS_CANCELAR,
    ComandoCobranca.PERDOAR: PERM_DIVIDAS_DECIDIR,
    ComandoCobranca.RENEGOCIAR: PERM_DIVIDAS_DECIDIR,
    ComandoCobranca.MANTER_DIVIDA: PERM_DIVIDAS_DECIDIR,
}

_ORDEM_ACOES_COBRANCA: tuple[ComandoCobranca, ...] = (
    ComandoCobranca.REGISTRAR_PAGAMENTO,
    ComandoCobranca.VALIDAR_PAGAMENTO,
    ComandoCobranca.REJEITAR_PAGAMENTO,
    ComandoCobranca.QUESTIONAR,
    ComandoCobranca.DECIDIR_QUESTIONAMENTO,
    ComandoCobranca.ISENTAR,
    ComandoCobranca.CANCELAR,
    ComandoCobranca.JUSTIFICAR_DIVIDA,
    ComandoCobranca.PERDOAR,
    ComandoCobranca.RENEGOCIAR,
    ComandoCobranca.MANTER_DIVIDA,
)


def avaliar_cobranca(comando: ComandoCobranca, fatos: FatosCobranca) -> DecisaoAutorizacao:
    """Decide se o ator tem direito ao comando sobre a cobrança (independente da situação)."""
    eh_devedor = fatos.ator_id == fatos.devedor_id

    if comando in _COMANDOS_EXCLUSIVOS_DEVEDOR:
        if eh_devedor:
            return _OK
        return _negado("SO_O_DEVEDOR", "Apenas o devedor da cobrança pode executar esta ação.")

    permissao = _PERMISSAO_DO_COMANDO.get(comando)
    if permissao is None:
        return _negado("PERMISSION_DENIED", "Este comando não está disponível para usuários.")

    if eh_devedor:
        if comando in (ComandoCobranca.VALIDAR_PAGAMENTO, ComandoCobranca.REJEITAR_PAGAMENTO):
            return _negado("DEVEDOR_NAO_VALIDA", "O devedor não pode validar o próprio pagamento.")
        return _negado("DEVEDOR_NAO_DECIDE", "O devedor não pode decidir a própria cobrança.")

    if fatos.ator_admin or (fatos.ator_le_gestao and permissao in fatos.permissoes_ator):
        return _OK
    return _negado("PERMISSION_DENIED", "Você não tem permissão para esta ação.")


def acoes_cobranca_disponiveis(fatos: FatosCobranca) -> list[str]:
    """Lista os comandos habilitados para o ator neste estado (alimenta `acoes` e a paridade)."""
    acoes: list[str] = []
    for comando in _ORDEM_ACOES_COBRANCA:
        if not transicao_cobranca_permitida(fatos.situacao, comando):
            continue
        if comando == ComandoCobranca.QUESTIONAR and fatos.tem_questionamento_aberto:
            continue
        if comando == ComandoCobranca.DECIDIR_QUESTIONAMENTO and not fatos.tem_questionamento_aberto:
            continue
        if (
            comando in (ComandoCobranca.JUSTIFICAR_DIVIDA, ComandoCobranca.MANTER_DIVIDA)
            and not fatos.tem_convocacao_aberta
        ):
            continue
        if avaliar_cobranca(comando, fatos).pode:
            acoes.append(comando.value)
    return acoes


@dataclass(frozen=True)
class FatosEntrada:
    ator_id: uuid.UUID
    ator_admin: bool
    tem_permissao_validar: bool
    registrada_por_id: uuid.UUID
    situacao: SituacaoEntrada


def avaliar_entrada(comando: ComandoEntrada, fatos: FatosEntrada) -> DecisaoAutorizacao:
    """Avalia se o ator pode validar ou rejeitar a entrada (INV-ENT-05)."""
    if fatos.ator_id == fatos.registrada_por_id:
        return _negado("REGISTRADOR_NAO_VALIDA", "Quem registrou a entrada não pode validá-la.")
    if fatos.ator_admin or fatos.tem_permissao_validar:
        return _OK
    return _negado("PERMISSION_DENIED", "Você não tem permissão para validar entradas.")


def acoes_entrada_disponiveis(fatos: FatosEntrada) -> list[str]:
    """Lista as ações de entrada disponíveis no detalhe."""
    acoes: list[str] = []
    for comando in (ComandoEntrada.VALIDAR, ComandoEntrada.REJEITAR):
        if transicao_entrada_permitida(fatos.situacao, comando) and avaliar_entrada(comando, fatos).pode:
            acoes.append(comando.value)
    return acoes


def pode_ver_comprovante_cobranca(
    *,
    ator_id: uuid.UUID,
    ator_admin: bool,
    tem_permissao_validar: bool,
    devedor_id: uuid.UUID,
) -> bool:
    """Regra 19 / CA-18: só devedor, quem valida pagamentos e admin abrem comprovantes."""
    return ator_admin or tem_permissao_validar or ator_id == devedor_id


def pode_ver_comprovante_entrada(
    *,
    ator_id: uuid.UUID,
    ator_admin: bool,
    tem_permissao_validar: bool,
    registrada_por_id: uuid.UUID,
) -> bool:
    """Comprovante da entrada fica visível para registrador, validador e admin."""
    return ator_admin or tem_permissao_validar or ator_id == registrada_por_id
