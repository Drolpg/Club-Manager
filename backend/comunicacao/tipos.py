"""O que `comunicacao` declara ao iniciar: as quatro permissões e os dois tipos de notificação."""

from comunicacao.domain.autorizacao import (
    PERM_ENVIAR_DOCUMENTOS,
    PERM_GERENCIAR,
    PERM_PUBLICAR,
    PERM_REGISTRAR_ATAS,
)
from notificacoes import public as notificacoes
from permissoes import public as permissoes

PERMISSOES: tuple[tuple[str, str, str], ...] = (
    (
        PERM_PUBLICAR,
        "Publicar comunicados",
        "Publicar comunicados e pautas no feed; editar e despublicar os próprios.",
    ),
    (
        PERM_GERENCIAR,
        "Gerenciar a comunicação",
        "Fixar comunicados; editar e despublicar os de outros; ocultar e reexibir comentários; "
        "arquivar e enviar nova versão de documentos de outros.",
    ),
    (
        PERM_ENVIAR_DOCUMENTOS,
        "Enviar documentos",
        "Enviar documentos à aba de documentos; arquivar e enviar nova versão dos próprios.",
    ),
    (PERM_REGISTRAR_ATAS, "Registrar atas", "Registrar atas de reunião como documentos."),
)

NOTIF_COMUNICADO_PUBLICADO = "comunicacao.comunicado_publicado"
NOTIF_COMENTARIO_NOVO = "comunicacao.comentario_novo"

# Código → (pede ação, descrição).
TIPOS_DE_NOTIFICACAO: dict[str, tuple[bool, str]] = {
    NOTIF_COMUNICADO_PUBLICADO: (False, "Um comunicado ou uma pauta foi publicado no feed."),
    NOTIF_COMENTARIO_NOVO: (False, "Alguém comentou num comunicado que você publicou."),
}


def registrar_catalogos() -> None:
    for codigo, nome, descricao in PERMISSOES:
        permissoes.registrar_permissao(codigo, nome, descricao)
    for codigo, (pede_acao, descricao) in TIPOS_DE_NOTIFICACAO.items():
        notificacoes.registrar_tipo(codigo, pede_acao=pede_acao, descricao=descricao)
