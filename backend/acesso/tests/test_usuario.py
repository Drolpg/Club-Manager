import pytest

from acesso.models import Situacao, Usuario
from acesso.services import usuarios
from acesso.tests.conftest import SENHA
from kernel.errors import BusinessError

pytestmark = pytest.mark.django_db


def _dados(**extra: str) -> dict[str, str]:
    dados = {
        "nome": "Bia Diretora",
        "nome_de_usuario": "bia",
        "email": "bia@exemplo.com",
        "telefone": "11988887777",
        "senha": SENHA,
    }
    dados.update(extra)
    return dados


def test_admin_criado_fica_ativo_com_email_verificado_e_senha_em_hash(admin: Usuario) -> None:
    assert admin.situacao == Situacao.ATIVO
    assert admin.admin is True
    assert admin.is_active is True
    assert admin.email_verificado_em is not None
    assert admin.password != SENHA
    assert admin.password.startswith("argon2")
    assert admin.check_password(SENHA)


def test_nome_de_usuario_e_unico_sem_diferenciar_maiusculas(admin: Usuario) -> None:
    with pytest.raises(BusinessError) as erro:
        usuarios.criar_admin(**_dados(nome_de_usuario="ANA.Admin"))

    assert erro.value.code == "NOME_DE_USUARIO_EM_USO"
    assert Usuario.objects.count() == 1


def test_email_e_unico_sem_diferenciar_maiusculas(admin: Usuario) -> None:
    with pytest.raises(BusinessError) as erro:
        usuarios.criar_admin(**_dados(email="ANA@Exemplo.com"))

    assert erro.value.code == "EMAIL_EM_USO"
    assert Usuario.objects.count() == 1


def test_banco_recusa_nome_de_usuario_repetido_mesmo_fora_do_servico(admin: Usuario) -> None:
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        Usuario.objects.create(nome="x", nome_de_usuario="Ana.ADMIN", email="outra@exemplo.com", telefone="1")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("senha", "curta123"),
        ("senha", "12345678901234"),
        ("senha", "password123"),
        ("senha", "bia@exemplo.com"),
        ("nome_de_usuario", "b"),
        ("nome_de_usuario", "bia maria"),
        ("email", "nao-e-email"),
        ("telefone", "123"),
        ("nome", "  "),
    ],
)
def test_dados_invalidos_sao_recusados_apontando_o_campo(campo: str, valor: str) -> None:
    with pytest.raises(BusinessError) as erro:
        usuarios.criar_admin(**_dados(**{campo: valor}))

    assert erro.value.code == "VALIDATION_ERROR"
    assert erro.value.status == 400
    assert campo in erro.value.details
    assert Usuario.objects.count() == 0


def test_email_e_guardado_normalizado() -> None:
    usuario = usuarios.criar_admin(**_dados(email="  Bia@Exemplo.COM "))

    assert usuario.email == "bia@exemplo.com"


def test_usuario_nao_ativo_nao_e_reconhecido_como_ativo(admin: Usuario) -> None:
    admin.situacao = Situacao.INATIVO

    assert admin.is_active is False
