"""Catálogo e concessões (CA-13, CA-23, CA-24; PER-R06, PER-R09)."""

import uuid
from typing import Any

import pytest
from rest_framework.test import APIClient

from auditoria import public as auditoria
from kernel.errors import BusinessError
from permissoes.catalogo import CONVITES_GERENCIAR
from permissoes.domain.resolucao import ACESSO_TOTAL
from permissoes.models import Cargo, Concessao, Setor
from permissoes.services import concessoes
from tests.apoio import Usuario, criar_diretor

pytestmark = pytest.mark.django_db

BASE = "/api/v1/permissoes/"


def _conceder(client: APIClient, permissao: str, alvo_tipo: str, alvo_id: Any) -> Any:
    corpo = {"permissao": permissao, "alvo_tipo": alvo_tipo, "alvo_id": str(alvo_id)}
    return client.post(f"{BASE}concessoes/", corpo)


def _erro(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def test_ca13_admin_ve_o_catalogo_com_nome_e_descricao(client_admin: APIClient) -> None:
    resposta = client_admin.get(f"{BASE}catalogo/")

    assert resposta.status_code == 200
    por_codigo = {p["codigo"]: p for p in resposta.json()}
    assert set(por_codigo[CONVITES_GERENCIAR]) == {"codigo", "nome", "descricao"}
    assert por_codigo[CONVITES_GERENCIAR]["nome"] == "Gerenciar convites"
    assert por_codigo[CONVITES_GERENCIAR]["descricao"]
    assert ACESSO_TOTAL in por_codigo
    assert list(por_codigo) == sorted(por_codigo)


def test_catalogo_e_negado_a_quem_nao_e_admin_e_a_quem_nao_tem_sessao(
    client_diretor: APIClient, client: APIClient
) -> None:
    assert _erro(client_diretor.get(f"{BASE}catalogo/")) == (403, "PERMISSION_DENIED")
    assert _erro(client.get(f"{BASE}catalogo/")) == (401, "NOT_AUTHENTICATED")


@pytest.mark.parametrize(
    ("alvo_tipo", "modelo", "item"),
    [("CARGO", Cargo, "cargo"), ("SETOR", Setor, "setor")],
)
def test_conceder_a_cargo_ou_setor_cria_e_audita_no_item_do_alvo(
    client_admin: APIClient, admin: Usuario, alvo_tipo: str, modelo: Any, item: str
) -> None:
    alvo = modelo.objects.get(nome="Tesoureiro" if modelo is Cargo else "Financeiro")

    resposta = _conceder(client_admin, CONVITES_GERENCIAR, alvo_tipo, alvo.id)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["permissao"] == CONVITES_GERENCIAR
    assert corpo["alvo_tipo"] == alvo_tipo
    assert corpo["alvo"] == {"id": str(alvo.id), "nome": alvo.nome}
    assert corpo["concedida_em"]
    (registro,) = auditoria.historico_do_item(item, alvo.id)
    assert (registro.acao, registro.ator_id) == ("PERMISSAO_CONCEDIDA", admin.id)
    assert registro.dados == {"permissao": CONVITES_GERENCIAR, "concessao_id": corpo["id"]}


def test_conceder_a_usuario_audita_no_historico_do_usuario(
    client_admin: APIClient, admin: Usuario, diretor: Usuario
) -> None:
    resposta = _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert resposta.status_code == 201
    assert resposta.json()["alvo"] == {"id": str(diretor.id), "nome": diretor.nome}
    (registro,) = auditoria.historico_do_item("usuario", diretor.id)
    assert (registro.acao, registro.ator_id) == ("PERMISSAO_CONCEDIDA", admin.id)


def test_ca23_conceder_duas_vezes_ao_mesmo_alvo_deixa_uma_concessao_so(
    client_admin: APIClient, diretor: Usuario
) -> None:
    primeira = _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    segunda = _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert (primeira.status_code, segunda.status_code) == (201, 200)
    assert primeira.json()["id"] == segunda.json()["id"]
    assert Concessao.objects.count() == 1
    assert len(auditoria.historico_do_item("usuario", diretor.id)) == 1


def test_conceder_de_novo_depois_de_revogar_cria_outra_concessao(
    client_admin: APIClient, diretor: Usuario
) -> None:
    primeira = _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id).json()
    client_admin.post(f"{BASE}concessoes/{primeira['id']}/revogar/")

    segunda = _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert segunda.status_code == 201
    assert segunda.json()["id"] != primeira["id"]
    assert Concessao.objects.count() == 2
    assert Concessao.objects.filter(revogada_em__isnull=True).count() == 1


def test_permissao_fora_do_catalogo_e_validation_error(client_admin: APIClient, diretor: Usuario) -> None:
    resposta = _conceder(client_admin, "inventada.total", "USUARIO", diretor.id)

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert Concessao.objects.count() == 0


@pytest.mark.parametrize("alvo_tipo", ["CARGO", "SETOR", "USUARIO"])
def test_alvo_inexistente_e_validation_error(client_admin: APIClient, alvo_tipo: str) -> None:
    resposta = _conceder(client_admin, CONVITES_GERENCIAR, alvo_tipo, uuid.uuid4())

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert Concessao.objects.count() == 0


def test_tipo_de_alvo_desconhecido_e_validation_error(client_admin: APIClient, diretor: Usuario) -> None:
    resposta = _conceder(client_admin, CONVITES_GERENCIAR, "TIME", diretor.id)

    assert _erro(resposta) == (400, "VALIDATION_ERROR")


@pytest.mark.parametrize(("alvo_tipo", "modelo"), [("CARGO", Cargo), ("SETOR", Setor)])
def test_per_r06_acesso_total_nao_e_concedido_a_cargo_nem_a_setor(
    client_admin: APIClient, alvo_tipo: str, modelo: Any
) -> None:
    alvo = modelo.objects.first()

    resposta = _conceder(client_admin, ACESSO_TOTAL, alvo_tipo, alvo.id)

    assert _erro(resposta) == (422, "ACESSO_TOTAL_SO_PARA_USUARIO")
    assert Concessao.objects.count() == 0


def test_acesso_total_e_concedido_a_usuario_e_audita(
    client_admin: APIClient, admin: Usuario, diretor: Usuario
) -> None:
    resposta = _conceder(client_admin, ACESSO_TOTAL, "USUARIO", diretor.id)

    assert resposta.status_code == 201
    (registro,) = auditoria.historico_do_item("usuario", diretor.id)
    assert registro.acao == "PERMISSAO_CONCEDIDA"
    assert registro.dados["permissao"] == ACESSO_TOTAL


def test_revogar_preenche_quem_e_quando_audita_e_nada_e_apagado(
    client_admin: APIClient, admin: Usuario, diretor: Usuario
) -> None:
    criada = _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id).json()

    resposta = client_admin.post(f"{BASE}concessoes/{criada['id']}/revogar/")

    assert resposta.status_code == 200
    concessao = Concessao.objects.get(pk=criada["id"])
    assert concessao.revogada_em is not None
    assert concessao.revogada_por_id == admin.id
    acoes = [r.acao for r in auditoria.historico_do_item("usuario", diretor.id)]
    assert acoes == ["PERMISSAO_CONCEDIDA", "PERMISSAO_REVOGADA"]


def test_revogar_concessao_de_cargo_audita_no_historico_do_cargo(client_admin: APIClient) -> None:
    cargo = Cargo.objects.get(nome="Tesoureiro")
    criada = _conceder(client_admin, CONVITES_GERENCIAR, "CARGO", cargo.id).json()

    client_admin.post(f"{BASE}concessoes/{criada['id']}/revogar/")

    acoes = [r.acao for r in auditoria.historico_do_item("cargo", cargo.id)]
    assert acoes == ["PERMISSAO_CONCEDIDA", "PERMISSAO_REVOGADA"]


def test_revogar_concessao_ja_revogada_e_recusado(client_admin: APIClient, diretor: Usuario) -> None:
    criada = _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id).json()
    client_admin.post(f"{BASE}concessoes/{criada['id']}/revogar/")

    resposta = client_admin.post(f"{BASE}concessoes/{criada['id']}/revogar/")

    assert _erro(resposta) == (422, "CONCESSAO_JA_REVOGADA")


def test_revogar_concessao_inexistente_e_404(client_admin: APIClient) -> None:
    resposta = client_admin.post(f"{BASE}concessoes/{uuid.uuid4()}/revogar/")

    assert _erro(resposta) == (404, "NOT_FOUND")


def test_lista_so_traz_concessoes_ativas_com_o_nome_do_alvo(
    client_admin: APIClient, diretor: Usuario
) -> None:
    cargo = Cargo.objects.get(nome="Tesoureiro")
    revogada = _conceder(client_admin, CONVITES_GERENCIAR, "CARGO", cargo.id).json()
    client_admin.post(f"{BASE}concessoes/{revogada['id']}/revogar/")
    _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    _conceder(client_admin, ACESSO_TOTAL, "USUARIO", diretor.id)

    resposta = client_admin.get(f"{BASE}concessoes/")

    assert resposta.status_code == 200
    itens = resposta.json()
    assert sorted(i["permissao"] for i in itens) == [ACESSO_TOTAL, CONVITES_GERENCIAR]
    assert {i["alvo"]["nome"] for i in itens} == {diretor.nome}
    assert all(i["alvo_tipo"] == "USUARIO" for i in itens)


def test_ca24_quem_nao_e_admin_nao_concede_nem_revoga(
    client_diretor: APIClient, client_admin: APIClient, diretor: Usuario
) -> None:
    criada = _conceder(client_admin, CONVITES_GERENCIAR, "USUARIO", diretor.id).json()

    conceder_comum = _conceder(client_diretor, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    conceder_total = _conceder(client_diretor, ACESSO_TOTAL, "USUARIO", diretor.id)
    revogar = client_diretor.post(f"{BASE}concessoes/{criada['id']}/revogar/")
    listar = client_diretor.get(f"{BASE}concessoes/")

    for resposta in (conceder_comum, conceder_total, revogar, listar):
        assert _erro(resposta) == (403, "PERMISSION_DENIED")
    assert Concessao.objects.get(pk=criada["id"]).revogada_em is None
    assert Concessao.objects.count() == 1


def test_ca24_sem_sessao_e_401(client: APIClient, diretor: Usuario) -> None:
    resposta = _conceder(client, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert _erro(resposta) == (401, "NOT_AUTHENTICATED")


def test_ca24_os_servicos_tambem_recusam_quem_nao_e_admin(admin: Usuario, diretor: Usuario) -> None:
    criada, _ = concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    outro = criar_diretor("outro")

    chamadas = (
        lambda: concessoes.conceder(outro.id, CONVITES_GERENCIAR, "USUARIO", outro.id),
        lambda: concessoes.revogar(outro.id, criada.id),
        lambda: concessoes.listar_ativas(outro.id),
    )

    for chamada in chamadas:
        with pytest.raises(BusinessError) as erro:
            chamada()
        assert (erro.value.code, erro.value.status) == ("PERMISSION_DENIED", 403)
    assert Concessao.objects.count() == 1
    assert Concessao.objects.get().revogada_em is None


def test_ca24_servico_recusa_usuario_inexistente_como_ator(diretor: Usuario) -> None:
    with pytest.raises(BusinessError) as erro:
        concessoes.listar_ativas(uuid.uuid4())

    assert erro.value.code == "PERMISSION_DENIED"


def test_conceder_devolve_a_concessao_e_se_foi_criada(admin: Usuario, diretor: Usuario) -> None:
    primeira, criada = concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    segunda, criada_de_novo = concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert (criada, criada_de_novo) == (True, False)
    assert primeira.id == segunda.id


def test_o_servico_recusa_tipo_de_alvo_desconhecido(admin: Usuario, diretor: Usuario) -> None:
    with pytest.raises(BusinessError) as erro:
        concessoes.conceder(admin.id, CONVITES_GERENCIAR, "TIME", diretor.id)

    assert (erro.value.code, erro.value.status) == ("VALIDATION_ERROR", 400)
