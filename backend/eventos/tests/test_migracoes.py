"""Dados iniciais de `eventos` (P5, P6, P8; CA-01) e a reversão das migrações."""

from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

from eventos.models import CategoriaDeEvento
from permissoes import public as permissoes
from tests import apoio

INICIAIS = {"Jogo", "Reunião", "Festa", "Outros"}


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
def test_ca01_sistema_nasce_com_as_quatro_categorias_ativas() -> None:
    assert set(CategoriaDeEvento.objects.filter(ativa=True).values_list("nome", flat=True)) == INICIAIS


@pytest.mark.django_db
@pytest.mark.parametrize("setor", ["Financeiro", "Futebol", "Eventos", "Operacional"])
def test_p5_e_p6_concessoes_iniciais(client_admin: APIClient, setor: str) -> None:
    diretor = _no_setor(client_admin, setor, f"dir.{setor.lower()}")

    do_diretor = set(permissoes.permissoes_de(diretor.id))

    assert "eventos.propor" in do_diretor
    assert ("eventos.aprovar" in do_diretor) is (setor == "Eventos")
    assert "eventos.cancelar" not in do_diretor


@pytest.mark.django_db(transaction=True)
def test_migracoes_de_eventos_sao_reversiveis() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("eventos", "0001_categoria_evento_presenca")])
    estado = executor.loader.project_state([("eventos", "0001_categoria_evento_presenca")])
    assert estado.apps.get_model("eventos", "CategoriaDeEvento").objects.count() == 0
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM permissoes_concessao WHERE permissao LIKE 'eventos.%%'")
        assert cursor.fetchone() == (0,)

    try:
        call_command("migrate", "eventos", verbosity=0)
    finally:
        call_command("migrate", verbosity=0)
    assert set(CategoriaDeEvento.objects.values_list("nome", flat=True)) == INICIAIS
