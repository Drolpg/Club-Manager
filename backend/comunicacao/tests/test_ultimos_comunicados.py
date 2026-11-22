"""`comunicacao.public.ultimos_comunicados`, os do dashboard (H5; CA-09).

Só leitura: não confere quem pergunta (é do serviço de `relatorios`). Os comunicados passam pelos serviços do
próprio módulo, com o instante da publicação fixado.
"""

from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from comunicacao import public
from comunicacao.models import Comunicado
from comunicacao.services import comunicados
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db


def _publicado(autor: Usuario, titulo: str, *, ha_dias: int, tipo: str = "COMUNICADO") -> Comunicado:
    with mock.patch.object(timezone, "now", return_value=timezone.now() - timedelta(days=ha_dias)):
        return comunicados.publicar(autor.id, tipo=tipo, titulo=titulo, texto="Texto")


def test_publicados_do_mais_novo_para_o_mais_antigo_e_despublicado_fora(papeis: dict[str, Usuario]) -> None:
    autor, gerente = papeis["autor"], papeis["gerente"]
    antigo = _publicado(autor, "Antigo", ha_dias=5)
    pauta = _publicado(autor, "Pauta", ha_dias=1, tipo="PAUTA")
    despublicado = _publicado(autor, "Errado", ha_dias=0)
    comunicados.despublicar(gerente.id, despublicado.id, motivo="Erro")
    comunicados.fixar(gerente.id, antigo.id)

    ultimos = public.ultimos_comunicados()

    assert [c.id for c in ultimos] == [pauta.id, antigo.id]
    assert (ultimos[0].tipo, ultimos[0].titulo, ultimos[0].fixado) == ("PAUTA", "Pauta", False)
    assert ultimos[1].fixado is True
    assert ultimos[0].publicado_em == pauta.publicado_em


def test_limite_de_cinco_por_padrao(papeis: dict[str, Usuario]) -> None:
    for dia in range(7):
        _publicado(papeis["autor"], f"Aviso {dia}", ha_dias=dia)

    assert len(public.ultimos_comunicados()) == 5
    assert len(public.ultimos_comunicados(limite=2)) == 2
