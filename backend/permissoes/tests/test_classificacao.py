"""Classificação de diretores (CA-07 a CA-12; PER-R08, PER-R09)."""

import uuid
from typing import Any

import pytest
from rest_framework.test import APIClient

from auditoria import public as auditoria
from kernel.errors import BusinessError
from permissoes import public as permissoes
from permissoes.models import Cargo, Classificacao, Setor
from permissoes.services import classificacao
from tests.apoio import Situacao, Usuario, criar_diretor

pytestmark = pytest.mark.django_db

BASE = "/api/v1/permissoes/"


def _url(usuario: Usuario) -> str:
    return f"{BASE}usuarios/{usuario.id}/classificacao/"


def _cargo(nome: str = "Tesoureiro") -> Cargo:
    return Cargo.objects.get(nome=nome)


def _setor(nome: str = "Financeiro") -> Setor:
    return Setor.objects.get(nome=nome)


def _corpo(cargo: Cargo | None, *setores: Setor) -> dict[str, Any]:
    return {"cargo_id": str(cargo.id) if cargo else None, "setor_ids": [str(s.id) for s in setores]}


def _erro(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def test_ca07_diretor_sem_cargo_recebe_cargo_e_dois_setores(
    client_admin: APIClient, diretor: Usuario
) -> None:
    resposta = client_admin.put(_url(diretor), _corpo(_cargo(), _setor("Financeiro"), _setor("Eventos")))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["cargo"]["nome"] == "Tesoureiro"
    assert sorted(s["nome"] for s in corpo["setores"]) == ["Eventos", "Financeiro"]
    info = permissoes.classificacao_de(diretor.id)
    assert info is not None
    assert info.cargo.nome == "Tesoureiro"
    assert sorted(s.nome for s in info.setores) == ["Eventos", "Financeiro"]


def test_classificar_audita_no_item_do_usuario_com_os_ids(
    client_admin: APIClient, admin: Usuario, diretor: Usuario
) -> None:
    cargo, setor = _cargo(), _setor()

    client_admin.put(_url(diretor), _corpo(cargo, setor))

    (registro,) = auditoria.historico_do_item("usuario", diretor.id)
    assert (registro.acao, registro.ator_id) == ("USUARIO_CLASSIFICADO", admin.id)
    assert registro.dados == {"cargo_id": str(cargo.id), "setor_ids": [str(setor.id)]}


def test_ca08_reclassificar_vale_na_requisicao_seguinte_do_diretor(
    client_admin: APIClient, diretor: Usuario, client_diretor: APIClient
) -> None:
    client_admin.put(_url(diretor), _corpo(_cargo("Tesoureiro"), _setor("Financeiro")))
    antes = client_diretor.get(f"{BASE}minhas/").json()

    client_admin.put(_url(diretor), _corpo(_cargo("Secretário"), _setor("Futebol")))
    depois = client_diretor.get(f"{BASE}minhas/").json()

    assert antes["cargo"]["nome"] == "Tesoureiro"
    assert depois["cargo"]["nome"] == "Secretário"
    assert [s["nome"] for s in depois["setores"]] == ["Futebol"]
    assert Classificacao.objects.filter(usuario_id=diretor.id).count() == 1


def test_ca09_tirar_o_cargo_remove_cargo_e_setores_e_audita(
    client_admin: APIClient, admin: Usuario, diretor: Usuario
) -> None:
    client_admin.put(_url(diretor), _corpo(_cargo(), _setor()))

    resposta = client_admin.put(_url(diretor), _corpo(None))

    assert resposta.status_code == 200
    assert resposta.json()["cargo"] is None
    assert resposta.json()["setores"] == []
    assert permissoes.classificacao_de(diretor.id) is None
    assert not Classificacao.objects.filter(usuario_id=diretor.id).exists()
    acoes = [r.acao for r in auditoria.historico_do_item("usuario", diretor.id)]
    assert acoes == ["USUARIO_CLASSIFICADO", "CLASSIFICACAO_REMOVIDA"]
    removida = auditoria.historico_do_item("usuario", diretor.id)[-1]
    assert removida.dados == {"cargo_id": str(_cargo().id), "setor_ids": [str(_setor().id)]}


def test_tirar_o_cargo_de_quem_nao_tem_e_inofensivo_e_nao_audita(
    client_admin: APIClient, diretor: Usuario
) -> None:
    resposta = client_admin.put(_url(diretor), _corpo(None))

    assert resposta.status_code == 200
    assert auditoria.historico_do_item("usuario", diretor.id) == []


@pytest.mark.parametrize("situacao", [Situacao.INATIVO, Situacao.AGUARDANDO_VERIFICACAO])
def test_ca10_usuario_que_nao_esta_ativo_nao_e_classificado(
    client_admin: APIClient, situacao: Situacao
) -> None:
    alvo = criar_diretor("inativo", situacao=situacao)

    resposta = client_admin.put(_url(alvo), _corpo(_cargo()))

    assert _erro(resposta) == (422, "USUARIO_NAO_ESTA_ATIVO")
    assert not Classificacao.objects.exists()


def test_usuario_inexistente_e_404(client_admin: APIClient) -> None:
    resposta = client_admin.put(f"{BASE}usuarios/{uuid.uuid4()}/classificacao/", _corpo(_cargo()))

    assert _erro(resposta) == (404, "NOT_FOUND")


def test_ca11_cargo_desativado_nao_e_atribuido(client_admin: APIClient, diretor: Usuario) -> None:
    cargo = _cargo()
    cargo.desativar()
    cargo.save()

    resposta = client_admin.put(_url(diretor), _corpo(cargo))

    assert _erro(resposta) == (422, "CARGO_INATIVO")
    assert not Classificacao.objects.exists()


def test_ca11_setor_desativado_nao_e_atribuido(client_admin: APIClient, diretor: Usuario) -> None:
    setor = _setor()
    setor.desativar()
    setor.save()

    resposta = client_admin.put(_url(diretor), _corpo(_cargo(), _setor("Eventos"), setor))

    assert _erro(resposta) == (422, "SETOR_INATIVO")
    assert not Classificacao.objects.exists()


def test_setores_sem_cargo_sao_recusados_com_o_campo_apontado(
    client_admin: APIClient, diretor: Usuario
) -> None:
    resposta = client_admin.put(_url(diretor), _corpo(None, _setor()))

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "setor_ids" in resposta.json()["error"]["details"]


def test_cargo_inexistente_e_validation_error(client_admin: APIClient, diretor: Usuario) -> None:
    resposta = client_admin.put(_url(diretor), {"cargo_id": str(uuid.uuid4()), "setor_ids": []})

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "cargo_id" in resposta.json()["error"]["details"]


def test_setor_inexistente_e_validation_error(client_admin: APIClient, diretor: Usuario) -> None:
    corpo = {"cargo_id": str(_cargo().id), "setor_ids": [str(uuid.uuid4())]}

    resposta = client_admin.put(_url(diretor), corpo)

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "setor_ids" in resposta.json()["error"]["details"]


def test_entrada_malformada_e_validation_error(client_admin: APIClient, diretor: Usuario) -> None:
    resposta = client_admin.put(_url(diretor), {"cargo_id": "nao-e-uuid", "setor_ids": "x"})

    assert _erro(resposta) == (400, "VALIDATION_ERROR")


def test_setor_repetido_na_lista_vale_uma_vez(client_admin: APIClient, diretor: Usuario) -> None:
    setor = _setor()

    resposta = client_admin.put(_url(diretor), _corpo(_cargo(), setor, setor))

    assert resposta.status_code == 200
    assert [s["nome"] for s in resposta.json()["setores"]] == ["Financeiro"]


def test_ca12_quem_nao_e_admin_nao_classifica(client_diretor: APIClient, diretor: Usuario) -> None:
    resposta = client_diretor.put(_url(diretor), _corpo(_cargo()))

    assert _erro(resposta) == (403, "PERMISSION_DENIED")
    assert not Classificacao.objects.exists()


def test_ca12_o_servico_tambem_recusa_quem_nao_e_admin(diretor: Usuario) -> None:
    with pytest.raises(BusinessError) as erro:
        classificacao.classificar(diretor.id, diretor.id, _cargo().id, [])

    assert (erro.value.code, erro.value.status) == ("PERMISSION_DENIED", 403)
    assert not Classificacao.objects.exists()


def test_sem_sessao_e_401(client: APIClient, diretor: Usuario) -> None:
    resposta = client.put(_url(diretor), _corpo(_cargo()))

    assert _erro(resposta) == (401, "NOT_AUTHENTICATED")


def test_diretor_classificado_le_gestao_e_perde_ao_ficar_sem_cargo(
    client_admin: APIClient, diretor: Usuario
) -> None:
    antes = permissoes.le_gestao(diretor.id)
    client_admin.put(_url(diretor), _corpo(_cargo()))
    com_cargo = permissoes.le_gestao(diretor.id)
    client_admin.put(_url(diretor), _corpo(None))

    assert (antes, com_cargo, permissoes.le_gestao(diretor.id)) == (False, True, False)
