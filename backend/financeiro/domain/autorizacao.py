"""Regras puras de autorização sobre cobranças, entradas, saídas e sigilo de comprovantes."""

import uuid
from dataclasses import dataclass

from financeiro.domain.transicoes import (
    ComandoCobranca,
    ComandoEntrada,
    ComandoSaida,
    SituacaoCobranca,
    SituacaoEntrada,
    SituacaoSaida,
    transicao_cobranca_permitida,
    transicao_entrada_permitida,
    transicao_saida_permitida,
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
PERM_GASTOS_APROVAR = "gastos.aprovar"
PERM_SAIDAS_ENVIAR = "saidas.enviar"
PERM_SAIDAS_LIQUIDAR = "saidas.liquidar"
PERM_FINANCEIRO_ESTORNAR = "financeiro.estornar"


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
    ComandoCobranca.ESTORNAR: PERM_FINANCEIRO_ESTORNAR,
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
    ComandoCobranca.ESTORNAR,
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
    tem_permissao_estornar: bool = False
    ator_le_gestao: bool = True
    saida_liquidada: bool = False


def avaliar_entrada(comando: ComandoEntrada, fatos: FatosEntrada) -> DecisaoAutorizacao:
    """Avalia se o ator pode validar, rejeitar ou estornar a entrada (INV-ENT-05)."""
    if comando == ComandoEntrada.ESTORNAR:
        if fatos.ator_admin or (fatos.ator_le_gestao and fatos.tem_permissao_estornar):
            return _OK
        return _negado("PERMISSION_DENIED", "Você não tem permissão para estornar lançamentos.")
    if fatos.ator_id == fatos.registrada_por_id:
        return _negado("REGISTRADOR_NAO_VALIDA", "Quem registrou a entrada não pode validá-la.")
    if fatos.ator_admin or fatos.tem_permissao_validar:
        return _OK
    return _negado("PERMISSION_DENIED", "Você não tem permissão para validar entradas.")


def acoes_entrada_disponiveis(fatos: FatosEntrada) -> list[str]:
    """Lista as ações de entrada disponíveis no detalhe."""
    acoes: list[str] = []
    for comando in (ComandoEntrada.VALIDAR, ComandoEntrada.REJEITAR, ComandoEntrada.ESTORNAR):
        if comando == ComandoEntrada.ESTORNAR and fatos.saida_liquidada:
            continue
        if transicao_entrada_permitida(fatos.situacao, comando) and avaliar_entrada(comando, fatos).pode:
            acoes.append(comando.value)
    return acoes


@dataclass(frozen=True)
class FatosSaida:
    ator_id: uuid.UUID
    ator_admin: bool
    ator_le_gestao: bool
    permissoes_ator: frozenset[str]
    solicitante_id: uuid.UUID
    situacao: SituacaoSaida
    tem_complemento_aprovado_para_enviar: bool = False
    tem_complemento_em_andamento: bool = False
    tem_excesso_para_complemento: bool = False
    tem_devolucao_em_validacao: bool = False
    tem_saldo_para_devolver: bool = True
    diferenca_pendente_acerto: bool = False


_COMANDOS_EXCLUSIVOS_SOLICITANTE_SAIDA = frozenset(
    {
        ComandoSaida.PRESTAR_CONTAS,
        ComandoSaida.DEVOLVER_SOBRA,
        ComandoSaida.PEDIR_COMPLEMENTO,
    }
)

_PERMISSAO_DO_COMANDO_SAIDA: dict[ComandoSaida, str] = {
    ComandoSaida.ENVIAR_RECURSO: PERM_SAIDAS_ENVIAR,
    ComandoSaida.DEVOLVER_PRESTACAO: PERM_SAIDAS_LIQUIDAR,
    ComandoSaida.LIQUIDAR: PERM_SAIDAS_LIQUIDAR,
    ComandoSaida.ESTORNAR: PERM_FINANCEIRO_ESTORNAR,
}

_ORDEM_ACOES_SAIDA: tuple[ComandoSaida, ...] = (
    ComandoSaida.ENVIAR_RECURSO,
    ComandoSaida.PRESTAR_CONTAS,
    ComandoSaida.DEVOLVER_PRESTACAO,
    ComandoSaida.DEVOLVER_SOBRA,
    ComandoSaida.PEDIR_COMPLEMENTO,
    ComandoSaida.LIQUIDAR,
    ComandoSaida.ESTORNAR,
)


def avaliar_saida(comando: ComandoSaida, fatos: FatosSaida) -> DecisaoAutorizacao:
    """Decide se o ator tem direito ao comando sobre a saída (INV-SAI-06, P7)."""
    eh_solicitante = fatos.ator_id == fatos.solicitante_id

    if comando in _COMANDOS_EXCLUSIVOS_SOLICITANTE_SAIDA:
        if eh_solicitante:
            return _OK
        return _negado(
            "SO_O_SOLICITANTE",
            "Apenas quem pediu o gasto pode executar esta ação.",
        )

    permissao = _PERMISSAO_DO_COMANDO_SAIDA.get(comando)
    if permissao is None:
        return _negado("PERMISSION_DENIED", "Este comando não está disponível diretamente.")

    if comando in (ComandoSaida.LIQUIDAR, ComandoSaida.DEVOLVER_PRESTACAO) and eh_solicitante:
        return _negado(
            "SOLICITANTE_NAO_LIQUIDA",
            "Quem pediu o gasto não pode conferir nem liquidar a própria saída.",
        )

    if fatos.ator_admin or (fatos.ator_le_gestao and permissao in fatos.permissoes_ator):
        return _OK
    return _negado("PERMISSION_DENIED", "Você não tem permissão para esta ação.")


def _acao_saida_habilitada_no_estado(comando: ComandoSaida, fatos: FatosSaida) -> bool:
    if comando == ComandoSaida.ENVIAR_RECURSO:
        if fatos.situacao == SituacaoSaida.AGUARDANDO_ENVIO:
            return True
        return fatos.tem_complemento_aprovado_para_enviar
    if comando == ComandoSaida.DEVOLVER_SOBRA:
        return fatos.tem_saldo_para_devolver
    if comando == ComandoSaida.PEDIR_COMPLEMENTO:
        return fatos.tem_excesso_para_complemento and not fatos.tem_complemento_em_andamento
    if comando == ComandoSaida.LIQUIDAR:
        return not (
            fatos.tem_devolucao_em_validacao
            or fatos.tem_complemento_em_andamento
            or fatos.tem_complemento_aprovado_para_enviar
            or fatos.diferenca_pendente_acerto
        )
    return True


def acoes_saida_disponiveis(fatos: FatosSaida) -> list[str]:
    """Lista os comandos disponíveis para o ator na situação atual da saída."""
    acoes: list[str] = []
    for comando in _ORDEM_ACOES_SAIDA:
        if not transicao_saida_permitida(fatos.situacao, comando):
            continue
        if not _acao_saida_habilitada_no_estado(comando, fatos):
            continue
        if avaliar_saida(comando, fatos).pode:
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


def pode_ver_anexos_saida(*, ator_le_gestao: bool, ator_admin: bool) -> bool:
    """P6 / CA-30: cotações e comprovantes de envio/prestação são visíveis a quem lê gestão."""
    return ator_admin or ator_le_gestao
