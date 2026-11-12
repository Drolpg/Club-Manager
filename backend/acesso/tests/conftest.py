import pytest

from acesso.models import Usuario
from acesso.services import usuarios

SENHA = "correta-bateria-grampo"


@pytest.fixture
def admin(db: None) -> Usuario:
    return usuarios.criar_admin(
        nome="Ana Admin",
        nome_de_usuario="ana.admin",
        email="ana@exemplo.com",
        telefone="11999990000",
        senha=SENHA,
    )
