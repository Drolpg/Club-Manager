"""NOT-R03: o e-mail vai se o tipo pede ação ou se o destinatário não desligou os informativos."""

import pytest

from notificacoes.domain.envio import deve_enviar_email


@pytest.mark.parametrize(
    ("pede_acao", "email_informativos", "esperado"),
    [
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ],
)
def test_not_r03_todas_as_combinacoes(pede_acao: bool, email_informativos: bool, esperado: bool) -> None:
    assert deve_enviar_email(pede_acao, email_informativos) is esperado
