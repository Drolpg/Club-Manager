"""Declaração das permissões, tipos de decisão e tipos de notificação do módulo financeiro."""

from aprovacoes import public as aprovacoes
from financeiro.domain.autorizacao import (
    PERM_COBRANCAS_CANCELAR,
    PERM_COBRANCAS_CRIAR,
    PERM_COBRANCAS_ISENTAR,
    PERM_COBRANCAS_SUSPENDER,
    PERM_DIVIDAS_DECIDIR,
    PERM_ENTRADAS_REGISTRAR,
    PERM_ENTRADAS_VALIDAR,
    PERM_PAGAMENTOS_VALIDAR,
    PERM_QUESTIONAMENTOS_DECIDIR,
)
from notificacoes import public as notificacoes
from permissoes import public as permissoes

PERMISSOES: tuple[tuple[str, str, str], ...] = (
    (PERM_COBRANCAS_CRIAR, "Criar cobranças", "Criar cobranças avulsas, em lote e gerenciar recorrências."),
    (PERM_PAGAMENTOS_VALIDAR, "Validar pagamentos", "Validar e rejeitar pagamentos e ver comprovantes."),
    (PERM_ENTRADAS_REGISTRAR, "Registrar entradas", "Registrar entradas sem devedor."),
    (PERM_ENTRADAS_VALIDAR, "Validar entradas", "Validar e rejeitar entradas sem devedor."),
    (PERM_COBRANCAS_CANCELAR, "Cancelamento de cobranças", "Cancelar cobrança aberta ou atrasada."),
    (PERM_COBRANCAS_ISENTAR, "Isenção de cobranças", "Isentar cobrança aberta ou atrasada."),
    (
        PERM_QUESTIONAMENTOS_DECIDIR,
        "Decidir questionamentos",
        "Decidir questionamentos abertos de cobranças.",
    ),
    (PERM_DIVIDAS_DECIDIR, "Decidir dívidas", "Perdoar, renegociar ou manter dívidas em inadimplência."),
    (PERM_COBRANCAS_SUSPENDER, "Suspender cobranças", "Criar e encerrar suspensões de cobranças."),
)

DECISAO_PAGAMENTO_VALIDAR = "financeiro.pagamento_validar"
DECISAO_PAGAMENTO_REJEITAR = "financeiro.pagamento_rejeitar"
DECISAO_COBRANCA_CANCELAR = "financeiro.cobranca_cancelar"
DECISAO_QUESTIONAMENTO_DECIDIR = "financeiro.questionamento_decidir"
DECISAO_DIVIDA_DECIDIR = "financeiro.divida_decidir"
DECISAO_ENTRADA_VALIDAR = "financeiro.entrada_validar"
DECISAO_ENTRADA_REJEITAR = "financeiro.entrada_rejeitar"

TIPOS_DE_DECISAO: tuple[tuple[str, str], ...] = (
    (DECISAO_PAGAMENTO_VALIDAR, "Validar pagamento"),
    (DECISAO_PAGAMENTO_REJEITAR, "Rejeitar pagamento"),
    (DECISAO_COBRANCA_CANCELAR, "Cancelar cobrança"),
    (DECISAO_QUESTIONAMENTO_DECIDIR, "Decidir questionamento"),
    (DECISAO_DIVIDA_DECIDIR, "Decidir dívida"),
    (DECISAO_ENTRADA_VALIDAR, "Validar entrada"),
    (DECISAO_ENTRADA_REJEITAR, "Rejeitar entrada"),
)

NOTIF_COBRANCA_CRIADA = "financeiro.cobranca_criada"
NOTIF_LEMBRETE_3_DIAS = "financeiro.cobranca_lembrete_tres_dias"
NOTIF_VENCIMENTO_HOJE = "financeiro.cobranca_vencimento_hoje"
NOTIF_PAGAMENTO_REGISTRADO = "financeiro.pagamento_registrado"
NOTIF_PAGAMENTO_VALIDADO = "financeiro.pagamento_validado"
NOTIF_PAGAMENTO_REJEITADO = "financeiro.pagamento_rejeitado"
NOTIF_ATRASADA_DEVEDOR = "financeiro.cobranca_atrasada_devedor"
NOTIF_ATRASADA_FINANCEIRO = "financeiro.cobranca_atrasada_financeiro"
NOTIF_QUESTIONADA = "financeiro.cobranca_questionada"
NOTIF_QUESTIONAMENTO_DECIDIDO = "financeiro.questionamento_decidido"
NOTIF_DEVEDOR_CONVOCADO = "financeiro.devedor_convocado"
NOTIF_CONVOCACAO_FINANCEIRO = "financeiro.convocacao_financeiro"
NOTIF_DIVIDA_JUSTIFICADA = "financeiro.divida_justificada"
NOTIF_DIVIDA_DECIDIDA = "financeiro.divida_decidida"
NOTIF_ENTRADA_REGISTRADA = "financeiro.entrada_registrada"
NOTIF_ENTRADA_DECIDIDA = "financeiro.entrada_decidida"
NOTIF_DIRETOR_DESATIVADO = "financeiro.diretor_desativado_com_cobrancas"

TIPOS_DE_NOTIFICACAO: tuple[tuple[str, bool, str], ...] = (
    (NOTIF_COBRANCA_CRIADA, True, "Uma nova cobrança foi emitida para você."),
    (NOTIF_LEMBRETE_3_DIAS, True, "Sua cobrança vence em 3 dias."),
    (NOTIF_VENCIMENTO_HOJE, True, "Sua cobrança vence hoje."),
    (NOTIF_PAGAMENTO_REGISTRADO, True, "Um pagamento foi registrado e aguarda validação."),
    (NOTIF_PAGAMENTO_VALIDADO, False, "Seu pagamento foi validado."),
    (NOTIF_PAGAMENTO_REJEITADO, True, "Seu pagamento foi rejeitado e precisa ser refeito."),
    (NOTIF_ATRASADA_DEVEDOR, True, "Sua cobrança está atrasada."),
    (NOTIF_ATRASADA_FINANCEIRO, False, "Uma cobrança do clube ficou atrasada."),
    (NOTIF_QUESTIONADA, True, "Um devedor questionou uma cobrança."),
    (NOTIF_QUESTIONAMENTO_DECIDIDO, False, "Seu questionamento sobre a cobrança foi decidido."),
    (NOTIF_DEVEDOR_CONVOCADO, True, "Você foi convocado por atraso na cobrança."),
    (NOTIF_CONVOCACAO_FINANCEIRO, False, "Uma cobrança atingiu o limite e gerou convocação."),
    (NOTIF_DIVIDA_JUSTIFICADA, True, "Um devedor registrou justificativa na convocação."),
    (NOTIF_DIVIDA_DECIDIDA, False, "Uma decisão foi tomada sobre sua dívida."),
    (NOTIF_ENTRADA_REGISTRADA, True, "Uma entrada sem devedor aguarda validação."),
    (NOTIF_ENTRADA_DECIDIDA, False, "A entrada registrada foi validada ou rejeitada."),
    (NOTIF_DIRETOR_DESATIVADO, True, "Um diretor com cobranças não encerradas foi desativado."),
)


def registrar_catalogos() -> None:
    """Declara permissões, tipos de decisão e tipos de notificação no boot do Django."""
    for codigo, nome, descricao in PERMISSOES:
        permissoes.registrar_permissao(codigo, nome, descricao)
    for codigo, nome in TIPOS_DE_DECISAO:
        aprovacoes.registrar_tipo_de_decisao(codigo, nome)
    for codigo, pede_acao, descricao in TIPOS_DE_NOTIFICACAO:
        notificacoes.registrar_tipo(codigo, pede_acao=pede_acao, descricao=descricao)
