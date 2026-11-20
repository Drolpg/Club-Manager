"""As notificações de `eventos` (spec funcional, tabela "Notificações"; spec técnica, chaves).

Chamadas dentro da transação do caso de uso: o registro entra nela, e o e-mail só sai depois do commit. A
chave identifica o fato e impede a duplicata. Os textos levam título, data local e local; nunca valores.
"""

import uuid
from collections.abc import Iterable

from django.utils import timezone

from eventos import tipos
from eventos.domain.autorizacao import PERM_APROVAR
from eventos.models import Evento, Presenca, RespostaDePresenca
from notificacoes import public as notificacoes
from permissoes import public as permissoes

_TITULO = 120
_TEXTO = 500


def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def quando_e_onde(evento: Evento) -> str:
    inicio = timezone.localtime(evento.inicio)
    return f"{inicio:%d/%m/%Y} às {inicio:%H:%M}, em {evento.local}"


def _notificar(
    tipo: str, destinatarios: Iterable[uuid.UUID], evento: Evento, *, titulo: str, texto: str, chave: str
) -> None:
    destino = set(destinatarios)
    if not destino:
        return
    notificacoes.notificar(
        tipo=tipo,
        destinatarios=destino,
        titulo=_cortar(titulo, _TITULO),
        texto=_cortar(texto, _TEXTO),
        item_tipo="evento",
        item_id=evento.id,
        caminho=f"/eventos/{evento.id}",
        chave=chave,
    )


def diretores_com_cargo() -> set[uuid.UUID]:
    return set(permissoes.usuarios_ativos_com_cargo())


def quem_aprova_eventos() -> set[uuid.UUID]:
    return set(permissoes.quem_pode(PERM_APROVAR))


def quem_disse_que_vai(evento: Evento) -> set[uuid.UUID]:
    return set(
        Presenca.objects.filter(
            evento=evento, ciclo=evento.ciclo_de_presenca, resposta=RespostaDePresenca.VOU
        ).values_list("diretor_id", flat=True)
    )


def montar_orcamento(evento: Evento, *, chave: str) -> None:
    """Evento aprovado e com custo, ainda sem orçamento → quem aprova eventos (pede ação; CA-05)."""
    _notificar(
        tipos.NOTIF_MONTAR_ORCAMENTO,
        quem_aprova_eventos(),
        evento,
        titulo="Evento esperando o orçamento",
        texto=f"O evento “{evento.titulo}” ({quando_e_onde(evento)}) envolve custo e espera o orçamento.",
        chave=chave,
    )


def publicado(evento: Evento) -> None:
    """Evento publicado → todos os diretores ativos com cargo, uma vez por publicação (CA-04, CA-16)."""
    _notificar(
        tipos.NOTIF_PUBLICADO,
        diretores_com_cargo(),
        evento,
        titulo="Evento no calendário",
        texto=f"O evento “{evento.titulo}” foi publicado: {quando_e_onde(evento)}.",
        chave=f"evento-publicado:{evento.id}:{evento.publicacoes}",
    )


def despublicado(evento: Evento) -> None:
    """Evento saiu do calendário → quem disse que vai, no ciclo atual."""
    _notificar(
        tipos.NOTIF_DESPUBLICADO,
        quem_disse_que_vai(evento),
        evento,
        titulo="Evento fora do calendário",
        texto=(
            f"O evento “{evento.titulo}” ({quando_e_onde(evento)}) mudou e saiu do calendário até ser "
            "aprovado de novo."
        ),
        chave=f"evento-despublicado:{evento.id}:{evento.publicacoes}",
    )
