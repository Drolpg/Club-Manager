"""Histórico de cargo e setor, o de convite para quem gerencia convites, e a ausência de rotas de apagar
(CA-30, CA-31, CA-32)."""

import uuid
from typing import Any

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from auditoria import public as auditoria
from permissoes.catalogo import CONVITES_GERENCIAR
from permissoes.domain.resolucao import ACESSO_TOTAL
from permissoes.models import Cargo, Concessao, Setor
from permissoes.services import concessoes
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

BASE = "/api/v1/permissoes/"
CONVITES = "/api/v1/acesso/convites/"
TIPOS = [("cargos", Cargo), ("setores", Setor)]
por_tipo = pytest.mark.parametrize(("rota", "modelo"), TIPOS)


def _erro(resposta: Any) -> tuple[int, str]:
    return int(resposta.status_code), str(resposta.json()["error"]["code"])


@por_tipo
def test_ca30_historico_do_item_vem_do_mais_recente_com_o_nome_do_ator(
    client_admin: APIClient, rota: str, modelo: Any
) -> None:
    criado = client_admin.post(f"{BASE}{rota}/", {"nome": "Marketing"}).json()
    client_admin.post(f"{BASE}{rota}/{criado['id']}/renomear/", {"nome": "Marketing Digital"})
    client_admin.post(f"{BASE}{rota}/{criado['id']}/desativar/")

    resposta = client_admin.get(f"{BASE}{rota}/{criado['id']}/historico/")

    assert resposta.status_code == 200
    itens = resposta.json()
    prefixo = "CARGO" if modelo is Cargo else "SETOR"
    assert [i["acao"] for i in itens] == [
        f"{prefixo}_DESATIVADO",
        f"{prefixo}_RENOMEADO",
        f"{prefixo}_CRIADO",
    ]
    assert {i["ator"]["nome"] for i in itens} == {"Ana Admin"}
    assert set(itens[0]) == {"acao", "ator", "justificativa", "criado_em"}


@por_tipo
def test_historico_do_cargo_ou_setor_inclui_as_concessoes(
    client_admin: APIClient, admin: Usuario, rota: str, modelo: Any
) -> None:
    alvo = modelo.objects.order_by("nome").first()
    concessao, _ = concessoes.conceder(
        admin.id, CONVITES_GERENCIAR, "CARGO" if modelo is Cargo else "SETOR", alvo.id
    )
    concessoes.revogar(admin.id, concessao.id)

    itens = client_admin.get(f"{BASE}{rota}/{alvo.id}/historico/").json()

    assert [i["acao"] for i in itens] == ["PERMISSAO_REVOGADA", "PERMISSAO_CONCEDIDA"]


@por_tipo
def test_historico_de_item_inexistente_e_404(client_admin: APIClient, rota: str, modelo: Any) -> None:
    assert _erro(client_admin.get(f"{BASE}{rota}/{uuid.uuid4()}/historico/")) == (404, "NOT_FOUND")


@por_tipo
def test_ca31_quem_nao_e_admin_nao_ve_o_historico(
    client_diretor: APIClient, client: APIClient, rota: str, modelo: Any
) -> None:
    alvo = modelo.objects.first()

    assert _erro(client_diretor.get(f"{BASE}{rota}/{alvo.id}/historico/")) == (403, "PERMISSION_DENIED")
    assert _erro(client.get(f"{BASE}{rota}/{alvo.id}/historico/")) == (401, "NOT_AUTHENTICATED")


def test_ca31_acesso_total_nao_abre_o_historico_de_administracao(
    admin: Usuario, diretor: Usuario, client_diretor: APIClient
) -> None:
    concessoes.conceder(admin.id, ACESSO_TOTAL, "USUARIO", diretor.id)
    cargo = Cargo.objects.first()
    assert cargo is not None

    resposta = client_diretor.get(f"{BASE}cargos/{cargo.id}/historico/")

    assert _erro(resposta) == (403, "PERMISSION_DENIED")


def test_ca30_quem_gerencia_convites_ve_o_historico_do_convite(
    admin: Usuario, diretor: Usuario, client_admin: APIClient, client_diretor: APIClient
) -> None:
    convite_id = client_admin.post(CONVITES).json()["id"]
    antes = client_diretor.get(f"{CONVITES}{convite_id}/historico/").status_code
    concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    resposta = client_diretor.get(f"{CONVITES}{convite_id}/historico/")

    assert (antes, resposta.status_code) == (403, 200)
    assert [i["acao"] for i in resposta.json()] == ["CONVITE_GERADO"]


def _rotas(padroes: list[Any], prefixo: str = "") -> list[tuple[str, URLPattern]]:
    achadas: list[tuple[str, URLPattern]] = []
    for padrao in padroes:
        caminho = prefixo + str(padrao.pattern)
        if isinstance(padrao, URLResolver):
            achadas += _rotas(padrao.url_patterns, caminho)
        elif isinstance(padrao, URLPattern):
            achadas.append((caminho, padrao))
    return achadas


def test_ca32_nenhuma_rota_de_permissoes_aceita_delete() -> None:
    rotas = [(c, p) for c, p in _rotas(get_resolver().url_patterns) if "permissoes/" in c]
    assert rotas

    com_delete = [
        caminho for caminho, padrao in rotas if hasattr(getattr(padrao.callback, "cls", None), "delete")
    ]

    assert com_delete == []


@pytest.mark.parametrize("metodo", ["delete", "patch"])
def test_ca32_apagar_cargo_setor_ou_concessao_nao_e_possivel(
    client_admin: APIClient, admin: Usuario, metodo: str
) -> None:
    concessao, _ = concessoes.conceder(admin.id, CONVITES_GERENCIAR, "USUARIO", admin.id)
    cargo, setor = Cargo.objects.first(), Setor.objects.first()
    assert cargo is not None
    assert setor is not None
    urls = [
        f"{BASE}cargos/",
        f"{BASE}cargos/{cargo.id}/",
        f"{BASE}setores/{setor.id}/",
        f"{BASE}concessoes/",
        f"{BASE}concessoes/{concessao.id}/",
        f"{BASE}concessoes/{concessao.id}/revogar/",
        f"{BASE}cargos/{cargo.id}/desativar/",
    ]

    status = [getattr(client_admin, metodo)(url).status_code for url in urls]

    assert all(codigo in (404, 405) for codigo in status), status
    assert Cargo.objects.filter(pk=cargo.pk).exists()
    assert Setor.objects.filter(pk=setor.pk).exists()
    assert Concessao.objects.filter(pk=concessao.pk, revogada_em__isnull=True).exists()


def test_ca29_toda_acao_da_regra_17_gera_registro_com_quem_o_que_quando_e_o_item(
    client_admin: APIClient, admin: Usuario, diretor: Usuario
) -> None:
    esperado: dict[tuple[str, uuid.UUID], list[str]] = {}

    def vai_para(item_tipo: str, item_id: Any, *acoes: str) -> None:
        esperado.setdefault((item_tipo, uuid.UUID(str(item_id))), []).extend(acoes)

    for rota, item, prefixo in (("cargos", "cargo", "CARGO"), ("setores", "setor", "SETOR")):
        novo = client_admin.post(f"{BASE}{rota}/", {"nome": "Novo"}).json()["id"]
        client_admin.post(f"{BASE}{rota}/{novo}/renomear/", {"nome": "Outro nome"})
        client_admin.post(f"{BASE}{rota}/{novo}/desativar/")
        client_admin.post(f"{BASE}{rota}/{novo}/reativar/")
        vai_para(item, novo, *(f"{prefixo}_{a}" for a in ("CRIADO", "RENOMEADO", "DESATIVADO", "REATIVADO")))
    cargo = Cargo.objects.get(nome="Diretor")
    client_admin.put(
        f"{BASE}usuarios/{diretor.id}/classificacao/", {"cargo_id": str(cargo.id), "setor_ids": []}
    )
    client_admin.put(f"{BASE}usuarios/{diretor.id}/classificacao/", {"cargo_id": None, "setor_ids": []})
    vai_para("usuario", diretor.id, "USUARIO_CLASSIFICADO", "CLASSIFICACAO_REMOVIDA")
    for permissao in (CONVITES_GERENCIAR, ACESSO_TOTAL):
        concessao = client_admin.post(
            f"{BASE}concessoes/",
            {"permissao": permissao, "alvo_tipo": "USUARIO", "alvo_id": str(diretor.id)},
        ).json()
        client_admin.post(f"{BASE}concessoes/{concessao['id']}/revogar/")
        vai_para("usuario", diretor.id, "PERMISSAO_CONCEDIDA", "PERMISSAO_REVOGADA")

    for (item_tipo, item_id), acoes in esperado.items():
        registros = auditoria.historico_do_item(item_tipo, item_id)
        assert [r.acao for r in registros] == acoes
        assert {r.ator_id for r in registros} == {admin.id}
        assert all(r.criado_em is not None and r.item_tipo == item_tipo for r in registros)
