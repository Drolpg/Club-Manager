"""Quem vê um perfil (P21, RN-008). Função pura: não importa Django, DRF nem Celery."""

import uuid


def pode_ver_perfil(*, ator_id: uuid.UUID, alvo_id: uuid.UUID, ator_e_admin: bool) -> bool:
    """Só o próprio usuário e o admin. Leitura de gestão, acesso total e permissões do catálogo não contam."""
    return ator_id == alvo_id or ator_e_admin
