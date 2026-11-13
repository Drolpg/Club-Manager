import pytest
from rest_framework.test import APIClient

from acesso import public
from acesso.models import Situacao, Usuario
from acesso.services import usuarios
from acesso.tests.conftest import SENHA, criar_diretor, entrar
from auditoria import public as auditoria
from kernel.errors import BusinessError

pytestmark = pytest.mark.django_db

URL = "/api/v1/acesso/usuarios/"
SESSAO = "/api/v1/acesso/sessao/"
CONVITES = "/api/v1/acesso/convites/"
ACOES = ("desativar", "reativar", "tornar-admin", "remover-admin")


def _acao(client: APIClient, usuario: Usuario, acao: str):  # type: ignore[no-untyped-def]
    return client.post(f"{URL}{usuario.id}/{acao}/")


def test_ca27_lista_mostra_situacao_papel_e_cargo(client_admin: APIClient, admin: Usuario) -> None:
    criar_diretor("bia")
    criar_diretor("caio", Situacao.AGUARDANDO_VERIFICACAO)
    criar_diretor("dani", Situacao.INATIVO)

    resposta = client_admin.get(URL)

    assert resposta.status_code == 200
    por_nome = {u["nome_de_usuario"]: u for u in resposta.json()}
    assert set(por_nome) == {"ana.admin", "bia", "caio", "dani"}
    assert por_nome["ana.admin"]["admin"] is True
    assert por_nome["bia"] == {
        "id": str(Usuario.objects.get(nome_de_usuario="bia").id),
        "nome": "Diretor bia",
        "nome_de_usuario": "bia",
        "email": "bia@exemplo.com",
        "admin": False,
        "situacao": "ATIVO",
        "tem_cargo": False,
    }
    assert por_nome["caio"]["situacao"] == "AGUARDANDO_VERIFICACAO"
    assert por_nome["dani"]["situacao"] == "INATIVO"
    assert "password" not in resposta.content.decode()


def test_ca28_desativar_encerra_a_sessao_na_hora_e_barra_o_login(
    client_admin: APIClient, client_diretor: APIClient, diretor: Usuario, admin: Usuario
) -> None:
    resposta = _acao(client_admin, diretor, "desativar")

    assert resposta.status_code == 200
    assert resposta.json()["situacao"] == "INATIVO"
    assert client_diretor.get(SESSAO).json() == {"usuario": None}
    login = APIClient().post(SESSAO, {"identificador": "bia", "senha": SENHA})
    assert login.status_code == 401
    historico = auditoria.historico_do_item("usuario", diretor.id)
    assert [(r.acao, r.ator_id) for r in historico] == [("USUARIO_DESATIVADO", admin.id)]


def test_ca29_reativar_devolve_o_acesso_com_o_mesmo_historico(
    client_admin: APIClient, diretor: Usuario, admin: Usuario
) -> None:
    _acao(client_admin, diretor, "desativar")

    resposta = _acao(client_admin, diretor, "reativar")

    assert resposta.status_code == 200
    assert resposta.json()["situacao"] == "ATIVO"
    entrar(APIClient(), "bia")
    assert Usuario.objects.get(nome_de_usuario="bia").id == diretor.id
    historico = auditoria.historico_do_item("usuario", diretor.id)
    assert [r.acao for r in historico] == ["USUARIO_DESATIVADO", "USUARIO_REATIVADO"]


@pytest.mark.parametrize("acao", ["desativar", "remover-admin"])
def test_ca30_ninguem_desativa_a_si_mesmo_nem_tira_o_proprio_papel(
    client_admin: APIClient, admin: Usuario, acao: str
) -> None:
    resposta = _acao(client_admin, admin, acao)

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == "NAO_PODE_ALTERAR_A_SI_MESMO"
    atual = Usuario.objects.get(pk=admin.pk)
    assert atual.situacao == Situacao.ATIVO
    assert atual.admin is True


def test_ca31_diretor_tornado_admin_passa_a_gerar_convites(
    client_admin: APIClient, client_diretor: APIClient, diretor: Usuario, admin: Usuario
) -> None:
    assert client_diretor.post(CONVITES).status_code == 403

    resposta = _acao(client_admin, diretor, "tornar-admin")

    assert resposta.status_code == 200
    assert resposta.json()["admin"] is True
    assert client_diretor.post(CONVITES).status_code == 201
    historico = auditoria.historico_do_item("usuario", diretor.id)
    assert [(r.acao, r.ator_id) for r in historico] == [("PAPEL_DE_ADMIN_DADO", admin.id)]


def test_um_admin_tira_o_papel_de_outro_admin(
    client_admin: APIClient, client_diretor: APIClient, diretor: Usuario
) -> None:
    _acao(client_admin, diretor, "tornar-admin")

    resposta = _acao(client_admin, diretor, "remover-admin")

    assert resposta.status_code == 200
    assert resposta.json()["admin"] is False
    assert client_diretor.post(CONVITES).status_code == 403
    historico = auditoria.historico_do_item("usuario", diretor.id)
    assert [r.acao for r in historico] == ["PAPEL_DE_ADMIN_DADO", "PAPEL_DE_ADMIN_REMOVIDO"]


def test_um_admin_pode_desativar_outro_admin_e_sempre_sobra_um(
    client_admin: APIClient, diretor: Usuario
) -> None:
    _acao(client_admin, diretor, "tornar-admin")

    resposta = _acao(client_admin, diretor, "desativar")

    assert resposta.status_code == 200
    assert Usuario.objects.filter(admin=True, situacao=Situacao.ATIVO).count() == 1


@pytest.mark.parametrize("acao", ACOES)
def test_ca32_quem_nao_e_admin_nao_administra_usuarios(
    client_diretor: APIClient, admin: Usuario, acao: str
) -> None:
    como_diretor = _acao(client_diretor, admin, acao)
    sem_sessao = _acao(APIClient(), admin, acao)

    assert como_diretor.status_code == 403
    assert sem_sessao.status_code == 401
    atual = Usuario.objects.get(pk=admin.pk)
    assert atual.situacao == Situacao.ATIVO
    assert atual.admin is True


def test_ca32_quem_nao_e_admin_nao_lista_usuarios(client_diretor: APIClient) -> None:
    assert client_diretor.get(URL).status_code == 403
    assert APIClient().get(URL).status_code == 401


def test_servico_recusa_quem_nao_e_admin_mesmo_sem_passar_pela_rota(diretor: Usuario, admin: Usuario) -> None:
    with pytest.raises(BusinessError) as erro:
        usuarios.desativar(ator=diretor, usuario_id=admin.id)

    assert erro.value.code == "PERMISSION_DENIED"


@pytest.mark.parametrize(
    ("situacao", "acao", "codigo"),
    [
        (Situacao.INATIVO, "desativar", "USUARIO_NAO_ESTA_ATIVO"),
        (Situacao.AGUARDANDO_VERIFICACAO, "desativar", "USUARIO_NAO_ESTA_ATIVO"),
        (Situacao.ATIVO, "reativar", "USUARIO_NAO_ESTA_INATIVO"),
        (Situacao.AGUARDANDO_VERIFICACAO, "reativar", "USUARIO_NAO_ESTA_INATIVO"),
        (Situacao.INATIVO, "tornar-admin", "USUARIO_NAO_ESTA_ATIVO"),
        (Situacao.ATIVO, "remover-admin", "USUARIO_NAO_E_ADMIN"),
    ],
)
def test_acao_fora_da_situacao_certa_e_recusada(
    client_admin: APIClient, situacao: Situacao, acao: str, codigo: str
) -> None:
    alvo = criar_diretor("edu", situacao)

    resposta = _acao(client_admin, alvo, acao)

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == codigo
    assert auditoria.historico_do_item("usuario", alvo.id) == []


def test_usuario_que_nao_existe_devolve_404(client_admin: APIClient) -> None:
    resposta = client_admin.post(f"{URL}019a0000-0000-7000-8000-000000000000/desativar/")

    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "NOT_FOUND"


def test_api_publica_do_modulo_entrega_dados_sem_expor_o_modelo(admin: Usuario, diretor: Usuario) -> None:
    criar_diretor("dani", Situacao.INATIVO)
    Usuario.objects.filter(nome_de_usuario="dani").update(admin=True)

    info = public.usuario_por_id(diretor.id)
    admins = public.admins_ativos()

    assert info is not None
    assert (info.id, info.nome, info.email, info.admin, info.ativo) == (
        diretor.id,
        "Diretor bia",
        "bia@exemplo.com",
        False,
        True,
    )
    assert not isinstance(info, Usuario)
    assert [a.id for a in admins] == [admin.id]
    assert public.usuario_por_id(admin.id).admin is True  # type: ignore[union-attr]
