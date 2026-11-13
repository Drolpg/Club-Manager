"""Perguntas sobre o que um usuário pode. É o que a API pública do módulo expõe."""

import uuid

from acesso import public as acesso
from permissoes.models import Classificacao


def le_gestao(usuario_id: uuid.UUID) -> bool:
    """Lê os dados de gestão quem é admin ativo, ou é ativo e tem cargo ativo (PER-R10)."""
    usuario = acesso.usuario_por_id(usuario_id)
    if usuario is None or not usuario.ativo:
        return False
    if usuario.admin:
        return True
    return Classificacao.objects.filter(usuario_id=usuario_id, cargo__ativo=True).exists()
