"""Contagem de ocorrências por chave, numa janela de tempo, guardada no cache.

Quem decide o que contar e o que fazer ao chegar no limite é o serviço que chama. Aqui não há regra de
negócio.
"""

import hashlib

from django.core.cache import cache


def cache_key(scope: str, identifier: str) -> str:
    # O identificador pode ser um e-mail ou um IP: vai para o cache só como hash.
    digest = hashlib.sha256(identifier.encode()).hexdigest()
    return f"rate:{scope}:{digest}"


def hit(scope: str, identifier: str, *, window: int) -> None:
    """Conta uma ocorrência. A janela, em segundos, começa na primeira."""
    key = cache_key(scope, identifier)
    if cache.add(key, 1, timeout=window):
        return
    try:
        cache.incr(key)
    except ValueError:
        # A chave venceu entre o add e o incr.
        cache.add(key, 1, timeout=window)


def exceeded(scope: str, identifier: str, *, limit: int) -> bool:
    return int(cache.get(cache_key(scope, identifier), 0)) >= limit


def reset(scope: str, identifier: str) -> None:
    cache.delete(cache_key(scope, identifier))
