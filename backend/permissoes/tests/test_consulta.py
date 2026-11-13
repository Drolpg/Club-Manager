"""Perguntas sobre o que um usuário pode (CA-14 a CA-22, CA-25, CA-26, CA-28; PER-R10) e a API pública."""

import uuid
from typing import Any

import pytest
from rest_framework.test import APIClient

from permissoes import catalogo
from permissoes import public as permissoes
from permissoes.catalogo import CONVITES_GERENCIAR
from permissoes.domain.resolucao import ACESSO_TOTAL, Origem, TipoDeOrigem
from permissoes.models import Cargo, Concessao, Setor
from permissoes.services import classificacao, concessoes
from tests.apoio import Usuario, cliente_de, criar_diretor

pytestmark = pytest.mark.django_db

BASE = "/api/v1/permissoes/"
ACESSO = "/api/v1/acesso/"


def _cargo(nome: str = "Tesoureiro") -> Cargo:
    return Cargo.objects.get(nome=nome)


def _setor(nome: str = "Financeiro") -> Setor:
    return Setor.objects.get(nome=nome)


def _classificar(admin: Usuario, usuario: Usuario, cargo: Cargo | None, *setores: Setor) -> None:
    classificacao.classificar(admin.id, usuario.id, cargo.id if cargo else None, [s.id for s in setores])


def _conceder(admin: Usuario, permissao: str, alvo_tipo: str, alvo_id: uuid.UUID) -> Concessao:
    concessao, _ = concessoes.conceder(admin.id, permissao, alvo_tipo, alvo_id)
    return concessao


def _revogar(admin: Usuario, concessao: Concessao) -> None:
    concessoes.revogar(admin.id, concessao.id)


def _pode(usuario: Usuario, codigo: str = CONVITES_GERENCIAR) -> bool:
    return permissoes.pode(usuario.id, codigo)


def test_ca14_permissao_concedida_a_um_cargo_vale_para_quem_tem_o_cargo(
    admin: Usuario, diretor: Usuario
) -> None:
    outro = criar_diretor("outro")
    _classificar(admin, diretor, _cargo("Tesoureiro"))
    _classificar(admin, outro, _cargo("Secretário"))

    _conceder(admin, CONVITES_GERENCIAR, "CARGO", _cargo("Tesoureiro").id)

    assert _pode(diretor) is True
    assert _pode(outro) is False


def test_ca15_permissao_concedida_a_um_setor_vale_para_quem_e_do_setor(
    admin: Usuario, diretor: Usuario
) -> None:
    outro = criar_diretor("outro")
    _classificar(admin, diretor, _cargo("Diretor"), _setor("Financeiro"), _setor("Eventos"))
    _classificar(admin, outro, _cargo("Diretor"), _setor("Futebol"))

    _conceder(admin, CONVITES_GERENCIAR, "SETOR", _setor("Eventos").id)

    assert _pode(diretor) is True
    assert _pode(outro) is False


def test_ca16_concessao_individual_vale_mesmo_fora_do_setor_de_origem(
    admin: Usuario, diretor: Usuario
) -> None:
    _classificar(admin, diretor, _cargo("Diretor"), _setor("Futebol"))
    _conceder(admin, CONVITES_GERENCIAR, "SETOR", _setor("Financeiro").id)
    assert _pode(diretor) is False

    _conceder(admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert _pode(diretor) is True


def test_ca16_concessao_individual_vale_ate_sem_classificacao(admin: Usuario, diretor: Usuario) -> None:
    _conceder(admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)

    assert _pode(diretor) is True


def test_ca17_a_permissao_dura_enquanto_restar_uma_concessao_ativa(admin: Usuario, diretor: Usuario) -> None:
    _classificar(admin, diretor, _cargo("Tesoureiro"), _setor("Financeiro"))
    pelo_cargo = _conceder(admin, CONVITES_GERENCIAR, "CARGO", _cargo("Tesoureiro").id)
    pelo_setor = _conceder(admin, CONVITES_GERENCIAR, "SETOR", _setor("Financeiro").id)

    _revogar(admin, pelo_cargo)
    com_uma = _pode(diretor)
    _revogar(admin, pelo_setor)

    assert com_uma is True
    assert _pode(diretor) is False


def test_ca18_cargo_ou_setor_desativado_deixa_de_conceder(admin: Usuario, diretor: Usuario) -> None:
    cargo, setor = _cargo("Tesoureiro"), _setor("Financeiro")
    _classificar(admin, diretor, cargo, setor)
    _conceder(admin, CONVITES_GERENCIAR, "CARGO", cargo.id)
    assert _pode(diretor) is True

    cargo.desativar()
    cargo.save()
    sem_o_cargo = _pode(diretor)
    _conceder(admin, CONVITES_GERENCIAR, "SETOR", setor.id)
    com_o_setor = _pode(diretor)
    setor.desativar()
    setor.save()

    assert (sem_o_cargo, com_o_setor, _pode(diretor)) == (False, True, False)


def test_ca19_usuario_desativado_nao_tem_permissao_e_reativado_volta_a_ter(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    _conceder(admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    assert _pode(diretor) is True

    client_admin.post(f"{ACESSO}usuarios/{diretor.id}/desativar/")
    desativado = (_pode(diretor), permissoes.permissoes_de(diretor.id))
    client_admin.post(f"{ACESSO}usuarios/{diretor.id}/reativar/")

    assert desativado == (False, {})
    assert _pode(diretor) is True


def test_ca20_admin_tem_todas_as_permissoes_do_catalogo_sem_concessao(
    admin: Usuario, permissoes_de_teste: tuple[str, str]
) -> None:
    comum, sensivel = permissoes_de_teste

    resultado = permissoes.permissoes_de(admin.id)

    assert {CONVITES_GERENCIAR, comum, sensivel} <= set(resultado)
    assert ACESSO_TOTAL not in resultado
    assert resultado[sensivel] == [Origem(TipoDeOrigem.ADMIN)]
    assert Concessao.objects.count() == 0


def test_ca21_acesso_total_da_tudo_menos_o_que_esta_fora_dele(
    admin: Usuario, diretor: Usuario, permissoes_de_teste: tuple[str, str]
) -> None:
    comum, sensivel = permissoes_de_teste
    _conceder(admin, ACESSO_TOTAL, "USUARIO", diretor.id)

    resultado = permissoes.permissoes_de(diretor.id)

    assert {CONVITES_GERENCIAR, comum} <= set(resultado)
    assert sensivel not in resultado
    assert _pode(diretor, sensivel) is False
    assert {o.tipo for o in resultado[comum]} == {TipoDeOrigem.ACESSO_TOTAL}


def test_ca21_acesso_total_nao_da_a_administracao(admin: Usuario, diretor: Usuario) -> None:
    alvo = criar_diretor("alvo")
    _conceder(admin, ACESSO_TOTAL, "USUARIO", diretor.id)
    client = cliente_de(diretor)
    cargo = _cargo()

    respostas = [
        client.get(f"{BASE}catalogo/"),
        client.get(f"{BASE}concessoes/"),
        client.get(f"{BASE}usuarios/{alvo.id}/"),
        client.post(f"{BASE}cargos/", {"nome": "Novo cargo"}),
        client.post(f"{BASE}setores/{_setor().id}/desativar/"),
        client.put(f"{BASE}usuarios/{alvo.id}/classificacao/", {"cargo_id": str(cargo.id), "setor_ids": []}),
        client.post(
            f"{BASE}concessoes/",
            {"permissao": CONVITES_GERENCIAR, "alvo_tipo": "USUARIO", "alvo_id": str(alvo.id)},
        ),
        client.post(f"{ACESSO}usuarios/{alvo.id}/tornar-admin/"),
    ]

    assert [r.status_code for r in respostas] == [403] * len(respostas)
    assert Concessao.objects.count() == 1


def test_ca22_presidente_sem_concessao_nao_tem_permissao_nenhuma(admin: Usuario, diretor: Usuario) -> None:
    _classificar(admin, diretor, _cargo("Presidente"), _setor("Financeiro"))

    assert permissoes.permissoes_de(diretor.id) == {}
    assert _pode(diretor) is False


def test_permissao_fora_do_catalogo_e_ignorada(
    admin: Usuario, diretor: Usuario, permissoes_de_teste: tuple[str, str]
) -> None:
    comum, _ = permissoes_de_teste
    _conceder(admin, comum, "USUARIO", diretor.id)
    assert _pode(diretor, comum) is True

    # O código sai do catálogo (um módulo que deixou de declará-lo): a concessão fica, sem efeito.
    catalogo.remover_para_testes(comum)

    assert _pode(diretor, comum) is False
    assert comum not in permissoes.permissoes_de(diretor.id)


def test_usuario_inexistente_nao_tem_nada() -> None:
    desconhecido = uuid.uuid4()

    assert permissoes.permissoes_de(desconhecido) == {}
    assert permissoes.pode(desconhecido, CONVITES_GERENCIAR) is False
    assert permissoes.le_gestao(desconhecido) is False
    assert permissoes.classificacao_de(desconhecido) is None


def test_ca28_le_gestao_so_com_cargo_e_ativo(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    sem_cargo = permissoes.le_gestao(diretor.id)
    _classificar(admin, diretor, _cargo("Diretor"))
    com_cargo = permissoes.le_gestao(diretor.id)
    client_admin.post(f"{ACESSO}usuarios/{diretor.id}/desativar/")

    assert (sem_cargo, com_cargo, permissoes.le_gestao(diretor.id)) == (False, True, False)
    assert permissoes.le_gestao(admin.id) is True


def test_le_gestao_nao_vale_com_o_cargo_desativado(admin: Usuario, diretor: Usuario) -> None:
    cargo = _cargo("Diretor")
    _classificar(admin, diretor, cargo)
    cargo.desativar()
    cargo.save()

    assert permissoes.le_gestao(diretor.id) is False


def test_classificacao_de_devolve_dataclass_com_cargo_e_setores(admin: Usuario, diretor: Usuario) -> None:
    _classificar(admin, diretor, _cargo("Tesoureiro"), _setor("Financeiro"), _setor("Eventos"))

    info = permissoes.classificacao_de(diretor.id)

    assert info is not None
    assert (info.cargo.id, info.cargo.nome, info.cargo.ativo) == (_cargo("Tesoureiro").id, "Tesoureiro", True)
    assert sorted(s.nome for s in info.setores) == ["Eventos", "Financeiro"]
    assert not isinstance(info.cargo, Cargo)


def test_quem_pode_une_as_origens_inclui_admin_e_exclui_inativo(
    admin: Usuario, client_admin: APIClient, permissoes_de_teste: tuple[str, str]
) -> None:
    pelo_cargo, pelo_setor, individual, total, inativo, sem_nada = (
        criar_diretor(nome)
        for nome in ("pelo.cargo", "pelo.setor", "individual", "total", "inativo", "sem.nada")
    )
    _classificar(admin, pelo_cargo, _cargo("Tesoureiro"))
    _classificar(admin, pelo_setor, _cargo("Diretor"), _setor("Eventos"))
    _classificar(admin, sem_nada, _cargo("Secretário"), _setor("Futebol"))
    _conceder(admin, CONVITES_GERENCIAR, "CARGO", _cargo("Tesoureiro").id)
    _conceder(admin, CONVITES_GERENCIAR, "SETOR", _setor("Eventos").id)
    _conceder(admin, CONVITES_GERENCIAR, "USUARIO", individual.id)
    _conceder(admin, ACESSO_TOTAL, "USUARIO", total.id)
    _conceder(admin, CONVITES_GERENCIAR, "USUARIO", inativo.id)
    client_admin.post(f"{ACESSO}usuarios/{inativo.id}/desativar/")

    quem = permissoes.quem_pode(CONVITES_GERENCIAR)

    assert set(quem) == {admin.id, pelo_cargo.id, pelo_setor.id, individual.id, total.id}
    assert len(quem) == len(set(quem))


def test_quem_pode_respeita_cargo_desativado_e_permissao_fora_do_acesso_total(
    admin: Usuario, diretor: Usuario, permissoes_de_teste: tuple[str, str]
) -> None:
    _, sensivel = permissoes_de_teste
    cargo = _cargo("Tesoureiro")
    _classificar(admin, diretor, cargo)
    _conceder(admin, CONVITES_GERENCIAR, "CARGO", cargo.id)
    outro = criar_diretor("outro")
    _conceder(admin, ACESSO_TOTAL, "USUARIO", outro.id)
    cargo.desativar()
    cargo.save()

    assert set(permissoes.quem_pode(CONVITES_GERENCIAR)) == {admin.id, outro.id}
    assert permissoes.quem_pode(sensivel) == [admin.id]
    assert permissoes.quem_pode("inventada.total") == []


def test_registrar_permissao_pela_api_publica_entra_no_catalogo(client_admin: APIClient) -> None:
    permissoes.registrar_permissao("teste.publica", "Pública de teste", "Registrada pela API pública.")
    try:
        codigos = [p["codigo"] for p in client_admin.get(f"{BASE}catalogo/").json()]
    finally:
        catalogo.remover_para_testes("teste.publica")

    assert "teste.publica" in codigos


def _detalhe(client: APIClient, url: str) -> dict[str, Any]:
    resposta = client.get(url)
    assert resposta.status_code == 200, resposta.content
    return dict(resposta.json())


def test_ca25_admin_ve_cada_permissao_com_todas_as_origens(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    _classificar(admin, diretor, _cargo("Tesoureiro"), _setor("Financeiro"))
    _conceder(admin, CONVITES_GERENCIAR, "CARGO", _cargo("Tesoureiro").id)
    _conceder(admin, CONVITES_GERENCIAR, "SETOR", _setor("Financeiro").id)
    _conceder(admin, CONVITES_GERENCIAR, "USUARIO", diretor.id)
    _conceder(admin, ACESSO_TOTAL, "USUARIO", diretor.id)

    corpo = _detalhe(client_admin, f"{BASE}usuarios/{diretor.id}/")

    assert corpo["cargo"] == {"id": str(_cargo("Tesoureiro").id), "nome": "Tesoureiro", "ativo": True}
    assert [s["nome"] for s in corpo["setores"]] == ["Financeiro"]
    (permissao,) = [p for p in corpo["permissoes"] if p["codigo"] == CONVITES_GERENCIAR]
    assert permissao["nome"] == "Gerenciar convites"
    assert [(o["tipo"], o["nome"]) for o in permissao["origens"]] == [
        ("CARGO", "Tesoureiro"),
        ("SETOR", "Financeiro"),
        ("INDIVIDUAL", None),
        ("ACESSO_TOTAL", None),
    ]
    assert permissao["origens"][0]["id"] == str(_cargo("Tesoureiro").id)
    assert ACESSO_TOTAL not in [p["codigo"] for p in corpo["permissoes"]]


def test_ca25_detalhe_de_usuario_sem_cargo_e_de_usuario_inexistente(
    client_admin: APIClient, diretor: Usuario
) -> None:
    corpo = _detalhe(client_admin, f"{BASE}usuarios/{diretor.id}/")
    inexistente = client_admin.get(f"{BASE}usuarios/{uuid.uuid4()}/")

    assert corpo == {"cargo": None, "setores": [], "permissoes": []}
    assert (inexistente.status_code, inexistente.json()["error"]["code"]) == (404, "NOT_FOUND")


def test_ca25_detalhe_de_outro_usuario_e_so_do_admin(client_diretor: APIClient, client: APIClient) -> None:
    alvo = criar_diretor("alvo")

    assert client_diretor.get(f"{BASE}usuarios/{alvo.id}/").status_code == 403
    assert client.get(f"{BASE}usuarios/{alvo.id}/").status_code == 401


def test_ca26_diretor_ve_o_proprio_cargo_setores_e_permissoes_e_nao_os_de_outro(
    admin: Usuario, diretor: Usuario, client_diretor: APIClient
) -> None:
    outro = criar_diretor("outro")
    _classificar(admin, diretor, _cargo("Tesoureiro"), _setor("Financeiro"))
    _classificar(admin, outro, _cargo("Secretário"), _setor("Futebol"))
    _conceder(admin, CONVITES_GERENCIAR, "SETOR", _setor("Financeiro").id)

    minhas = _detalhe(client_diretor, f"{BASE}minhas/")
    das_do_outro = _detalhe(cliente_de(outro), f"{BASE}minhas/")

    assert minhas["cargo"]["nome"] == "Tesoureiro"
    assert [s["nome"] for s in minhas["setores"]] == ["Financeiro"]
    assert [p["codigo"] for p in minhas["permissoes"]] == [CONVITES_GERENCIAR]
    assert das_do_outro["cargo"]["nome"] == "Secretário"
    assert das_do_outro["permissoes"] == []
    assert client_diretor.get(f"{BASE}usuarios/{outro.id}/").status_code == 403


def test_ca26_diretor_sem_cargo_ve_tudo_vazio(client_diretor: APIClient) -> None:
    assert _detalhe(client_diretor, f"{BASE}minhas/") == {"cargo": None, "setores": [], "permissoes": []}


def test_minhas_exige_sessao(client: APIClient) -> None:
    resposta = client.get(f"{BASE}minhas/")

    assert (resposta.status_code, resposta.json()["error"]["code"]) == (401, "NOT_AUTHENTICATED")
