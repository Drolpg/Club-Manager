"""Preferências de alerta do usuário (RF-030)."""

import uuid
from dataclasses import dataclass

from django.db import transaction

from notificacoes.models import PreferenciaDeAlerta


@dataclass(frozen=True)
class Preferencias:
    aviso_na_tela: bool
    email_informativos: bool


_PADRAO = Preferencias(aviso_na_tela=True, email_informativos=True)


def obter(usuario_id: uuid.UUID) -> Preferencias:
    """As preferências do usuário; sem linha, os padrões."""
    linha = PreferenciaDeAlerta.objects.filter(pk=usuario_id).first()
    if linha is None:
        return _PADRAO
    return Preferencias(linha.aviso_na_tela, linha.email_informativos)


@transaction.atomic
def alterar(
    usuario_id: uuid.UUID, *, aviso_na_tela: bool | None = None, email_informativos: bool | None = None
) -> Preferencias:
    """Muda só o que foi informado. A linha nasce na primeira alteração; sem nada a mudar, não nasce."""
    novos = {
        campo: valor
        for campo, valor in (("aviso_na_tela", aviso_na_tela), ("email_informativos", email_informativos))
        if valor is not None
    }
    if novos:
        PreferenciaDeAlerta.objects.update_or_create(usuario_id=usuario_id, defaults=novos)
    return obter(usuario_id)
