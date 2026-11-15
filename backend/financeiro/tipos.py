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
    PERM_FINANCEIRO_ESTORNAR,
    PERM_GASTOS_APROVAR,
    PERM_PAGAMENTOS_VALIDAR,
    PERM_QUESTIONAMENTOS_DECIDIR,
    PERM_SAIDAS_ENVIAR,
    PERM_SAIDAS_LIQUIDAR,
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
    (
        PERM_GASTOS_APROVAR,
        "Aprovar gastos",
        "Decidir solicitações de gasto iniciais e complementares.",
    ),
    (
        PERM_SAIDAS_ENVIAR,
        "Enviar recursos",
        "Registrar envio de recurso e de complemento em saídas aprovadas.",
    ),
    (
        PERM_SAIDAS_LIQUIDAR,
        "Liquidar saídas",
        "Conferir prestação de contas, devolver para correção e liquidar saídas.",
    ),
    (
        PERM_FINANCEIRO_ESTORNAR,
        "Estornar lançamentos",
        "Registrar estorno de saída liquidada, entrada validada ou cobrança paga.",
    ),
)

DECISAO_PAGAMENTO_VALIDAR = "financeiro.pagamento_validar"
DECISAO_PAGAMENTO_REJEITAR = "financeiro.pagamento_rejeitar"
DECISAO_COBRANCA_CANCELAR = "financeiro.cobranca_cancelar"
DECISAO_QUESTIONAMENTO_DECIDIR = "financeiro.questionamento_decidir"
DECISAO_DIVIDA_DECIDIR = "financeiro.divida_decidir"
DECISAO_ENTRADA_VALIDAR = "financeiro.entrada_validar"
DECISAO_ENTRADA_REJEITAR = "financeiro.entrada_rejeitar"
DECISAO_PRESTACAO_DEVOLVER = "financeiro.prestacao_devolver"
DECISAO_ESTORNAR = "financeiro.estornar"

TIPOS_DE_DECISAO: tuple[tuple[str, str], ...] = (
    (DECISAO_PAGAMENTO_VALIDAR, "Validar pagamento"),
    (DECISAO_PAGAMENTO_REJEITAR, "Rejeitar pagamento"),
    (DECISAO_COBRANCA_CANCELAR, "Cancelar cobrança"),
    (DECISAO_QUESTIONAMENTO_DECIDIR, "Decidir questionamento"),
    (DECISAO_DIVIDA_DECIDIR, "Decidir dívida"),
    (DECISAO_ENTRADA_VALIDAR, "Validar entrada"),
    (DECISAO_ENTRADA_REJEITAR, "Rejeitar entrada"),
    (DECISAO_PRESTACAO_DEVOLVER, "Devolver prestação de contas"),
    (DECISAO_ESTORNAR, "Estornar lançamento financeiro"),
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
NOTIF_SAIDA_AGUARDANDO_ENVIO = "financeiro.saida_aguardando_envio"
NOTIF_RECURSO_ENVIADO = "financeiro.recurso_enviado"
NOTIF_PRESTACAO_LEMBRETE_5_DIAS = "financeiro.prestacao_lembrete_cinco_dias"
NOTIF_PRESTACAO_VENCIDA = "financeiro.prestacao_vencida"
NOTIF_PRESTACAO_VENCIDA_FIN = "financeiro.prestacao_vencida_financeiro"
NOTIF_PRESTACAO_REGISTRADA = "financeiro.prestacao_registrada"
NOTIF_PRESTACAO_DEVOLVIDA = "financeiro.prestacao_devolvida"
NOTIF_COMPLEMENTO_APROVADO = "financeiro.complemento_aprovado"
NOTIF_SAIDA_LIQUIDADA = "financeiro.saida_liquidada"
NOTIF_REGISTRO_ESTORNADO = "financeiro.registro_estornado"

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
    (NOTIF_SAIDA_AGUARDANDO_ENVIO, True, "Um gasto aprovado aguarda envio de recurso."),
    (NOTIF_RECURSO_ENVIADO, True, "O recurso de seu gasto foi enviado e aguarda prestação."),
    (NOTIF_PRESTACAO_LEMBRETE_5_DIAS, True, "Lembrete: envie a prestação de contas da sua saída."),
    (NOTIF_PRESTACAO_VENCIDA, True, "O prazo para prestar contas desta saída venceu."),
    (NOTIF_PRESTACAO_VENCIDA_FIN, False, "Uma saída está com prestação de contas em atraso."),
    (NOTIF_PRESTACAO_REGISTRADA, True, "Uma prestação de contas foi registrada para conferência."),
    (NOTIF_PRESTACAO_DEVOLVIDA, True, "Sua prestação de contas foi devolvida para correção."),
    (NOTIF_COMPLEMENTO_APROVADO, True, "Um complemento de saída foi aprovado e aguarda envio."),
    (NOTIF_SAIDA_LIQUIDADA, False, "Sua saída de recurso foi liquidada."),
    (NOTIF_REGISTRO_ESTORNADO, False, "Um lançamento financeiro foi estornado."),
)


def registrar_catalogos() -> None:
    """Declara permissões, tipos de decisão e tipos de notificação no boot do Django."""
    for codigo, nome, descricao in PERMISSOES:
        permissoes.registrar_permissao(codigo, nome, descricao)
    for codigo, nome in TIPOS_DE_DECISAO:
        aprovacoes.registrar_tipo_de_decisao(codigo, nome)
    for codigo, pede_acao, descricao in TIPOS_DE_NOTIFICACAO:
        notificacoes.registrar_tipo(codigo, pede_acao=pede_acao, descricao=descricao)
