from collections.abc import Iterator

import pytest
from django.core.cache import cache
from django.test import RequestFactory

from kernel import rate_limit
from kernel.http import client_ip


@pytest.fixture(autouse=True)
def _zerar() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


def test_conta_as_ocorrencias_e_avisa_quando_chega_ao_limite() -> None:
    for _ in range(3):
        assert not rate_limit.exceeded("login", "bia", limit=3)
        rate_limit.hit("login", "bia", window=60)

    assert rate_limit.exceeded("login", "bia", limit=3)


def test_chaves_e_escopos_diferentes_nao_se_misturam() -> None:
    for _ in range(3):
        rate_limit.hit("login", "bia", window=60)

    assert not rate_limit.exceeded("login", "edu", limit=3)
    assert not rate_limit.exceeded("recuperacao", "bia", limit=3)


def test_reset_zera_a_contagem() -> None:
    for _ in range(3):
        rate_limit.hit("login", "bia", window=60)

    rate_limit.reset("login", "bia")

    assert not rate_limit.exceeded("login", "bia", limit=3)


def test_o_identificador_nao_fica_legivel_no_cache() -> None:
    assert "bia@exemplo.com" not in rate_limit.cache_key("login", "bia@exemplo.com")


def test_ip_do_cliente_vem_do_ultimo_salto_do_proxy() -> None:
    request = RequestFactory().get("/", headers={"X-Forwarded-For": "9.9.9.9, 203.0.113.7"})

    assert client_ip(request) == "203.0.113.7"


def test_ip_do_cliente_sem_proxy_e_o_da_conexao() -> None:
    request = RequestFactory().get("/", REMOTE_ADDR="198.51.100.4")

    assert client_ip(request) == "198.51.100.4"
