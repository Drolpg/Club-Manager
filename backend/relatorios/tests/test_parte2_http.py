"""As rotas HTTP do perfil (CA-01, CA-02, CA-04, CA-05), com `APIClient`.

Os dados vêm das rotas dos módulos donos, como faria outro cliente. A regra "dono ou admin" é do serviço.
"""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from auditoria import public as auditoria
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

BASE = "/api/v1/relatorios/perfil"


def _diretor(nome: str, *codigos: str) -> Usuario:
    usuario = apoio.criar_diretor(f"{nome}.dir")
    apoio.dar_cargo(usuario)
    for codigo in codigos:
        apoio.conceder(usuario, codigo)
    return usuario


@pytest.fixture
def cenario(db: None) -> dict[str, Usuario]:
    return {
        "ana": _diretor("ana", "eventos.propor"),
        "bia": _diretor("bia", "eventos.propor"),
        "total": _diretor("total", "acesso.total"),
        "emissor": _diretor("emissor", "cobrancas.criar"),
        "admin": apoio.criar_admin(),
    }


def _cobrar(cenario: dict[str, Usuario], devedor: Usuario, quantas: int = 1) -> None:
    c_admin = apoio.cliente_de(cenario["admin"])
    categoria = c_admin.post(
        "/api/v1/financeiro/categorias/", {"nome": "Taxa do perfil", "natureza": "ENTRADA"}, format="json"
    ).json()["id"]
    pix = c_admin.post(
        "/api/v1/financeiro/chaves-pix/",
        {
            "tipo": "EMAIL",
            "chave": "clube@clube.local",
            "nome_recebedor": "Clube",
            "cidade": "Curitiba",
            "padrao": True,
        },
        format="json",
    ).json()["id"]
    for n in range(quantas):
        resposta = apoio.cliente_de(cenario["emissor"]).post(
            "/api/v1/financeiro/cobrancas/",
            {
                "devedor_id": str(devedor.id),
                "categoria_id": categoria,
                "descricao": f"Cobrança {n}",
                "valor": "150.00",
                "vencimento": (timezone.localdate() + timedelta(days=5)).isoformat(),
                "chave_pix_id": pix,
            },
            format="json",
        )
        assert resposta.status_code == 201, resposta.content


def _propor_eventos(quem: Usuario, quantos: int) -> None:
    cliente = apoio.cliente_de(quem)
    referencias = cliente.get("/api/v1/eventos/referencias/").json()
    categoria = referencias["categorias"][0]["id"]
    for n in range(quantos):
        resposta = cliente.post(
            "/api/v1/eventos/",
            {
                "titulo": f"Evento {n}",
                "descricao": "",
                "inicio": (timezone.now() + timedelta(days=10 + n)).isoformat(),
                "local": "Campo",
                "categoria_id": categoria,
                "envolve_custo": False,
            },
            format="json",
        )
        assert resposta.status_code == 201, resposta.content


def _registros(alvo: Usuario) -> list[auditoria.Registro]:
    return [r for r in auditoria.historico_do_item("usuario", alvo.id) if r.acao == "PERFIL_CONSULTADO"]


def _codigo(resposta: Any) -> str:
    return str(resposta.json()["error"]["code"])


# --- sem sessão e sem permissão --------------------------------------------------------------------------

_ID = uuid.UUID(int=7)
_ROTAS = [
    f"{BASE}/",
    f"{BASE}/cobrancas/",
    f"{BASE}/eventos/",
    f"{BASE}/{_ID}/",
    f"{BASE}/{_ID}/cobrancas/",
    f"{BASE}/{_ID}/eventos/",
]


@pytest.mark.parametrize("rota", _ROTAS)
def test_sem_sessao_toda_rota_e_401(rota: str) -> None:
    assert APIClient().get(rota).status_code == 401


@pytest.mark.parametrize("rota", ["{}/{}/", "{}/{}/cobrancas/", "{}/{}/eventos/"])
@pytest.mark.parametrize("quem", ["bia", "total", "emissor"])
def test_diretor_vendo_o_de_outro_e_403_inclusive_com_leitura_total(
    cenario: dict[str, Usuario], quem: str, rota: str
) -> None:
    resposta = apoio.cliente_de(cenario[quem]).get(rota.format(BASE, cenario["ana"].id))

    assert resposta.status_code == 403
    assert _codigo(resposta) == "PERMISSION_DENIED"
    assert _registros(cenario["ana"]) == []


@pytest.mark.parametrize("rota", ["{}/{}/", "{}/{}/cobrancas/", "{}/{}/eventos/"])
def test_diretor_com_id_inexistente_tambem_e_403_e_nao_404(cenario: dict[str, Usuario], rota: str) -> None:
    resposta = apoio.cliente_de(cenario["bia"]).get(rota.format(BASE, uuid.uuid4()))

    assert (resposta.status_code, _codigo(resposta)) == (403, "PERMISSION_DENIED")


def test_o_403_vem_antes_do_400_de_um_limite_ruim(cenario: dict[str, Usuario]) -> None:
    cliente = apoio.cliente_de(cenario["bia"])

    resposta = cliente.get(f"{BASE}/{cenario['ana'].id}/cobrancas/", {"limite": "0"})

    assert resposta.status_code == 403


# --- o próprio perfil (CA-01 a CA-03) --------------------------------------------------------------------


def test_o_dono_ve_as_quatro_secoes_pelo_atalho_e_pelo_id(cenario: dict[str, Usuario]) -> None:
    ana = cenario["ana"]
    _cobrar(cenario, ana)
    _propor_eventos(ana, 1)
    cliente = apoio.cliente_de(ana)

    atalho = cliente.get(f"{BASE}/")
    por_id = cliente.get(f"{BASE}/{ana.id}/")

    assert atalho.status_code == por_id.status_code == 200
    corpo = atalho.json()
    assert corpo == por_id.json()
    assert set(corpo) == {"dados", "cobrancas", "eventos", "notificacoes"}
    assert corpo["dados"]["email"] == ana.email
    assert corpo["dados"]["telefone"] == "11988887777"
    assert corpo["dados"]["cargo"] == "Diretor"
    assert [c["descricao"] for c in corpo["cobrancas"]["itens"]] == ["Cobrança 0"]
    assert corpo["cobrancas"]["itens"][0]["valor"] == "150.00"
    assert corpo["cobrancas"]["itens"][0]["pagamentos"] == []
    assert [e["titulo"] for e in corpo["eventos"]["itens"]] == ["Evento 0"]
    assert corpo["eventos"]["itens"][0]["papel"] == "PROPONENTE"
    assert set(corpo["notificacoes"]) == {"nao_lidas"}
    assert _registros(ana) == []


def test_o_dono_ve_so_o_que_e_dele(cenario: dict[str, Usuario]) -> None:
    ana, bia = cenario["ana"], cenario["bia"]
    _cobrar(cenario, bia)
    _propor_eventos(bia, 1)

    corpo = apoio.cliente_de(ana).get(f"{BASE}/").json()

    assert corpo["cobrancas"]["itens"] == []
    assert corpo["eventos"]["itens"] == []


def test_a_saida_so_tem_campos_declarados_sem_hash_nem_identificador_do_google(
    cenario: dict[str, Usuario],
) -> None:
    ana = cenario["ana"]
    _cobrar(cenario, ana)
    _propor_eventos(ana, 1)

    corpo = apoio.cliente_de(ana).get(f"{BASE}/").json()

    assert set(corpo["dados"]) == {
        "id", "nome", "nome_de_usuario", "email", "telefone", "ativo", "admin", "cadastrado_em", "cargo",
        "setores",
    }  # fmt: skip
    assert set(corpo["cobrancas"]["itens"][0]) == {
        "id", "descricao", "categoria_nome", "valor", "vencimento", "situacao", "pagamentos",
    }  # fmt: skip
    assert set(corpo["eventos"]["itens"][0]) == {
        "id", "titulo", "inicio", "local", "categoria_nome", "situacao", "papel", "resposta",
    }  # fmt: skip
    texto = str(corpo).lower()
    assert "password" not in texto
    assert "google_sub" not in texto
    assert "comprovante" not in texto


def test_paginas_de_cobrancas_e_de_eventos_do_dono_por_cursor(cenario: dict[str, Usuario]) -> None:
    ana = cenario["ana"]
    _cobrar(cenario, ana, quantas=3)
    _propor_eventos(ana, 3)
    cliente = apoio.cliente_de(ana)

    cobrancas = cliente.get(f"{BASE}/cobrancas/", {"limite": "2"}).json()
    mais = cliente.get(f"{BASE}/cobrancas/", {"limite": "2", "antes": cobrancas["itens"][-1]["id"]}).json()
    eventos = cliente.get(f"{BASE}/eventos/", {"limite": "2"}).json()
    mais_eventos = cliente.get(
        f"{BASE}/eventos/", {"limite": "2", "antes": eventos["itens"][-1]["id"]}
    ).json()

    assert (len(cobrancas["itens"]), cobrancas["tem_mais"]) == (2, True)
    assert (len(mais["itens"]), mais["tem_mais"]) == (1, False)
    assert (len(eventos["itens"]), eventos["tem_mais"]) == (2, True)
    assert (len(mais_eventos["itens"]), mais_eventos["tem_mais"]) == (1, False)
    assert set(cobrancas) == {"itens", "tem_mais"}


@pytest.mark.parametrize("limite", ["0", "51", "-3", "abc"])
def test_limite_invalido_e_400_no_campo(cenario: dict[str, Usuario], limite: str) -> None:
    cliente = apoio.cliente_de(cenario["ana"])

    for rota in (f"{BASE}/cobrancas/", f"{BASE}/eventos/"):
        resposta = cliente.get(rota, {"limite": limite})
        assert resposta.status_code == 400
        assert _codigo(resposta) == "VALIDATION_ERROR"
        assert "limite" in resposta.json()["error"]["details"]


def test_cursor_inexistente_ou_mal_formado_e_404(cenario: dict[str, Usuario]) -> None:
    cliente = apoio.cliente_de(cenario["ana"])

    for antes in (str(uuid.uuid4()), "nao-e-uuid"):
        resposta = cliente.get(f"{BASE}/cobrancas/", {"antes": antes})
        assert (resposta.status_code, _codigo(resposta)) == (404, "NOT_FOUND")


# --- o admin vendo outro (CA-05) -------------------------------------------------------------------------


def test_o_admin_ve_o_perfil_de_outro_sem_notificacoes_e_deixa_registro(
    cenario: dict[str, Usuario],
) -> None:
    ana, admin = cenario["ana"], cenario["admin"]
    _cobrar(cenario, ana)

    resposta = apoio.cliente_de(admin).get(f"{BASE}/{ana.id}/")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == {"dados", "cobrancas", "eventos"}
    assert "notificacoes" not in corpo
    assert corpo["dados"]["email"] == ana.email
    assert [c["descricao"] for c in corpo["cobrancas"]["itens"]] == ["Cobrança 0"]
    registros = _registros(ana)
    assert sorted(r.dados["secao"] for r in registros) == ["cobrancas", "dados", "eventos"]
    assert {r.ator_id for r in registros} == {admin.id}


def test_cada_rota_do_admin_audita_a_sua_secao(cenario: dict[str, Usuario]) -> None:
    ana, admin = cenario["ana"], cenario["admin"]
    cliente = apoio.cliente_de(admin)

    assert cliente.get(f"{BASE}/{ana.id}/cobrancas/").status_code == 200
    assert cliente.get(f"{BASE}/{ana.id}/eventos/").status_code == 200

    assert sorted(r.dados["secao"] for r in _registros(ana)) == ["cobrancas", "eventos"]


def test_o_admin_com_alvo_inexistente_e_404(cenario: dict[str, Usuario]) -> None:
    cliente = apoio.cliente_de(cenario["admin"])

    for rota in ("{}/{}/", "{}/{}/cobrancas/", "{}/{}/eventos/"):
        resposta = cliente.get(rota.format(BASE, uuid.uuid4()))
        assert (resposta.status_code, _codigo(resposta)) == (404, "NOT_FOUND")


def test_o_admin_ve_o_proprio_perfil_com_notificacoes_e_sem_registro(cenario: dict[str, Usuario]) -> None:
    admin = cenario["admin"]

    corpo = apoio.cliente_de(admin).get(f"{BASE}/").json()

    assert corpo["notificacoes"] == {"nao_lidas": 0}
    assert _registros(admin) == []


def test_a_resposta_nunca_traz_a_caixa_do_outro_mesmo_com_notificacoes_dele(
    cenario: dict[str, Usuario],
) -> None:
    ana, admin = cenario["ana"], cenario["admin"]
    _cobrar(cenario, ana)  # a criação de cobrança notifica o devedor
    assert apoio.cliente_de(ana).get(f"{BASE}/").json()["notificacoes"]["nao_lidas"] >= 1

    corpo = apoio.cliente_de(admin).get(f"{BASE}/{ana.id}/").json()

    assert "notificacoes" not in corpo


# --- métodos e esquema OpenAPI ---------------------------------------------------------------------------


@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
def test_nao_ha_rota_de_escrita_em_relatorios(cenario: dict[str, Usuario], metodo: str) -> None:
    resposta = getattr(apoio.cliente_de(cenario["ana"]), metodo)(f"{BASE}/")

    assert resposta.status_code == 405


def test_o_esquema_openapi_traz_as_rotas_novas_so_para_o_admin(cenario: dict[str, Usuario]) -> None:
    cabecalho = {"Accept": "application/json"}

    negado = apoio.cliente_de(cenario["ana"]).get("/api/v1/schema/", headers=cabecalho)
    esquema = apoio.cliente_de(cenario["admin"]).get("/api/v1/schema/", headers=cabecalho)

    assert negado.status_code == 403
    caminhos = esquema.json()["paths"]
    for esperado in (
        "/api/v1/relatorios/perfil/",
        "/api/v1/relatorios/perfil/cobrancas/",
        "/api/v1/relatorios/perfil/eventos/",
        "/api/v1/relatorios/perfil/{usuario_id}/",
        "/api/v1/relatorios/perfil/{usuario_id}/cobrancas/",
        "/api/v1/relatorios/perfil/{usuario_id}/eventos/",
        "/api/v1/acesso/telefone/",
    ):
        assert esperado in caminhos
