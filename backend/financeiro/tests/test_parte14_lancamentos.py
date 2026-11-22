"""Parte 14: a lista de lançamentos da aba Financeiro (RF-104; CA-14 a CA-18, CA-21).

Quatro tipos numa lista só (cobrança, entrada, saída e estorno), com filtros por período, categoria, tipo e
estado, e paginação por cursor `<tipo>:<uuid>`.
"""

import json
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from financeiro.domain.realizado import EstadoDoLancamento, TipoDeLancamento
from financeiro.services import lancamentos
from financeiro.tests.apoio_lancamentos import Livro
from financeiro.tests.conftest import client, novo_diretor
from kernel.errors import BusinessError

pytestmark = pytest.mark.django_db

ROTA = "/api/v1/financeiro/lancamentos/"
_CAMPOS = {
    "tipo",
    "subtipo",
    "id",
    "data_referencia",
    "descricao",
    "categoria",
    "contraparte",
    "valor",
    "valor_realizado",
    "estado",
    "situacao",
    "realizado_em",
    "original",
}


@pytest.fixture
def livro(db: None) -> Livro:
    return Livro()


def _cenario(livro: Livro) -> dict[str, Any]:
    aberta = livro.cobranca("10.00", descricao="Mensalidade aberta")
    paga = livro.cobranca_paga("100.00")
    entrada = livro.entrada_validada("1000.00")
    saida = livro.saida("300.00")
    livro.enviar(saida, "200.00")
    livro.prestar(saida, "150.00")
    devolucao = livro.devolver(saida, "50.00")
    saida = livro.liquidar(saida)
    livro.estornar_cobranca(paga)
    return {"aberta": aberta, "paga": paga, "entrada": entrada, "saida": saida, "devolucao": devolucao}


def _todos(ator_id: uuid.UUID, **filtros: Any) -> list[lancamentos.Lancamento]:
    return lancamentos.listar(ator_id, limite=50, **filtros).itens


def _por_id(itens: list[lancamentos.Lancamento]) -> dict[uuid.UUID, lancamentos.Lancamento]:
    return {i.id: i for i in itens}


def test_ca14_os_quatro_tipos_com_os_campos_e_em_ordem(livro: Livro) -> None:
    c = _cenario(livro)

    itens = _todos(livro.fin.id)

    assert {i.tipo for i in itens} == {"COBRANCA", "ENTRADA", "SAIDA", "ESTORNO"}
    chaves = [(i.data_referencia, i.id) for i in itens]
    assert chaves == sorted(chaves, reverse=True)
    por_id = _por_id(itens)
    aberta = por_id[c["aberta"].id]
    assert (aberta.descricao, aberta.valor, aberta.estado) == (
        "Mensalidade aberta",
        Decimal("10.00"),
        "EM_ABERTO",
    )
    assert aberta.contraparte == livro.devedor.nome
    assert aberta.data_referencia == c["aberta"].vencimento
    assert aberta.realizado_em is None
    paga = por_id[c["paga"].id]
    assert (paga.estado, paga.situacao) == ("ESTORNADO", "ESTORNADA")
    assert paga.realizado_em == timezone.localdate()
    entrada = por_id[c["entrada"].id]
    assert (entrada.subtipo, entrada.estado, entrada.contraparte) == (
        "SEM_DEVEDOR",
        "REALIZADO",
        "Patrocinador",
    )
    saida = por_id[c["saida"].id]
    assert (saida.valor, saida.valor_realizado, saida.estado) == (
        Decimal("300.00"),
        Decimal("150.00"),
        "REALIZADO",
    )
    assert saida.contraparte == f"{livro.solicitante.nome} — {livro.setor.nome}"


def test_ca16_devolucao_aponta_para_a_saida_e_estorno_para_o_original(livro: Livro) -> None:
    c = _cenario(livro)

    itens = _todos(livro.fin.id)

    devolucao = _por_id(itens)[c["devolucao"].id]
    assert (devolucao.subtipo, devolucao.original_tipo, devolucao.original_id) == (
        "DEVOLUCAO",
        "SAIDA",
        c["saida"].id,
    )
    (estorno,) = [i for i in itens if i.tipo == "ESTORNO"]
    assert estorno.valor == Decimal("-100.00")
    assert (estorno.original_tipo, estorno.original_id) == ("COBRANCA", c["paga"].id)
    assert estorno.categoria_id == c["paga"].categoria_id
    assert estorno.descricao == "Estorno de: Mensalidade"
    assert (estorno.estado, estorno.contraparte) == ("REALIZADO", livro.devedor.nome)


def test_ca15_filtro_por_tipo(livro: Livro) -> None:
    _cenario(livro)

    assert {i.tipo for i in _todos(livro.fin.id, tipo=TipoDeLancamento.ENTRADA)} == {"ENTRADA"}
    assert {i.subtipo for i in _todos(livro.fin.id, tipo=TipoDeLancamento.ENTRADA)} == {
        "SEM_DEVEDOR",
        "DEVOLUCAO",
    }
    assert len(_todos(livro.fin.id, tipo=TipoDeLancamento.ESTORNO)) == 1


def test_ca15_filtro_por_estado(livro: Livro) -> None:
    c = _cenario(livro)

    realizados = _todos(livro.fin.id, estado=EstadoDoLancamento.REALIZADO)

    assert {i.id for i in realizados if i.tipo != "ESTORNO"} == {
        c["entrada"].id,
        c["saida"].id,
        c["devolucao"].id,
    }
    assert {i.tipo for i in realizados} >= {"ESTORNO"}
    em_aberto = _todos(livro.fin.id, estado=EstadoDoLancamento.EM_ABERTO)
    assert [i.id for i in em_aberto] == [c["aberta"].id]
    assert _todos(livro.fin.id, estado=EstadoDoLancamento.EM_ABERTO, tipo=TipoDeLancamento.ESTORNO) == []


def test_ca15_filtro_por_categoria_inclusive_desativada(livro: Livro) -> None:
    c = _cenario(livro)
    livro.cat_mensalidade.desativar()

    da_mensalidade = _todos(livro.fin.id, categoria_id=livro.cat_mensalidade.id)

    assert {i.id for i in da_mensalidade if i.tipo == "COBRANCA"} == {c["aberta"].id, c["paga"].id}
    assert {i.tipo for i in da_mensalidade} == {"COBRANCA", "ESTORNO"}


def test_ca15_filtro_por_periodo_sobre_a_data_de_referencia(livro: Livro) -> None:
    hoje = timezone.localdate()
    perto = livro.cobranca("10.00", vencimento=hoje + timedelta(days=2))
    livro.cobranca("20.00", vencimento=hoje + timedelta(days=40))

    itens = _todos(livro.fin.id, de=hoje + timedelta(days=1), ate=hoje + timedelta(days=5))

    assert [i.id for i in itens] == [perto.id]


def test_paginacao_por_cursor_percorre_tudo_sem_repetir(livro: Livro) -> None:
    _cenario(livro)
    esperado = [i.id for i in _todos(livro.fin.id)]

    vistos: list[uuid.UUID] = []
    antes: str | None = None
    while True:
        pagina = lancamentos.listar(livro.fin.id, antes=antes, limite=2)
        vistos += [i.id for i in pagina.itens]
        if not pagina.tem_mais:
            break
        ultimo = pagina.itens[-1]
        antes = f"{ultimo.tipo}:{ultimo.id}"

    assert vistos == esperado


@pytest.mark.parametrize("antes", ["COBRANCA:" + str(uuid.uuid4()), "SAIDA:nao-e-uuid", "ilegivel", "X:1"])
def test_cursor_inexistente_ou_ilegivel_e_not_found(livro: Livro, antes: str) -> None:
    with pytest.raises(BusinessError) as excecao:
        lancamentos.listar(livro.fin.id, antes=antes)

    assert excecao.value.code == "NOT_FOUND"


def test_ca17_diretor_sem_cargo_e_negado_no_servico() -> None:
    sem_cargo = novo_diretor("semcargo_l")

    with pytest.raises(BusinessError) as excecao:
        lancamentos.listar(sem_cargo.id)

    assert excecao.value.code == "PERMISSION_DENIED"


# --- HTTP ------------------------------------------------------------------------------------------------


def test_ca14_e_ca21_rota_com_os_campos_declarados_e_valores_em_texto(livro: Livro) -> None:
    c = _cenario(livro)

    corpo = client(livro.fin).get(ROTA, {"limite": 50}).json()

    assert set(corpo) == {"itens", "tem_mais"}
    for item in corpo["itens"]:
        assert set(item) == _CAMPOS
    saida = next(i for i in corpo["itens"] if i["id"] == str(c["saida"].id))
    assert (saida["valor"], saida["valor_realizado"]) == ("300.00", "150.00")
    assert saida["categoria"] == {"id": str(livro.cat_saida.id), "nome": livro.cat_saida.nome}
    estorno = next(i for i in corpo["itens"] if i["tipo"] == "ESTORNO")
    assert estorno["valor"] == "-100.00"
    assert estorno["original"] == {"tipo": "COBRANCA", "id": str(c["paga"].id)}


def test_ca15_filtros_pela_rota(livro: Livro) -> None:
    _cenario(livro)

    corpo = client(livro.fin).get(ROTA, {"tipo": "ESTORNO", "estado": "REALIZADO"}).json()

    assert [i["tipo"] for i in corpo["itens"]] == ["ESTORNO"]


@pytest.mark.parametrize(
    ("parametros", "campo"),
    [
        ({"limite": 0}, "limite"),
        ({"limite": 51}, "limite"),
        ({"tipo": "PIX"}, "tipo"),
        ({"estado": "PAGO"}, "estado"),
        ({"de": "2026-11-10", "ate": "2026-11-01"}, "ate"),
        ({"de": "ontem"}, "de"),
        ({"categoria_id": "abc"}, "categoria_id"),
    ],
)
def test_entrada_invalida_e_400_no_campo(livro: Livro, parametros: dict[str, Any], campo: str) -> None:
    resposta = client(livro.fin).get(ROTA, parametros)

    assert resposta.status_code == 400
    assert campo in resposta.json()["error"]["details"]


def test_cursor_inexistente_pela_rota_e_404(livro: Livro) -> None:
    resposta = client(livro.fin).get(ROTA, {"antes": f"SAIDA:{uuid.uuid4()}"})

    assert resposta.status_code == 404


def test_ca17_sem_cargo_e_403_e_sem_sessao_e_401(livro: Livro) -> None:
    _cenario(livro)
    sem_cargo = novo_diretor("semcargo_h")

    assert client(sem_cargo).get(ROTA).status_code == 403
    assert client(sem_cargo).get(ROTA, {"antes": "lixo", "limite": "0"}).status_code == 403
    assert APIClient().get(ROTA).status_code == 401


def test_ca18_sem_comprovante_email_nem_telefone(livro: Livro) -> None:
    _cenario(livro)

    texto = json.dumps(client(livro.fin).get(ROTA, {"limite": 50}).json())

    for proibido in ("comprovante", "email", "telefone", livro.devedor.email):
        assert proibido not in texto
