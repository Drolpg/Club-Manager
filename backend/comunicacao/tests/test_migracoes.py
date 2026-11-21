"""Dados iniciais de `comunicacao` (P15; CA-28), os catálogos e a reversão das migrações."""

from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

from comunicacao.models import CategoriaDeDocumento
from notificacoes import public as notificacoes
from permissoes import public as permissoes
from tests import apoio

INICIAIS = {"Institucional", "Financeiro", "Eventos", "Outros"}
SETORES = ["Financeiro", "Futebol", "Eventos", "Operacional"]
PERMISSOES = {
    "comunicacao.publicar",
    "comunicacao.gerenciar",
    "comunicacao.enviar_documentos",
    "comunicacao.registrar_atas",
}


def _no_setor(client_admin: APIClient, nome_do_setor: str, nome_de_usuario: str) -> Any:
    diretor = apoio.criar_diretor(nome_de_usuario)
    setores = client_admin.get("/api/v1/permissoes/setores/").json()
    cargos = client_admin.get("/api/v1/permissoes/cargos/").json()
    resposta = client_admin.put(
        f"/api/v1/permissoes/usuarios/{diretor.id}/classificacao/",
        {
            "cargo_id": cargos[0]["id"],
            "setor_ids": [next(s["id"] for s in setores if s["nome"] == nome_do_setor)],
        },
    )
    assert resposta.status_code == 200, resposta.content
    return diretor


@pytest.mark.django_db
def test_ca28_sistema_nasce_com_as_quatro_categorias_ativas() -> None:
    assert set(CategoriaDeDocumento.objects.filter(ativa=True).values_list("nome", flat=True)) == INICIAIS


@pytest.mark.django_db
@pytest.mark.parametrize("setor", SETORES)
def test_p15_publicar_e_enviar_documentos_nascem_com_os_quatro_setores(
    client_admin: APIClient, setor: str
) -> None:
    diretor = _no_setor(client_admin, setor, f"dir.{setor.lower()}")

    do_diretor = set(permissoes.permissoes_de(diretor.id))

    assert {"comunicacao.publicar", "comunicacao.enviar_documentos"} <= do_diretor
    assert "comunicacao.gerenciar" not in do_diretor
    assert "comunicacao.registrar_atas" not in do_diretor


@pytest.mark.django_db
def test_as_quatro_permissoes_estao_no_catalogo() -> None:
    for codigo in PERMISSOES:
        assert permissoes.nome_da_permissao(codigo)


@pytest.mark.django_db
def test_os_dois_tipos_de_notificacao_estao_declarados() -> None:
    destinatario = apoio.criar_diretor("quem.recebe")

    for tipo in ("comunicacao.comunicado_publicado", "comunicacao.comentario_novo"):
        criadas = notificacoes.notificar(
            tipo=tipo,
            destinatarios=[destinatario.id],
            titulo="Título",
            texto="Texto",
            item_tipo="comunicado",
            item_id=destinatario.id,
            caminho="/feed",
            chave=f"teste-{tipo}",
        )
        assert criadas == 1


@pytest.mark.django_db(transaction=True)
def test_migracoes_de_comunicacao_sao_reversiveis() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("comunicacao", "0001_modelos")])
    estado = executor.loader.project_state([("comunicacao", "0001_modelos")])
    assert estado.apps.get_model("comunicacao", "CategoriaDeDocumento").objects.count() == 0
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM permissoes_concessao WHERE permissao LIKE 'comunicacao.%%'")
        assert cursor.fetchone() == (0,)
        cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'comunicacao_%%'")
        assert cursor.fetchone() == (0,)

    try:
        call_command("migrate", "comunicacao", verbosity=0)
    finally:
        call_command("migrate", verbosity=0)
    assert set(CategoriaDeDocumento.objects.values_list("nome", flat=True)) == INICIAIS
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'comunicacao_%%'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] > 0
