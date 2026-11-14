"""Consultas: fila, lista, detalhe, histórico e tipos (CA-26 a CA-28, CA-33; adendo 1, A2 e A9)."""

import uuid
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from aprovacoes import public
from aprovacoes.models import MotivoDeDecisao
from aprovacoes.tests.conftest import (
    APROVAR_TESTE,
    AUTO_APROVAR,
    SOLICITACOES,
    TIPO,
    TipoDeTeste,
    com_cargo,
    enviada,
    levar_a,
    pedido,
    preparar_pedido,
)
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

BASE = "/api/v1/aprovacoes/"
FILA = f"{BASE}fila/"


def _erro(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def _get(usuario: Usuario | APIClient, url: str, **parametros: Any) -> Any:
    client = usuario if isinstance(usuario, APIClient) else apoio.cliente_de(usuario)
    resposta = client.get(url, parametros)
    assert resposta.status_code == 200, resposta.content
    return resposta.json()


def _ids(itens: list[dict[str, Any]]) -> list[str]:
    return [item["id"] for item in itens]


def _ha(dias: int) -> Any:
    return mock.patch("django.utils.timezone.now", return_value=timezone.now() - timedelta(days=dias))


@pytest.fixture
def solicitante(tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario) -> Usuario:
    return diretor_com_cargo


# --- CA-26: fila de pendências ---


def test_ca26_a_fila_traz_so_o_que_o_aprovador_pode_decidir_da_mais_antiga_para_a_mais_nova(
    solicitante: Usuario, aprovador: Usuario
) -> None:
    with _ha(5):
        antiga = enviada(solicitante)
    with _ha(3):
        do_meio = enviada(solicitante)
    nova = enviada(solicitante)
    levar_a(enviada(solicitante), "CONTESTADA")
    levar_a(enviada(solicitante), "APROVADA")
    propria = enviada(aprovador, indicado=com_cargo("indicado"))

    fila = _get(aprovador, FILA)

    assert _ids(fila) == [str(antiga.id), str(do_meio.id), str(nova.id)]
    assert str(propria.id) not in _ids(fila)
    assert set(fila[0]) >= {
        "id",
        "tipo",
        "tipo_nome",
        "situacao",
        "resumo",
        "valor",
        "solicitante",
        "aguardando_desde",
    }


def test_a9_a_fila_conta_a_espera_a_partir_da_versao_atual(solicitante: Usuario, aprovador: Usuario) -> None:
    with _ha(5):
        reenviada = enviada(solicitante)
        levar_a(reenviada, "CONTESTADA")
    with _ha(2):
        apoio.cliente_de(solicitante).post(
            f"{SOLICITACOES}{reenviada.id}/reenviar/", {"conteudo": pedido()}, format="json"
        )
    with _ha(4):
        esperando = enviada(solicitante)

    assert _ids(_get(aprovador, FILA)) == [str(esperando.id), str(reenviada.id)]


def test_ca26_o_indicado_ve_so_a_que_foi_indicado(aprovador: Usuario, solicitante: Usuario) -> None:
    indicado = com_cargo("indicado")
    indicada = enviada(aprovador, indicado=indicado)
    enviada(solicitante)

    assert _ids(_get(indicado, FILA)) == [str(indicada.id)]


def test_ca26_com_auto_aprovacao_a_propria_aparece(tipo_de_teste: TipoDeTeste) -> None:
    auto = com_cargo("auto", APROVAR_TESTE, AUTO_APROVAR)
    propria = enviada(auto)

    assert _ids(_get(auto, FILA)) == [str(propria.id)]


def test_ca26_o_admin_ve_todas_inclusive_as_proprias(solicitante: Usuario, admin: Usuario) -> None:
    de_outro = enviada(solicitante)
    propria = enviada(admin)

    assert set(_ids(_get(admin, FILA))) == {str(de_outro.id), str(propria.id)}


def test_ca26_a_retirada_sai_da_fila(solicitante: Usuario, aprovador: Usuario) -> None:
    levar_a(enviada(solicitante), "RETIRADA")

    assert _get(aprovador, FILA) == []


def test_ca26_quem_nao_aprova_o_tipo_tem_a_fila_vazia(solicitante: Usuario) -> None:
    enviada(solicitante)

    assert _get(com_cargo("leitor"), FILA) == []


def test_a2_a_fila_exige_leitura_de_gestao(tipo_de_teste: TipoDeTeste, client: APIClient) -> None:
    sem_cargo = apoio.criar_diretor("sem.cargo")
    apoio.conceder(sem_cargo, APROVAR_TESTE)

    assert _erro(apoio.cliente_de(sem_cargo).get(FILA)) == (403, "PERMISSION_DENIED")
    assert _erro(client.get(FILA)) == (401, "NOT_AUTHENTICATED")


# --- CA-27: lista ---


def test_ca27_quem_tem_cargo_ve_todas_da_mais_recente_para_a_mais_antiga(solicitante: Usuario) -> None:
    primeira = enviada(solicitante)
    segunda = enviada(com_cargo("outro"))
    terceira = levar_a(enviada(solicitante), "RECUSADA")

    pagina = _get(com_cargo("leitor"), f"{BASE}solicitacoes/")

    assert _ids(pagina["itens"]) == [str(terceira.id), str(segunda.id), str(primeira.id)]
    assert pagina["tem_mais"] is False
    item = pagina["itens"][2]
    assert item["resumo"] == "Bolas de treino"
    assert item["valor"] == "150.00"
    assert item["solicitante"] == {"id": str(solicitante.id), "nome": solicitante.nome}
    assert item["tipo_nome"] == "Pedido de teste"


def test_ca27_filtros_por_tipo_situacao_e_as_minhas(solicitante: Usuario) -> None:
    public.registrar_tipo(
        codigo="teste.outro",
        nome="Outro",
        permissao_de_aprovar=APROVAR_TESTE,
        tem_valor=True,
        preparar=preparar_pedido,
        ao_mudar=lambda mudanca: None,
    )
    try:
        minha = enviada(solicitante)
        de_outro_tipo = enviada(solicitante, "teste.outro")
        de_outra_pessoa = levar_a(enviada(com_cargo("outro")), "APROVADA")
        lista = f"{BASE}solicitacoes/"

        assert set(_ids(_get(solicitante, lista, tipo=TIPO)["itens"])) == {
            str(minha.id),
            str(de_outra_pessoa.id),
        }
        assert _ids(_get(solicitante, lista, situacao="APROVADA")["itens"]) == [str(de_outra_pessoa.id)]
        assert set(_ids(_get(solicitante, lista, minhas="1")["itens"])) == {
            str(minha.id),
            str(de_outro_tipo.id),
        }
        assert _ids(_get(solicitante, lista, minhas="1", tipo="teste.outro")["itens"]) == [
            str(de_outro_tipo.id)
        ]
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("teste.outro")


def test_ca27_a_lista_e_paginada(solicitante: Usuario) -> None:
    criadas = [enviada(solicitante) for _ in range(5)]
    lista = f"{BASE}solicitacoes/"

    primeira = _get(solicitante, lista, limite=2)
    segunda = _get(solicitante, lista, limite=2, antes=primeira["itens"][-1]["id"])
    ultima = _get(solicitante, lista, limite=2, antes=segunda["itens"][-1]["id"])

    assert primeira["tem_mais"]
    assert segunda["tem_mais"]
    assert not ultima["tem_mais"]
    vistas = _ids(primeira["itens"]) + _ids(segunda["itens"]) + _ids(ultima["itens"])
    assert vistas == [str(s.id) for s in reversed(criadas)]


@pytest.mark.parametrize(
    "parametros", [{"situacao": "INVENTADA"}, {"limite": "0"}, {"limite": "51"}, {"antes": str(uuid.uuid7())}]
)
def test_ca27_parametros_invalidos_da_lista(solicitante: Usuario, parametros: dict[str, str]) -> None:
    resposta = apoio.cliente_de(solicitante).get(f"{BASE}solicitacoes/", parametros)

    assert _erro(resposta) == (400, "VALIDATION_ERROR")


def test_ca27_diretor_sem_cargo_nao_ve_a_lista(tipo_de_teste: TipoDeTeste, client_diretor: APIClient) -> None:
    assert _erro(client_diretor.get(f"{BASE}solicitacoes/")) == (403, "PERMISSION_DENIED")


# --- CA-28: detalhe ---


def test_ca28_o_detalhe_mostra_versoes_decisoes_indicacao_e_acoes(aprovador: Usuario) -> None:
    indicado = com_cargo("indicado")
    solicitacao = enviada(aprovador, indicado=indicado)
    contestar = MotivoDeDecisao.objects.get(texto="Valor acima do necessário")
    apoio.cliente_de(indicado).post(
        f"{SOLICITACOES}{solicitacao.id}/contestar/",
        {
            "motivo_id": str(contestar.id),
            "mensagem": "Reduza.",
            "texto": "Veja o teto.",
            "teto_sugerido": "90",
        },
        format="json",
    )
    apoio.cliente_de(aprovador).post(
        f"{SOLICITACOES}{solicitacao.id}/reenviar/",
        {"conteudo": pedido("Bolas oficiais", "90")},
        format="json",
    )

    detalhe = _get(indicado, f"{SOLICITACOES}{solicitacao.id}/")

    assert detalhe["situacao"] == "EM_ANALISE"
    assert detalhe["tem_valor"] is True
    assert detalhe["solicitante"] == {"id": str(aprovador.id), "nome": aprovador.nome}
    assert detalhe["aprovador_indicado"] == {"id": str(indicado.id), "nome": indicado.nome}
    primeira, segunda = detalhe["versoes"]
    assert (primeira["numero"], primeira["conteudo"], primeira["valor"]) == (
        1,
        {"descricao": "Bolas de treino", "valor": "150.00"},
        "150.00",
    )
    assert primeira["autor"] == {"id": str(aprovador.id), "nome": aprovador.nome}
    assert primeira["decisao"] == {
        "tipo": "CONTESTAR",
        "aprovador": {"id": str(indicado.id), "nome": indicado.nome},
        "motivo_id": str(contestar.id),
        "motivo_texto": "Valor acima do necessário",
        "texto": "Veja o teto.",
        "mensagem": "Reduza.",
        "teto_sugerido": "90.00",
        "aprovacao_propria": False,
        "criada_em": primeira["decisao"]["criada_em"],
    }
    assert (segunda["numero"], segunda["resumo"], segunda["decisao"]) == (2, "Bolas oficiais", None)
    assert detalhe["acoes"] == ["aprovar", "contestar", "recusar"]


def test_ca28_e_ca33_o_historico_traz_todas_as_acoes_com_os_nomes(aprovador: Usuario) -> None:
    indicado = com_cargo("indicado")
    solicitacao = enviada(aprovador, indicado=indicado)
    levar_a(solicitacao, "CONTESTADA")
    apoio.cliente_de(aprovador).post(
        f"{SOLICITACOES}{solicitacao.id}/reenviar/", {"conteudo": pedido()}, format="json"
    )
    levar_a(solicitacao, "EM_EXECUCAO")
    public.encerrar(solicitacao.id)

    historico = _get(com_cargo("leitor"), f"{SOLICITACOES}{solicitacao.id}/historico/")

    assert [r["acao"] for r in reversed(historico)] == [
        "SOLICITACAO_ENVIADA",
        "APROVADOR_INDICADO",
        "SOLICITACAO_CONTESTADA",
        "SOLICITACAO_REENVIADA",
        "SOLICITACAO_APROVADA",
        "SOLICITACAO_EM_EXECUCAO",
        "SOLICITACAO_ENCERRADA",
    ]
    assert historico[-1]["ator"] == {"id": str(aprovador.id), "nome": aprovador.nome}
    assert historico[0]["ator"] is None


def test_ca28_detalhe_e_historico_exigem_leitura_e_respondem_404(
    solicitante: Usuario, client_diretor: APIClient, client_com_cargo: APIClient
) -> None:
    solicitacao = enviada(solicitante)
    for url in (f"{SOLICITACOES}{solicitacao.id}/", f"{SOLICITACOES}{solicitacao.id}/historico/"):
        assert _erro(client_diretor.get(url)) == (403, "PERMISSION_DENIED")
    for url in (f"{SOLICITACOES}{uuid.uuid7()}/", f"{SOLICITACOES}{uuid.uuid7()}/historico/"):
        assert _erro(client_com_cargo.get(url)) == (404, "NOT_FOUND")
        assert _erro(client_diretor.get(url)) == (403, "PERMISSION_DENIED")


# --- tipos ---


def test_quem_le_gestao_ve_os_tipos_registrados(
    tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient
) -> None:
    tipos = _get(client_com_cargo, f"{BASE}tipos/")

    assert {"codigo": TIPO, "nome": "Pedido de teste", "tem_valor": True} in tipos


def test_os_tipos_exigem_leitura_de_gestao(tipo_de_teste: TipoDeTeste, client_diretor: APIClient) -> None:
    assert _erro(client_diretor.get(f"{BASE}tipos/")) == (403, "PERMISSION_DENIED")


# --- paridade entre `acoes` e as rotas, por papel e por situação ---

SITUACOES = (
    "EM_ANALISE",
    "RETIRADA",
    "CONTESTADA",
    "RECUSADA",
    "APROVADA",
    "EM_EXECUCAO",
    "ENCERRADA",
    "CANCELADA",
)
PAPEIS = ("solicitante", "indicado", "aprovador", "admin", "leitor", "reabre_e_cancela")
COMANDOS = ("retirar", "reenviar", "reabrir", "editar", "cancelar", "aprovar", "contestar", "recusar")


def _corpo(comando: str) -> dict[str, Any]:
    motivo = {
        "aprovar": "Dentro do orçamento",
        "contestar": "Falta justificativa",
        "recusar": "Pedido duplicado",
    }
    corpos: dict[str, dict[str, Any]] = {
        "retirar": {},
        "reenviar": {"conteudo": pedido()},
        "reabrir": {"justificativa": "Revisto"},
        "editar": {"conteudo": pedido()},
        "cancelar": {"motivo": "Não precisa"},
        "contestar": {"mensagem": "Ajuste"},
    }
    corpo = corpos.get(comando, {})
    if comando in motivo:
        corpo = {**corpo, "motivo_id": str(MotivoDeDecisao.objects.get(texto=motivo[comando]).id)}
    return corpo


@pytest.mark.parametrize("situacao", SITUACOES)
@pytest.mark.parametrize("papel", PAPEIS)
def test_acoes_do_detalhe_coincidem_com_o_que_as_rotas_aceitam(
    tipo_de_teste: TipoDeTeste, admin: Usuario, papel: str, situacao: str
) -> None:
    from tests.apoio import conceder

    # Quem envia aprovaria o próprio pedido: precisa indicar, e assim o papel "indicado" existe.
    solicitante = com_cargo("solicitante", APROVAR_TESTE)
    indicado = com_cargo("indicado")
    usuarios = {
        "solicitante": solicitante,
        "indicado": indicado,
        "aprovador": com_cargo("aprovador", APROVAR_TESTE),
        "admin": admin,
        "leitor": com_cargo("leitor"),
        "reabre_e_cancela": com_cargo("reabre", "solicitacoes.reabrir"),
    }
    conceder(usuarios["reabre_e_cancela"], "solicitacoes.cancelar")
    client = apoio.cliente_de(usuarios[papel])

    def nova() -> Any:
        return levar_a(enviada(solicitante, indicado=indicado), situacao)

    solicitacao = nova()
    acoes = _get(client, f"{SOLICITACOES}{solicitacao.id}/")["acoes"]

    for comando in COMANDOS:
        alvo = nova() if comando in acoes else solicitacao
        resposta = client.post(f"{SOLICITACOES}{alvo.id}/{comando}/", _corpo(comando), format="json")
        if comando in acoes:
            assert resposta.status_code == 200, (papel, situacao, comando, resposta.content)
        else:
            assert resposta.status_code in (403, 422), (papel, situacao, comando, resposta.content)
    assert set(acoes) <= set(COMANDOS)
