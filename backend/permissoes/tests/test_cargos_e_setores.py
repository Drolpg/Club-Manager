from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection
from rest_framework.test import APIClient

from auditoria import public as auditoria
from permissoes.models import Cargo, Classificacao, Concessao, Setor
from tests.apoio import Situacao, Usuario, criar_diretor

pytestmark = pytest.mark.django_db

BASE = "/api/v1/permissoes/"
TIPOS = [("cargos", Cargo, "cargo", "CARGO"), ("setores", Setor, "setor", "SETOR")]
por_tipo = pytest.mark.parametrize(("rota", "modelo", "item", "prefixo"), TIPOS)


def _classificar(usuario: Usuario, cargo: Cargo, *setores: Setor) -> None:
    classificacao = Classificacao.objects.create(usuario_id=usuario.id, cargo=cargo)
    classificacao.setores.set(setores)


def test_ca01_sistema_nasce_com_quatro_setores_e_cinco_cargos_sem_permissao() -> None:
    assert sorted(Setor.objects.values_list("nome", flat=True)) == [
        "Eventos",
        "Financeiro",
        "Futebol",
        "Operacional",
    ]
    assert sorted(Cargo.objects.values_list("nome", flat=True)) == [
        "Diretor",
        "Presidente",
        "Secretário",
        "Tesoureiro",
        "Vice-presidente",
    ]
    assert all(Cargo.objects.values_list("ativo", flat=True))
    assert all(Setor.objects.values_list("ativo", flat=True))
    assert Concessao.objects.count() == 0
    assert Classificacao.objects.count() == 0


@por_tipo
def test_ca02_admin_cria_e_o_item_aparece_ativo_na_lista(
    client_admin: APIClient, admin: Usuario, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    resposta = client_admin.post(f"{BASE}{rota}/", {"nome": "  Marketing  "})

    assert resposta.status_code == 201
    assert resposta.json()["nome"] == "Marketing"
    assert resposta.json()["ativo"] is True
    nomes = [i["nome"] for i in client_admin.get(f"{BASE}{rota}/").json()]
    assert "Marketing" in nomes
    assert nomes == sorted(nomes)
    criado = modelo.objects.get(nome="Marketing")
    historico = auditoria.historico_do_item(item, criado.id)
    assert [(r.acao, r.ator_id) for r in historico] == [(f"{prefixo}_CRIADO", admin.id)]


@por_tipo
def test_ca03_nome_repetido_em_qualquer_caixa_e_recusado_ao_criar_e_ao_renomear(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    existente, outro = modelo.objects.order_by("nome")[:2]

    ao_criar = client_admin.post(f"{BASE}{rota}/", {"nome": existente.nome.upper()})
    ao_renomear = client_admin.post(f"{BASE}{rota}/{outro.id}/renomear/", {"nome": existente.nome.lower()})

    assert ao_criar.status_code == ao_renomear.status_code == 409
    assert ao_criar.json()["error"]["code"] == ao_renomear.json()["error"]["code"] == "NOME_EM_USO"
    assert modelo.objects.get(pk=outro.pk).nome == outro.nome


@por_tipo
def test_renomear_troca_o_nome_e_audita(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    alvo = modelo.objects.order_by("nome").first()

    resposta = client_admin.post(f"{BASE}{rota}/{alvo.id}/renomear/", {"nome": "Nome Novo"})

    assert resposta.status_code == 200
    assert modelo.objects.get(pk=alvo.pk).nome == "Nome Novo"
    assert [r.acao for r in auditoria.historico_do_item(item, alvo.id)] == [f"{prefixo}_RENOMEADO"]


@por_tipo
def test_renomear_para_o_proprio_nome_com_outra_caixa_e_permitido(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    alvo = modelo.objects.order_by("nome").first()

    resposta = client_admin.post(f"{BASE}{rota}/{alvo.id}/renomear/", {"nome": alvo.nome.upper()})

    assert resposta.status_code == 200


@por_tipo
@pytest.mark.parametrize("nome", ["", " ", "a", "x" * 61])
def test_nome_invalido_e_recusado(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str, nome: str
) -> None:
    resposta = client_admin.post(f"{BASE}{rota}/", {"nome": nome})

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "VALIDATION_ERROR"


@por_tipo
def test_ca04_item_sem_uso_e_desativado_e_pode_ser_reativado(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    alvo = modelo.objects.order_by("nome").first()

    desativado = client_admin.post(f"{BASE}{rota}/{alvo.id}/desativar/")
    reativado = client_admin.post(f"{BASE}{rota}/{alvo.id}/reativar/")

    assert desativado.status_code == 200
    assert desativado.json()["ativo"] is False
    assert reativado.json()["ativo"] is True
    acoes = [r.acao for r in auditoria.historico_do_item(item, alvo.id)]
    assert acoes == [f"{prefixo}_DESATIVADO", f"{prefixo}_REATIVADO"]


@por_tipo
def test_desativar_ou_reativar_fora_da_situacao_e_recusado(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    alvo = modelo.objects.order_by("nome").first()

    reativar_ativo = client_admin.post(f"{BASE}{rota}/{alvo.id}/reativar/")
    client_admin.post(f"{BASE}{rota}/{alvo.id}/desativar/")
    desativar_inativo = client_admin.post(f"{BASE}{rota}/{alvo.id}/desativar/")

    assert (reativar_ativo.status_code, reativar_ativo.json()["error"]["code"]) == (422, "JA_ESTA_ATIVO")
    assert (desativar_inativo.status_code, desativar_inativo.json()["error"]["code"]) == (
        422,
        "JA_ESTA_INATIVO",
    )


@por_tipo
def test_ca05_item_que_um_usuario_ativo_tem_nao_e_desativado(
    client_admin: APIClient, diretor: Usuario, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    cargo = Cargo.objects.get(nome="Tesoureiro")
    setor = Setor.objects.get(nome="Financeiro")
    _classificar(diretor, cargo, setor)
    alvo = cargo if modelo is Cargo else setor

    resposta = client_admin.post(f"{BASE}{rota}/{alvo.id}/desativar/")

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == f"{prefixo}_EM_USO"
    assert resposta.json()["error"]["details"] == {"usuarios": 1}
    assert modelo.objects.get(pk=alvo.pk).ativo is True


@por_tipo
def test_item_usado_so_por_usuario_inativo_pode_ser_desativado(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    inativo = criar_diretor("dani", Situacao.INATIVO)
    cargo = Cargo.objects.get(nome="Tesoureiro")
    setor = Setor.objects.get(nome="Financeiro")
    _classificar(inativo, cargo, setor)
    alvo = cargo if modelo is Cargo else setor

    resposta = client_admin.post(f"{BASE}{rota}/{alvo.id}/desativar/")

    assert resposta.status_code == 200


@por_tipo
@pytest.mark.parametrize("acao", ["criar", "renomear", "desativar", "reativar"])
def test_ca06_quem_nao_e_admin_nao_altera(
    client_diretor: APIClient, rota: str, modelo: Any, item: str, prefixo: str, acao: str
) -> None:
    alvo = modelo.objects.order_by("nome").first()
    url = f"{BASE}{rota}/" if acao == "criar" else f"{BASE}{rota}/{alvo.id}/{acao}/"

    como_diretor = client_diretor.post(url, {"nome": "Qualquer"})
    sem_sessao = APIClient().post(url, {"nome": "Qualquer"})

    assert como_diretor.status_code == 403
    assert sem_sessao.status_code == 401
    assert modelo.objects.count() == (5 if modelo is Cargo else 4)
    assert modelo.objects.get(pk=alvo.pk).nome == alvo.nome


@por_tipo
def test_ca06_diretor_com_cargo_lista_e_diretor_sem_cargo_nao(
    client_diretor: APIClient, diretor: Usuario, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    sem_cargo = client_diretor.get(f"{BASE}{rota}/")
    _classificar(diretor, Cargo.objects.get(nome="Diretor"))
    com_cargo = client_diretor.get(f"{BASE}{rota}/")

    assert sem_cargo.status_code == 403
    assert com_cargo.status_code == 200
    assert APIClient().get(f"{BASE}{rota}/").status_code == 401


@por_tipo
def test_item_que_nao_existe_devolve_404(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    resposta = client_admin.post(f"{BASE}{rota}/019a0000-0000-7000-8000-000000000000/desativar/")

    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "NOT_FOUND"


@por_tipo
def test_ca32_nao_ha_rota_para_apagar(
    client_admin: APIClient, rota: str, modelo: Any, item: str, prefixo: str
) -> None:
    alvo = modelo.objects.order_by("nome").first()

    assert client_admin.delete(f"{BASE}{rota}/{alvo.id}/").status_code in (404, 405)
    assert modelo.objects.filter(pk=alvo.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_migracoes_revertem_e_reaplicam_com_os_dados_iniciais() -> None:
    call_command("migrate", "permissoes", "zero", verbosity=0)
    assert "permissoes_cargo" not in connection.introspection.table_names()

    call_command("migrate", "permissoes", verbosity=0)
    assert Cargo.objects.count() == 5
    assert Setor.objects.count() == 4
