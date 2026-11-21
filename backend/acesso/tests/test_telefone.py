"""Telefone próprio (RF-143, CA-06): serviço e rota. A auditoria nunca leva o número, antigo ou novo."""

import pytest
from rest_framework.test import APIClient

from acesso.models import Usuario
from acesso.services import usuarios
from auditoria import public as auditoria
from kernel.errors import BusinessError

pytestmark = pytest.mark.django_db

ROTA = "/api/v1/acesso/telefone/"
ANTIGO = "11988887777"


def _registros(usuario: Usuario) -> list[str]:
    return [r.acao for r in auditoria.historico_do_item("usuario", usuario.id)]


def test_telefone_valido_e_normalizado_e_gravado(diretor: Usuario) -> None:
    usuarios.alterar_telefone(ator=diretor, telefone="+55 (11) 97777-6666")

    diretor.refresh_from_db()
    assert diretor.telefone == "+5511977776666"


def test_a_troca_audita_sem_o_numero(diretor: Usuario) -> None:
    usuarios.alterar_telefone(ator=diretor, telefone="(11) 97777-6666")

    registros = [
        r for r in auditoria.historico_do_item("usuario", diretor.id) if r.acao == "TELEFONE_ALTERADO"
    ]
    assert len(registros) == 1
    assert registros[0].dados == {}
    assert registros[0].ator_id == diretor.id
    texto = str(registros[0])
    for numero in ("977776666", ANTIGO, "5511"):
        assert numero not in texto


def test_o_mesmo_valor_nao_audita(diretor: Usuario) -> None:
    usuarios.alterar_telefone(ator=diretor, telefone="(11) 98888-7777")

    assert "TELEFONE_ALTERADO" not in _registros(diretor)


@pytest.mark.parametrize("telefone", ["", "   ", "1234567", "1" * 16, "abc12345678", "11 9888x7777"])
def test_telefone_invalido_e_recusado_e_nada_muda(diretor: Usuario, telefone: str) -> None:
    with pytest.raises(BusinessError) as erro:
        usuarios.alterar_telefone(ator=diretor, telefone=telefone)

    assert erro.value.code == "VALIDATION_ERROR"
    assert "telefone" in erro.value.details
    diretor.refresh_from_db()
    assert diretor.telefone == ANTIGO
    assert "TELEFONE_ALTERADO" not in _registros(diretor)


def test_usuario_inativo_nao_altera(diretor: Usuario) -> None:
    Usuario.objects.filter(pk=diretor.pk).update(situacao="INATIVO")
    diretor.refresh_from_db()

    with pytest.raises(BusinessError) as erro:
        usuarios.alterar_telefone(ator=diretor, telefone="11977776666")

    assert erro.value.code == "PERMISSION_DENIED"


def test_rota_altera_o_proprio_telefone(client_diretor: APIClient, diretor: Usuario) -> None:
    resposta = client_diretor.post(ROTA, {"telefone": "(21) 91234-5678"}, format="json")

    assert resposta.status_code == 200
    assert resposta.json() == {"telefone": "21912345678"}
    diretor.refresh_from_db()
    assert diretor.telefone == "21912345678"


def test_rota_com_o_mesmo_valor_responde_200(client_diretor: APIClient) -> None:
    resposta = client_diretor.post(ROTA, {"telefone": ANTIGO}, format="json")

    assert resposta.status_code == 200
    assert resposta.json() == {"telefone": ANTIGO}


@pytest.mark.parametrize("telefone", ["", "123", "1" * 16, "letras"])
def test_rota_recusa_telefone_invalido_no_campo(client_diretor: APIClient, telefone: str) -> None:
    resposta = client_diretor.post(ROTA, {"telefone": telefone}, format="json")

    assert resposta.status_code == 400
    erro = resposta.json()["error"]
    assert erro["code"] == "VALIDATION_ERROR"
    assert "telefone" in erro["details"]


def test_rota_sem_o_campo_telefone_e_400(client_diretor: APIClient) -> None:
    resposta = client_diretor.post(ROTA, {}, format="json")

    assert resposta.status_code == 400
    assert "telefone" in resposta.json()["error"]["details"]


@pytest.mark.parametrize(
    ("chave", "valor"),
    [
        ("nome", "Outro Nome"),
        ("email", "novo@exemplo.com"),
        ("nome_de_usuario", "novo.nome"),
        ("admin", True),
        ("usuario_id", "00000000-0000-0000-0000-000000000001"),
    ],
)
def test_rota_recusa_chave_estranha_e_nada_muda(
    client_diretor: APIClient, diretor: Usuario, chave: str, valor: object
) -> None:
    antes = (diretor.nome, diretor.email, diretor.nome_de_usuario, diretor.admin)

    resposta = client_diretor.post(ROTA, {"telefone": "11977776666", chave: valor}, format="json")

    assert resposta.status_code == 400
    erro = resposta.json()["error"]
    assert erro["code"] == "VALIDATION_ERROR"
    assert chave in erro["details"]
    diretor.refresh_from_db()
    assert (diretor.nome, diretor.email, diretor.nome_de_usuario, diretor.admin) == antes
    assert diretor.telefone == ANTIGO


def test_o_telefone_de_outro_nao_muda_pela_rota(client_diretor: APIClient, admin: Usuario) -> None:
    antes = admin.telefone

    client_diretor.post(ROTA, {"telefone": "11977776666"}, format="json")

    admin.refresh_from_db()
    assert admin.telefone == antes


def test_sem_sessao_e_401(client: APIClient) -> None:
    resposta = client.post(ROTA, {"telefone": "11977776666"}, format="json")

    assert resposta.status_code == 401


def test_o_numero_nao_aparece_em_nenhum_registro_de_auditoria(
    client_diretor: APIClient, diretor: Usuario
) -> None:
    client_diretor.post(ROTA, {"telefone": "21912345678"}, format="json")

    todos = " ".join(str(r) for r in auditoria.historico_do_item("usuario", diretor.id))
    assert "21912345678" not in todos
    assert ANTIGO not in todos
