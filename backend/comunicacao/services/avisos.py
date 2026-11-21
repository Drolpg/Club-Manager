"""As notificações de `comunicacao` (spec funcional, tabela "Notificações"; spec técnica, chaves).

Chamadas dentro da transação do caso de uso: o registro entra nela, e o e-mail só sai depois do commit. A
chave identifica o fato e impede a duplicata. Os textos levam só o título do comunicado e o nome de quem agiu:
nunca o texto do comunicado nem o do comentário.
"""

import uuid
from collections.abc import Iterable

from acesso import public as acesso
from comunicacao import tipos
from comunicacao.domain.valores import TipoDeComunicado
from comunicacao.models import Comentario, Comunicado
from notificacoes import public as notificacoes
from permissoes import public as permissoes

_TITULO = 120
_TEXTO = 500


def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _nome(usuario_id: uuid.UUID) -> str:
    usuario = acesso.usuario_por_id(usuario_id)
    return usuario.nome if usuario else "Alguém"


def _notificar(
    tipo: str,
    destinatarios: Iterable[uuid.UUID],
    comunicado: Comunicado,
    *,
    titulo: str,
    texto: str,
    chave: str,
) -> None:
    destino = set(destinatarios)
    if not destino:
        return
    notificacoes.notificar(
        tipo=tipo,
        destinatarios=destino,
        titulo=_cortar(titulo, _TITULO),
        texto=_cortar(texto, _TEXTO),
        item_tipo="comunicado",
        item_id=comunicado.id,
        caminho=f"/feed/{comunicado.id}",
        chave=chave,
    )


def comunicado_publicado(comunicado: Comunicado) -> None:
    """Todos os diretores ativos com cargo, menos o autor, uma vez por comunicado (CA-05)."""
    rotulo = "Nova pauta" if comunicado.tipo == TipoDeComunicado.PAUTA else "Novo comunicado"
    destinatarios = set(permissoes.usuarios_ativos_com_cargo()) - {comunicado.autor_id}
    _notificar(
        tipos.NOTIF_COMUNICADO_PUBLICADO,
        destinatarios,
        comunicado,
        titulo=f"{rotulo}: {comunicado.titulo}",
        texto=f"{_nome(comunicado.autor_id)} publicou no feed: {comunicado.titulo}",
        chave=f"comunicado-publicado:{comunicado.id}",
    )


def comentario_novo(comunicado: Comunicado, comentario: Comentario) -> None:
    """O autor do comunicado é avisado de cada comentário novo, menos dos que ele mesmo faz (CA-15)."""
    destinatarios = {comunicado.autor_id} - {comentario.autor_id}
    _notificar(
        tipos.NOTIF_COMENTARIO_NOVO,
        destinatarios,
        comunicado,
        titulo=f"Novo comentário: {comunicado.titulo}",
        texto=f"{_nome(comentario.autor_id)} comentou em «{comunicado.titulo}».",
        chave=f"comentario-novo:{comentario.id}",
    )
