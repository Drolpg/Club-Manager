"""O que `eventos` declara ao iniciar: permissões, tipos de notificação e o tipo de solicitação no motor."""

from aprovacoes import public as aprovacoes
from eventos.domain.autorizacao import PERM_APROVAR, PERM_CANCELAR, PERM_PROPOR
from notificacoes import public as notificacoes
from permissoes import public as permissoes

TIPO_EVENTO = "eventos.evento"

PERMISSOES: tuple[tuple[str, str, str], ...] = (
    (PERM_PROPOR, "Propor eventos", "Propor eventos e editar os próprios."),
    (
        PERM_APROVAR,
        "Aprovar eventos",
        "Decidir solicitações de evento, abrir o orçamento, editar qualquer evento e confirmar a realização.",
    ),
    (PERM_CANCELAR, "Cancelar eventos", "Cancelar evento de outra pessoa."),
)

NOTIF_MONTAR_ORCAMENTO = "eventos.montar_orcamento"
NOTIF_PUBLICADO = "eventos.publicado"
NOTIF_DESPUBLICADO = "eventos.despublicado"
NOTIF_REALIZACAO_PENDENTE = "eventos.realizacao_pendente"
NOTIF_REALIZADO = "eventos.realizado"
NOTIF_CANCELADO = "eventos.cancelado"
NOTIF_CANCELADO_PELA_DATA = "eventos.cancelado_pela_data"

# Código → (pede ação, descrição).
TIPOS_DE_NOTIFICACAO: dict[str, tuple[bool, str]] = {
    NOTIF_MONTAR_ORCAMENTO: (
        True,
        "A solicitação de um evento com custo foi aprovada e o evento espera o orçamento.",
    ),
    NOTIF_PUBLICADO: (False, "Um evento entrou no calendário."),
    NOTIF_DESPUBLICADO: (False, "Um evento em que você disse que vai saiu do calendário."),
    NOTIF_REALIZACAO_PENDENTE: (True, "A data de um evento chegou: confirme se ele aconteceu."),
    NOTIF_REALIZADO: (False, "O seu evento foi confirmado como realizado."),
    NOTIF_CANCELADO: (False, "Um evento foi cancelado."),
    NOTIF_CANCELADO_PELA_DATA: (False, "O seu evento foi cancelado porque a data passou sem aprovação."),
}


def registrar_catalogos() -> None:
    from eventos import handlers

    for codigo, nome, descricao in PERMISSOES:
        permissoes.registrar_permissao(codigo, nome, descricao)
    for codigo, (pede_acao, descricao) in TIPOS_DE_NOTIFICACAO.items():
        notificacoes.registrar_tipo(codigo, pede_acao=pede_acao, descricao=descricao)
    aprovacoes.registrar_tipo(
        codigo=TIPO_EVENTO,
        nome="Evento",
        permissao_de_aprovar=PERM_APROVAR,
        permissao_de_enviar=PERM_PROPOR,
        tem_valor=False,
        preparar=handlers.preparar_solicitacao_do_evento,
        ao_mudar=handlers.ao_mudar_solicitacao_do_evento,
        so_pelo_modulo_dono=True,
    )
