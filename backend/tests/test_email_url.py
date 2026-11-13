"""`EMAIL_URL`: o servidor SMTP por variável de ambiente (AD-012), com `?tls=0` só para o Mailpit."""

from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings import _mailer_from_url

BACKEND_SMTP = "django.core.mail.backends.smtp.EmailBackend"


def _opcoes(url: str) -> dict[str, Any]:
    configuracao = _mailer_from_url(url)
    assert configuracao["BACKEND"] == BACKEND_SMTP
    opcoes: dict[str, Any] = configuracao["OPTIONS"]  # type: ignore[assignment]
    return opcoes


def test_smtp_usa_starttls_e_decodifica_usuario_e_senha() -> None:
    opcoes = _opcoes("smtp://aviso%40clube.exemplo:p%40ss%3Aword@mail.exemplo:2525")

    assert opcoes == {
        "host": "mail.exemplo",
        "port": 2525,
        "username": "aviso@clube.exemplo",
        "password": "p@ss:word",
        "use_ssl": False,
        "use_tls": True,
        "timeout": 10,
    }


def test_smtps_usa_tls_direto() -> None:
    opcoes = _opcoes("smtps://usuario:senha@mail.exemplo:465")

    assert (opcoes["use_ssl"], opcoes["use_tls"], opcoes["port"]) == (True, False, 465)


@pytest.mark.parametrize(("url", "porta"), [("smtp://mail.exemplo", 587), ("smtps://mail.exemplo", 465)])
def test_a_porta_padrao_depende_do_esquema(url: str, porta: int) -> None:
    assert _opcoes(url)["port"] == porta


def test_tls_zero_desliga_a_criptografia_para_o_servidor_de_desenvolvimento() -> None:
    opcoes = _opcoes("smtp://mailpit:1025?tls=0")

    assert opcoes == {
        "host": "mailpit",
        "port": 1025,
        "username": "",
        "password": "",
        "use_ssl": False,
        "use_tls": False,
        "timeout": 10,
    }


@pytest.mark.parametrize(
    "url",
    [
        "smtp://mailpit:1025?tls=1",
        "smtp://mailpit:1025?tls=nao",
        "smtp://mailpit:1025?tls=",
        "smtp://mailpit:1025?tls=0&tls=1",
        "smtp://mailpit:1025?outra=0",
        "smtp://mailpit:1025?tls=0&outra=1",
        "smtps://mailpit:1025?tls=0",
    ],
)
def test_so_o_tls_zero_em_smtp_e_aceito_na_consulta(url: str) -> None:
    with pytest.raises(ImproperlyConfigured, match="tls=0"):
        _mailer_from_url(url)


def test_esquema_desconhecido_e_recusado_sem_vazar_a_senha() -> None:
    with pytest.raises(ImproperlyConfigured) as erro:
        _mailer_from_url("http://usuario:segredo-da-senha@mail.exemplo")

    assert "segredo-da-senha" not in str(erro.value)
    assert "smtp://" in str(erro.value)
