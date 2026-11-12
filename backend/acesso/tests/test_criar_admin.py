from collections.abc import Iterator
from unittest import mock

import pytest
from django.core.management import CommandError, call_command

from acesso.models import Situacao, Usuario
from acesso.tests.conftest import SENHA
from auditoria import public as auditoria

pytestmark = pytest.mark.django_db


@pytest.fixture
def digitar() -> Iterator[mock.MagicMock]:
    """Simula o que a pessoa digita: nome, nome de usuário, e-mail, telefone; e a senha, duas vezes."""
    with (
        mock.patch(
            "builtins.input", side_effect=["Ana Admin", "ana.admin", "ana@exemplo.com", "11999990000"]
        ),
        mock.patch("getpass.getpass", side_effect=[SENHA, SENHA]) as senha,
    ):
        yield senha


def test_ca01_comando_cria_um_admin_ativo_com_email_verificado(digitar: mock.MagicMock) -> None:
    call_command("criar_admin")

    usuario = Usuario.objects.get()
    assert usuario.admin is True
    assert usuario.situacao == Situacao.ATIVO
    assert usuario.email_verificado_em is not None
    assert usuario.check_password(SENHA)


def test_comando_audita_a_criacao_como_acao_do_sistema(digitar: mock.MagicMock) -> None:
    call_command("criar_admin")

    usuario = Usuario.objects.get()
    historico = auditoria.historico_do_item("usuario", usuario.id)
    assert [r.acao for r in historico] == ["ADMIN_CRIADO_POR_COMANDO"]
    assert historico[0].ator_id is None
    assert SENHA not in str(historico[0].dados)


def test_ca02_senha_fraca_nao_cria_usuario_e_mostra_o_motivo(digitar: mock.MagicMock) -> None:
    digitar.side_effect = ["12345678", "12345678"]

    with pytest.raises(CommandError) as erro:
        call_command("criar_admin")

    assert "senha" in str(erro.value).lower()
    assert Usuario.objects.count() == 0


def test_ca02_nome_de_usuario_ja_usado_nao_cria_outro(digitar: mock.MagicMock, admin: Usuario) -> None:
    with pytest.raises(CommandError) as erro:
        call_command("criar_admin")

    assert "nome de usuário" in str(erro.value).lower()
    assert Usuario.objects.count() == 1


def test_senhas_diferentes_nao_criam_usuario(digitar: mock.MagicMock) -> None:
    digitar.side_effect = [SENHA, SENHA + "x"]

    with pytest.raises(CommandError):
        call_command("criar_admin")

    assert Usuario.objects.count() == 0


def test_comando_nao_aceita_senha_por_argumento() -> None:
    with pytest.raises((CommandError, TypeError)):
        call_command("criar_admin", senha=SENHA)
