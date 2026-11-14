"""Retirar, reenviar, reabrir, editar e cancelar (CA-09 a CA-17; INV-SOL-05, 06, 08, 09, 12 e 13; A4).

As decisões entram no checkpoint 4: aqui, as situações que dependem delas (contestada, recusada, aprovada, em
execução) são postas direto no banco, só para preparar o cenário.
"""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.test import APIClient

from aprovacoes import public
from aprovacoes.models import Solicitacao
from aprovacoes.tests.conftest import (
    APROVAR_TESTE,
    CANCELAR,
    REABRIR,
    SOLICITACOES,
    TIPO,
    TipoDeTeste,
    com_cargo,
    pedido,
    preparar_pedido,
)
from auditoria import public as auditoria
from kernel.dinheiro import Dinheiro
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

Acontecimento = public.Acontecimento


def _erro(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def _enviada(solicitante: Usuario, tipo: str = TIPO) -> Solicitacao:
    return Solicitacao.objects.get(
        pk=public.enviar(tipo=tipo, conteudo=pedido(), solicitante_id=solicitante.id)
    )


def _na_situacao(solicitacao: Solicitacao, situacao: str) -> Solicitacao:
    # Só prepara o cenário: no sistema, a situação muda pelos métodos do aggregate.
    Solicitacao.objects.filter(pk=solicitacao.pk).update(situacao=situacao)
    solicitacao.refresh_from_db()
    return solicitacao


def _acao(client: APIClient, solicitacao: Solicitacao, acao: str, **corpo: Any) -> Any:
    return client.post(f"{SOLICITACOES}{solicitacao.id}/{acao}/", corpo, format="json")


def _versoes(solicitacao: Solicitacao) -> list[tuple[int, str, uuid.UUID, str]]:
    return [(v.numero, v.resumo, v.autor_id, v.justificativa) for v in solicitacao.versoes.order_by("numero")]


def _acoes_auditadas(solicitacao: Solicitacao) -> list[str]:
    return [r.acao for r in auditoria.historico_do_item("solicitacao", solicitacao.id)]


@pytest.fixture
def solicitante(tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario) -> Usuario:
    return diretor_com_cargo


@pytest.fixture
def client_solicitante(solicitante: Usuario) -> APIClient:
    return apoio.cliente_de(solicitante)


# --- retirar (CA-12, CA-13; INV-SOL-12) ---


def test_ca12_o_solicitante_retira_a_solicitacao_em_analise(
    solicitante: Usuario, client_solicitante: APIClient, tipo_de_teste: TipoDeTeste
) -> None:
    solicitacao = _enviada(solicitante)

    resposta = _acao(client_solicitante, solicitacao, "retirar")

    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["situacao"] == "RETIRADA"
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "RETIRADA"
    (mudanca,) = tipo_de_teste.recebidas
    assert (mudanca.acontecimento, mudanca.versao, mudanca.ator_id) == (
        Acontecimento.RETIRADA,
        1,
        solicitante.id,
    )


def test_inv_sol_12_a_retirada_nao_cria_versao(solicitante: Usuario, client_solicitante: APIClient) -> None:
    solicitacao = _enviada(solicitante)

    _acao(client_solicitante, solicitacao, "retirar")

    assert solicitacao.versoes.count() == 1
    solicitacao.refresh_from_db()
    assert solicitacao.numero_da_versao_atual == 1


def test_ca12_a_retirada_volta_por_reenvio_como_versao_nova(
    solicitante: Usuario, client_solicitante: APIClient
) -> None:
    solicitacao = _enviada(solicitante)
    _acao(client_solicitante, solicitacao, "retirar")

    resposta = _acao(client_solicitante, solicitacao, "reenviar", conteudo=pedido("Bolas oficiais", "180"))

    assert resposta.status_code == 200, resposta.content
    assert (resposta.json()["situacao"], resposta.json()["numero_da_versao_atual"]) == ("EM_ANALISE", 2)


def test_inv_sol_12_so_se_retira_em_analise(solicitante: Usuario, client_solicitante: APIClient) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "CONTESTADA")

    assert _erro(_acao(client_solicitante, solicitacao, "retirar")) == (422, "NAO_ESTA_EM_ANALISE")


def test_ca13_ninguem_alem_do_solicitante_retira(solicitante: Usuario, client_admin: APIClient) -> None:
    solicitacao = _enviada(solicitante)
    aprovador = apoio.cliente_de(com_cargo("dora", APROVAR_TESTE, CANCELAR))

    assert _erro(_acao(aprovador, solicitacao, "retirar")) == (403, "SO_O_SOLICITANTE")
    assert _erro(_acao(client_admin, solicitacao, "retirar")) == (403, "SO_O_SOLICITANTE")
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_ANALISE"


# --- reenviar (CA-09; INV-SOL-05, INV-SOL-13) ---


def test_ca09_a_contestada_reenviada_vira_a_versao_seguinte_e_a_anterior_continua(
    solicitante: Usuario, client_solicitante: APIClient, tipo_de_teste: TipoDeTeste
) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "CONTESTADA")

    resposta = _acao(client_solicitante, solicitacao, "reenviar", conteudo=pedido("Bolas oficiais", "120"))

    assert resposta.status_code == 200, resposta.content
    solicitacao.refresh_from_db()
    assert (solicitacao.situacao, solicitacao.numero_da_versao_atual) == ("EM_ANALISE", 2)
    assert _versoes(solicitacao) == [
        (1, "Bolas de treino", solicitante.id, ""),
        (2, "Bolas oficiais", solicitante.id, ""),
    ]
    assert solicitacao.versoes.get(numero=2).valor == Decimal("120.00")
    # O reenvio não está na lista de avisos ao módulo dono (technical-spec, `ao_mudar`).
    assert tipo_de_teste.recebidas == []


def test_inv_sol_13_so_se_reenvia_contestada_ou_retirada(
    solicitante: Usuario, client_solicitante: APIClient
) -> None:
    for situacao in ("EM_ANALISE", "RECUSADA", "APROVADA", "CANCELADA"):
        solicitacao = _na_situacao(_enviada(solicitante), situacao)

        resposta = _acao(client_solicitante, solicitacao, "reenviar", conteudo=pedido())

        assert _erro(resposta) == (422, "NAO_ESTA_CONTESTADA_NEM_RETIRADA"), situacao


def test_reenvio_com_conteudo_recusado_pelo_dono_nao_muda_nada(
    solicitante: Usuario, client_solicitante: APIClient
) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "CONTESTADA")

    resposta = _acao(client_solicitante, solicitacao, "reenviar", conteudo={"descricao": ""})

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    solicitacao.refresh_from_db()
    assert (solicitacao.situacao, solicitacao.versoes.count()) == ("CONTESTADA", 1)


def test_so_o_solicitante_reenvia(solicitante: Usuario, client_admin: APIClient) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "CONTESTADA")

    assert _erro(_acao(client_admin, solicitacao, "reenviar", conteudo=pedido())) == (403, "SO_O_SOLICITANTE")


def test_reenviar_sem_conteudo_e_recusado(solicitante: Usuario, client_solicitante: APIClient) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "CONTESTADA")

    assert _erro(_acao(client_solicitante, solicitacao, "reenviar")) == (400, "VALIDATION_ERROR")


# --- reabrir (CA-10, CA-11; adendo 1, A4) ---


def test_ca10_a_recusada_reaberta_com_justificativa_vira_versao_nova_por_varias_rodadas(
    solicitante: Usuario, client_solicitante: APIClient, tipo_de_teste: TipoDeTeste
) -> None:
    solicitacao = _enviada(solicitante)

    for rodada in (2, 3, 4):
        _na_situacao(solicitacao, "RECUSADA")
        resposta = _acao(
            client_solicitante,
            solicitacao,
            "reabrir",
            justificativa=f"Rodada {rodada}",
            conteudo=pedido(f"Pedido {rodada}"),
        )
        assert resposta.status_code == 200, resposta.content
        assert (resposta.json()["situacao"], resposta.json()["numero_da_versao_atual"]) == (
            "EM_ANALISE",
            rodada,
        )

    assert [v[0] for v in _versoes(solicitacao)] == [1, 2, 3, 4]
    assert solicitacao.versoes.get(numero=4).justificativa == "Rodada 4"
    assert [m.acontecimento for m in tipo_de_teste.recebidas] == [Acontecimento.REABERTA] * 3
    assert [m.versao for m in tipo_de_teste.recebidas] == [2, 3, 4]


@pytest.mark.parametrize("justificativa", [None, "", "   "])
def test_ca10_reabrir_sem_justificativa_e_recusado(
    solicitante: Usuario, client_solicitante: APIClient, justificativa: str | None
) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "RECUSADA")
    corpo = {} if justificativa is None else {"justificativa": justificativa}

    assert _erro(_acao(client_solicitante, solicitacao, "reabrir", **corpo)) == (400, "VALIDATION_ERROR")
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "RECUSADA"


def test_so_se_reabre_recusada(solicitante: Usuario, client_solicitante: APIClient) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "CONTESTADA")

    resposta = _acao(client_solicitante, solicitacao, "reabrir", justificativa="Mudou o cenário")

    assert _erro(resposta) == (422, "NAO_ESTA_RECUSADA")


def test_ca11_so_o_admin_ou_quem_tem_a_permissao_reabre_a_de_outra_pessoa(
    solicitante: Usuario, client_admin: APIClient
) -> None:
    sem_permissao = apoio.cliente_de(com_cargo("sem", APROVAR_TESTE))
    com_permissao = apoio.cliente_de(com_cargo("com", REABRIR))
    primeira = _na_situacao(_enviada(solicitante), "RECUSADA")
    segunda = _na_situacao(_enviada(solicitante), "RECUSADA")

    assert _erro(_acao(sem_permissao, primeira, "reabrir", justificativa="Quero")) == (
        403,
        "PERMISSION_DENIED",
    )
    assert _acao(client_admin, primeira, "reabrir", justificativa="Revisto").status_code == 200
    assert _acao(com_permissao, segunda, "reabrir", justificativa="Revisto").status_code == 200


def test_a4_reabrir_sem_conteudo_copia_a_anterior_valida_em_nome_do_solicitante_e_o_autor_e_quem_reabriu(
    solicitante: Usuario, client_admin: APIClient, admin: Usuario
) -> None:
    chamadas: list[tuple[dict[str, Any], uuid.UUID]] = []

    def preparar(conteudo: dict[str, Any], solicitante_id: uuid.UUID) -> public.ConteudoPreparado:
        chamadas.append((conteudo, solicitante_id))
        return preparar_pedido(conteudo, solicitante_id)

    public.registrar_tipo(
        codigo="teste.registrado",
        nome="Registrado",
        permissao_de_aprovar=APROVAR_TESTE,
        tem_valor=True,
        preparar=preparar,
        ao_mudar=lambda mudanca: None,
    )
    try:
        solicitacao = _na_situacao(_enviada(solicitante, "teste.registrado"), "RECUSADA")
        chamadas.clear()

        resposta = _acao(client_admin, solicitacao, "reabrir", justificativa="Revisto em reunião")
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("teste.registrado")

    assert resposta.status_code == 200, resposta.content
    assert chamadas == [({"descricao": "Bolas de treino", "valor": "150.00"}, solicitante.id)]
    assert _versoes(solicitacao)[1] == (2, "Bolas de treino", admin.id, "Revisto em reunião")


# --- editar (CA-14, CA-15; INV-SOL-06, INV-SOL-09) ---


def test_ca14_a_aprovada_editada_vira_versao_nova_em_analise_e_o_dono_e_avisado(
    solicitante: Usuario, client_solicitante: APIClient, tipo_de_teste: TipoDeTeste
) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "APROVADA")

    resposta = _acao(
        client_solicitante,
        solicitacao,
        "editar",
        conteudo=pedido("Bolas e coletes", "200"),
        justificativa="Faltou",
    )

    assert resposta.status_code == 200, resposta.content
    solicitacao.refresh_from_db()
    assert (solicitacao.situacao, solicitacao.numero_da_versao_atual) == ("EM_ANALISE", 2)
    assert _versoes(solicitacao)[1] == (2, "Bolas e coletes", solicitante.id, "Faltou")
    (mudanca,) = tipo_de_teste.recebidas
    assert mudanca == public.MudancaDeSolicitacao(
        solicitacao_id=solicitacao.id,
        tipo=TIPO,
        acontecimento=Acontecimento.EDITADA,
        versao=2,
        valor=Dinheiro("200.00"),
        ator_id=solicitante.id,
        teto_sugerido=None,
    )


def test_inv_sol_06_a_versao_nova_da_editada_nao_tem_decisao(
    solicitante: Usuario, client_solicitante: APIClient
) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "APROVADA")

    _acao(client_solicitante, solicitacao, "editar", conteudo=pedido())

    assert not hasattr(solicitacao.versoes.get(numero=2), "decisao")


def test_editar_so_aprovada(solicitante: Usuario, client_solicitante: APIClient) -> None:
    for situacao in ("EM_ANALISE", "CONTESTADA", "RETIRADA", "RECUSADA"):
        solicitacao = _na_situacao(_enviada(solicitante), situacao)

        resposta = _acao(client_solicitante, solicitacao, "editar", conteudo=pedido())

        assert _erro(resposta) == (422, "NAO_PODE_EDITAR"), situacao


def test_so_o_solicitante_edita(solicitante: Usuario, client_admin: APIClient) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "APROVADA")

    assert _erro(_acao(client_admin, solicitacao, "editar", conteudo=pedido())) == (403, "SO_O_SOLICITANTE")


@pytest.mark.parametrize(
    ("acao", "corpo", "codigo"),
    [
        ("editar", {"conteudo": pedido()}, "NAO_PODE_EDITAR"),
        ("retirar", {}, "NAO_ESTA_EM_ANALISE"),
        ("cancelar", {"motivo": "Desisti"}, "NAO_PODE_CANCELAR"),
    ],
)
def test_ca15_em_execucao_nao_edita_nao_retira_nem_cancela(
    solicitante: Usuario, client_solicitante: APIClient, acao: str, corpo: dict[str, Any], codigo: str
) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), "EM_EXECUCAO")

    assert _erro(_acao(client_solicitante, solicitacao, acao, **corpo)) == (422, codigo)
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_EXECUCAO"


# --- cancelar (CA-16, CA-17; INV-SOL-08) ---


@pytest.mark.parametrize("situacao", ["EM_ANALISE", "CONTESTADA", "RETIRADA", "RECUSADA", "APROVADA"])
def test_ca16_o_solicitante_cancela_com_motivo(
    solicitante: Usuario, client_solicitante: APIClient, tipo_de_teste: TipoDeTeste, situacao: str
) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), situacao)

    resposta = _acao(client_solicitante, solicitacao, "cancelar", motivo="Não vamos mais comprar")

    assert resposta.status_code == 200, resposta.content
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "CANCELADA"
    (mudanca,) = tipo_de_teste.recebidas
    assert mudanca.acontecimento == Acontecimento.CANCELADA
    (registro,) = [
        r for r in auditoria.historico_do_item("solicitacao", solicitacao.id) if "CANCELADA" in r.acao
    ]
    assert registro.justificativa == "Não vamos mais comprar"


@pytest.mark.parametrize("motivo", [None, "", "  "])
def test_ca16_cancelar_sem_motivo_e_recusado(
    solicitante: Usuario, client_solicitante: APIClient, motivo: str | None
) -> None:
    solicitacao = _enviada(solicitante)
    corpo = {} if motivo is None else {"motivo": motivo}

    assert _erro(_acao(client_solicitante, solicitacao, "cancelar", **corpo)) == (400, "VALIDATION_ERROR")


@pytest.mark.parametrize(
    ("acao", "corpo", "codigo"),
    [
        ("retirar", {}, "NAO_ESTA_EM_ANALISE"),
        ("reenviar", {"conteudo": pedido()}, "NAO_ESTA_CONTESTADA_NEM_RETIRADA"),
        ("reabrir", {"justificativa": "Volta"}, "NAO_ESTA_RECUSADA"),
        ("editar", {"conteudo": pedido()}, "NAO_PODE_EDITAR"),
        ("cancelar", {"motivo": "De novo"}, "NAO_PODE_CANCELAR"),
    ],
)
@pytest.mark.parametrize("final", ["CANCELADA", "ENCERRADA"])
def test_ca16_inv_sol_08_cancelada_e_encerrada_nao_aceitam_mais_nada(
    solicitante: Usuario,
    client_solicitante: APIClient,
    final: str,
    acao: str,
    corpo: dict[str, Any],
    codigo: str,
) -> None:
    solicitacao = _na_situacao(_enviada(solicitante), final)

    assert _erro(_acao(client_solicitante, solicitacao, acao, **corpo)) == (422, codigo)


def test_ca17_so_o_admin_ou_quem_tem_a_permissao_cancela_a_de_outra_pessoa(
    solicitante: Usuario, client_admin: APIClient
) -> None:
    sem_permissao = apoio.cliente_de(com_cargo("sem", APROVAR_TESTE, REABRIR))
    com_permissao = apoio.cliente_de(com_cargo("com", CANCELAR))
    primeira = _enviada(solicitante)
    segunda = _enviada(solicitante)

    assert _erro(_acao(sem_permissao, primeira, "cancelar", motivo="X")) == (403, "PERMISSION_DENIED")
    assert _acao(client_admin, primeira, "cancelar", motivo="Duplicada").status_code == 200
    assert _acao(com_permissao, segunda, "cancelar", motivo="Duplicada").status_code == 200


# --- transversais ---


def test_ca33_cada_acao_do_solicitante_gera_registro_de_auditoria(
    solicitante: Usuario, client_solicitante: APIClient
) -> None:
    solicitacao = _enviada(solicitante)
    _acao(client_solicitante, solicitacao, "retirar")
    _acao(client_solicitante, solicitacao, "reenviar", conteudo=pedido())
    _na_situacao(solicitacao, "RECUSADA")
    _acao(client_solicitante, solicitacao, "reabrir", justificativa="Revisto")
    _na_situacao(solicitacao, "APROVADA")
    _acao(client_solicitante, solicitacao, "editar", conteudo=pedido())
    _acao(client_solicitante, solicitacao, "cancelar", motivo="Desisti")

    assert _acoes_auditadas(solicitacao) == [
        "SOLICITACAO_ENVIADA",
        "SOLICITACAO_RETIRADA",
        "SOLICITACAO_REENVIADA",
        "SOLICITACAO_REABERTA",
        "SOLICITACAO_EDITADA",
        "SOLICITACAO_CANCELADA",
    ]
    reaberta = auditoria.historico_do_item("solicitacao", solicitacao.id)[3]
    assert (reaberta.justificativa, reaberta.dados) == ("Revisto", {"versao": 3})


def test_o_erro_no_aviso_ao_modulo_dono_desfaz_a_acao(
    solicitante: Usuario, client_solicitante: APIClient
) -> None:
    def falha(mudanca: public.MudancaDeSolicitacao) -> None:
        raise RuntimeError("o módulo dono falhou")

    public.registrar_tipo(
        codigo="teste.falho",
        nome="Falho",
        permissao_de_aprovar=APROVAR_TESTE,
        tem_valor=True,
        preparar=preparar_pedido,
        ao_mudar=falha,
    )
    try:
        solicitacao = _enviada(solicitante, "teste.falho")
        resposta = _acao(client_solicitante, solicitacao, "retirar")
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("teste.falho")

    assert _erro(resposta) == (500, "INTERNAL_ERROR")
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_ANALISE"
    assert _acoes_auditadas(solicitacao) == ["SOLICITACAO_ENVIADA"]


def test_solicitacao_inexistente(client_com_cargo: APIClient, tipo_de_teste: TipoDeTeste) -> None:
    resposta = client_com_cargo.post(f"{SOLICITACOES}{uuid.uuid7()}/retirar/")

    assert _erro(resposta) == (404, "NOT_FOUND")


def test_quem_nao_le_gestao_nao_descobre_se_a_solicitacao_existe(
    client_diretor: APIClient, tipo_de_teste: TipoDeTeste
) -> None:
    resposta = client_diretor.post(f"{SOLICITACOES}{uuid.uuid7()}/retirar/")

    assert _erro(resposta) == (403, "PERMISSION_DENIED")


@pytest.mark.parametrize(
    ("acao", "campo"), [("reabrir", "justificativa"), ("editar", "justificativa"), ("cancelar", "motivo")]
)
def test_textos_livres_ate_1000_caracteres(
    solicitante: Usuario, client_solicitante: APIClient, acao: str, campo: str
) -> None:
    situacao = {"reabrir": "RECUSADA", "editar": "APROVADA", "cancelar": "EM_ANALISE"}[acao]
    solicitacao = _na_situacao(_enviada(solicitante), situacao)

    resposta = _acao(client_solicitante, solicitacao, acao, conteudo=pedido(), **{campo: "a" * 1001})

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
