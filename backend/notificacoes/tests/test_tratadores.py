"""Tratadores dos quatro eventos de integração (ADR-003): cada um gera a notificação certa, para quem deve.

As ações vêm da API HTTP dos outros módulos: `notificacoes` não importa os serviços deles, nem nos testes.
"""

import uuid
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.apps import apps
from django.core import mail
from rest_framework.test import APIClient

from acesso import public as acesso
from kernel import events
from notificacoes import tipos
from notificacoes.models import Notificacao, SituacaoDoEmail
from notificacoes.services import preferencias
from permissoes import public as permissoes
from tests.apoio import Situacao, Usuario, criar_diretor

pytestmark = pytest.mark.django_db

ACESSO = "/api/v1/acesso/"
PERMISSOES = "/api/v1/permissoes/"
# O código é contrato estável do catálogo; o teste não importa o catálogo de outro módulo.
CONVITES_GERENCIAR = "convites.gerenciar"
ACESSO_TOTAL = "acesso.total"


@pytest.fixture(autouse=True)
def _executar_na_hora_o_que_roda_depois_do_commit() -> Iterator[None]:
    with mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()):
        yield


def _do_tipo(codigo: str, **filtros: Any) -> list[Notificacao]:
    return list(Notificacao.objects.filter(tipo=codigo, **filtros).order_by("criada_em", "id"))


def _cargo_e_setor(client_admin: APIClient) -> tuple[dict[str, Any], dict[str, Any]]:
    cargo = next(c for c in client_admin.get(f"{PERMISSOES}cargos/").json() if c["nome"] == "Tesoureiro")
    setor = next(s for s in client_admin.get(f"{PERMISSOES}setores/").json() if s["nome"] == "Financeiro")
    return cargo, setor


def _classificar(
    client_admin: APIClient, usuario: Usuario, cargo: dict[str, Any] | None, *setores: Any
) -> None:
    corpo = {"cargo_id": cargo["id"] if cargo else None, "setor_ids": [s["id"] for s in setores]}
    resposta = client_admin.put(f"{PERMISSOES}usuarios/{usuario.id}/classificacao/", corpo, format="json")
    assert resposta.status_code == 200, resposta.content


def _conceder(client_admin: APIClient, usuario: Usuario, permissao: str) -> Any:
    return client_admin.post(
        f"{PERMISSOES}concessoes/",
        {"permissao": permissao, "alvo_tipo": "USUARIO", "alvo_id": str(usuario.id)},
        format="json",
    )


def _tornar_admin(client_admin: APIClient, usuario: Usuario) -> None:
    assert client_admin.post(f"{ACESSO}usuarios/{usuario.id}/tornar-admin/").status_code == 200


def test_o_ready_registra_os_quatro_tipos_do_modulo() -> None:
    esperados = {
        "acesso.cadastro_concluido": True,
        "permissoes.classificacao_alterada": False,
        "acesso.papel_de_admin_alterado": False,
        "permissoes.concessao_individual_alterada": False,
    }

    registrados = {t.codigo: t.pede_acao for t in tipos.listar() if t.codigo in esperados}

    assert registrados == esperados


def test_o_ready_registra_um_tratador_para_cada_evento_e_nao_duplica_ao_rodar_de_novo() -> None:
    tipos_de_evento = (
        acesso.CadastroConcluido,
        acesso.PapelDeAdminAlterado,
        permissoes.ClassificacaoAlterada,
        permissoes.ConcessaoIndividualAlterada,
    )
    antes = events.copiar_registro()

    apps.get_app_config("notificacoes").ready()
    depois = events.copiar_registro()

    assert all(len(depois[tipo]) == 1 for tipo in tipos_de_evento)
    assert depois == antes


def test_ca20_cadastro_concluido_notifica_todos_os_admins_ativos_com_pedido_de_acao(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    outro_admin = criar_diretor("beto")
    _tornar_admin(client_admin, outro_admin)
    inativo = criar_diretor("ines")
    _tornar_admin(client_admin, inativo)
    client_admin.post(f"{ACESSO}usuarios/{inativo.id}/desativar/")
    novo = criar_diretor("caio")
    mail.outbox.clear()

    events.publish(acesso.CadastroConcluido(usuario_id=novo.id))

    notificacoes = _do_tipo("acesso.cadastro_concluido")
    assert {n.destinatario_id for n in notificacoes} == {admin.id, outro_admin.id}
    for n in notificacoes:
        assert n.pede_acao is True
        assert n.titulo == "Novo diretor para classificar"
        assert "Diretor caio" in n.texto
        assert (n.item_tipo, n.item_id) == ("usuario", novo.id)
        assert n.caminho == f"/admin/usuarios/{novo.id}"
        assert n.chave == f"cadastro-concluido:{novo.id}"
    assert sorted(m.to[0] for m in mail.outbox) == sorted([admin.email, outro_admin.email])
    assert {m.subject for m in mail.outbox} == {"Novo diretor para classificar"}


def test_ca20_o_mesmo_cadastro_concluido_duas_vezes_gera_uma_notificacao_por_admin(
    admin: Usuario,
) -> None:
    novo = criar_diretor("caio")
    mail.outbox.clear()

    events.publish(acesso.CadastroConcluido(usuario_id=novo.id))
    events.publish(acesso.CadastroConcluido(usuario_id=novo.id))

    assert len(_do_tipo("acesso.cadastro_concluido")) == 1
    assert len(mail.outbox) == 1


def test_o_email_do_admin_nao_leva_dado_pessoal_do_novo_diretor(admin: Usuario) -> None:
    novo = criar_diretor("caio")
    mail.outbox.clear()

    events.publish(acesso.CadastroConcluido(usuario_id=novo.id))

    corpo = f"{mail.outbox[0].subject} {mail.outbox[0].body}"
    assert novo.email not in corpo
    assert novo.telefone not in corpo
    assert novo.nome_de_usuario not in corpo.replace(novo.nome, "")


def test_cadastro_concluido_sem_admin_ativo_nao_notifica_ninguem(diretor: Usuario) -> None:
    assert _do_tipo("acesso.cadastro_concluido") == []
    Usuario.objects.filter(admin=True).update(situacao=Situacao.INATIVO)
    novo = criar_diretor("caio")

    events.publish(acesso.CadastroConcluido(usuario_id=novo.id))

    assert Notificacao.objects.count() == 0


def test_ca21_classificar_notifica_o_diretor_com_o_cargo_e_os_setores(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    cargo, setor = _cargo_e_setor(client_admin)
    mail.outbox.clear()

    _classificar(client_admin, diretor, cargo, setor)

    (n,) = _do_tipo("permissoes.classificacao_alterada")
    assert n.destinatario_id == diretor.id
    assert n.pede_acao is False
    assert n.titulo == "Sua classificação mudou"
    assert "Tesoureiro" in n.texto
    assert "Financeiro" in n.texto
    assert (n.item_tipo, n.item_id, n.caminho) == ("usuario", diretor.id, "/")
    assert [m.to for m in mail.outbox] == [[diretor.email]]


def test_ca21_classificar_sem_setores_diz_que_nao_ha_setores(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    cargo, _ = _cargo_e_setor(client_admin)

    _classificar(client_admin, diretor, cargo)

    (n,) = _do_tipo("permissoes.classificacao_alterada")
    assert "Tesoureiro" in n.texto
    assert "sem setores" in n.texto.lower()


def test_ca21_cada_mudanca_gera_a_sua_notificacao(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    cargo, setor = _cargo_e_setor(client_admin)

    _classificar(client_admin, diretor, cargo, setor)
    _classificar(client_admin, diretor, cargo)
    _classificar(client_admin, diretor, None)

    textos = [n.texto for n in _do_tipo("permissoes.classificacao_alterada")]
    assert len(textos) == 3
    assert len({n.chave for n in _do_tipo("permissoes.classificacao_alterada")}) == 3
    assert "Financeiro" in textos[0]
    assert "Financeiro" not in textos[1]
    assert "sem cargo" in textos[2].lower()


def test_ca21_tirar_o_cargo_de_quem_nao_tinha_nao_notifica(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    _classificar(client_admin, diretor, None)

    assert _do_tipo("permissoes.classificacao_alterada") == []


def test_ca22_ganhar_e_perder_o_papel_de_admin_notifica_o_usuario(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    mail.outbox.clear()
    _tornar_admin(client_admin, diretor)
    assert client_admin.post(f"{ACESSO}usuarios/{diretor.id}/remover-admin/").status_code == 200

    ganhou, perdeu = _do_tipo("acesso.papel_de_admin_alterado")

    assert (ganhou.destinatario_id, perdeu.destinatario_id) == (diretor.id, diretor.id)
    assert (ganhou.pede_acao, perdeu.pede_acao) == (False, False)
    assert ganhou.titulo == perdeu.titulo == "Seu papel de administrador mudou"
    assert "agora é administrador" in ganhou.texto
    assert "deixou de ser administrador" in perdeu.texto
    assert (ganhou.item_tipo, ganhou.item_id, ganhou.caminho) == ("usuario", diretor.id, "/")
    assert ganhou.chave != perdeu.chave
    assert [m.to for m in mail.outbox] == [[diretor.email]] * 2


def test_ca22_ganhar_e_perder_uma_permissao_individual_notifica_com_o_nome_do_catalogo(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    concessao = _conceder(client_admin, diretor, CONVITES_GERENCIAR)
    assert client_admin.post(f"{PERMISSOES}concessoes/{concessao.json()['id']}/revogar/").status_code == 200

    ganhou, perdeu = _do_tipo("permissoes.concessao_individual_alterada")

    assert (ganhou.destinatario_id, perdeu.destinatario_id) == (diretor.id, diretor.id)
    assert (ganhou.pede_acao, perdeu.pede_acao) == (False, False)
    assert ganhou.titulo == "Suas permissões mudaram"
    assert "ganhou" in ganhou.texto
    assert "Gerenciar convites" in ganhou.texto
    assert "perdeu" in perdeu.texto
    assert "Gerenciar convites" in perdeu.texto
    assert CONVITES_GERENCIAR not in ganhou.texto
    assert (ganhou.item_tipo, ganhou.item_id, ganhou.caminho) == ("usuario", diretor.id, "/")


def test_ca22_o_acesso_total_notifica_pelo_nome(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    _conceder(client_admin, diretor, ACESSO_TOTAL)

    (n,) = _do_tipo("permissoes.concessao_individual_alterada")
    assert "Acesso total" in n.texto


def test_ca22_conceder_o_que_o_usuario_ja_tem_nao_notifica_de_novo(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    _conceder(client_admin, diretor, CONVITES_GERENCIAR)
    _conceder(client_admin, diretor, CONVITES_GERENCIAR)

    assert len(_do_tipo("permissoes.concessao_individual_alterada")) == 1


def test_ca22_permissao_dada_a_cargo_ou_setor_nao_gera_notificacao(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    cargo, setor = _cargo_e_setor(client_admin)
    for alvo_tipo, alvo in (("CARGO", cargo), ("SETOR", setor)):
        client_admin.post(
            f"{PERMISSOES}concessoes/",
            {"permissao": CONVITES_GERENCIAR, "alvo_tipo": alvo_tipo, "alvo_id": alvo["id"]},
            format="json",
        )

    assert Notificacao.objects.count() == 0


def test_o_informativo_respeita_a_preferencia_de_email_do_destinatario(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    preferencias.alterar(diretor.id, email_informativos=False)
    cargo, _ = _cargo_e_setor(client_admin)
    mail.outbox.clear()

    _classificar(client_admin, diretor, cargo)

    (n,) = _do_tipo("permissoes.classificacao_alterada")
    assert n.email_situacao == SituacaoDoEmail.DISPENSADO
    assert mail.outbox == []


def test_o_que_pede_acao_ignora_a_preferencia_de_email_do_admin(admin: Usuario) -> None:
    preferencias.alterar(admin.id, email_informativos=False)
    novo = criar_diretor("caio")
    mail.outbox.clear()

    events.publish(acesso.CadastroConcluido(usuario_id=novo.id))

    assert [m.to for m in mail.outbox] == [[admin.email]]


def test_usuario_inativo_nao_recebe_a_notificacao_do_evento(
    admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    client_admin.post(f"{ACESSO}usuarios/{diretor.id}/desativar/")
    mail.outbox.clear()

    events.publish(permissoes.ClassificacaoAlterada(usuario_id=diretor.id))

    assert Notificacao.objects.filter(destinatario_id=diretor.id).count() == 0
    assert mail.outbox == []


def test_evento_de_usuario_que_nao_existe_nao_quebra_a_operacao() -> None:
    fantasma = uuid.uuid4()

    events.publish(acesso.CadastroConcluido(usuario_id=fantasma))
    events.publish(acesso.PapelDeAdminAlterado(usuario_id=fantasma, admin=True))
    events.publish(permissoes.ClassificacaoAlterada(usuario_id=fantasma))
    events.publish(
        permissoes.ConcessaoIndividualAlterada(
            usuario_id=fantasma, permissao=CONVITES_GERENCIAR, concedida=True
        )
    )

    assert Notificacao.objects.count() == 0
