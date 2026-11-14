"""Aprovar, contestar e recusar (CA-03 a 05, 07, 08, 19, 21 a 25; INV-SOL-01 a 04, 07, 10 e 11).

A regra do próprio pedido (INV-SOL-02) é testada por todos os caminhos: sem a permissão, com a permissão, com
aprovador indicado, com acesso total, com auto-aprovação e como admin. As notificações entram no checkpoint 6;
a concorrência (CA-06) fica em `test_concorrencia.py`.
"""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.test import APIClient

from aprovacoes import public
from aprovacoes.models import Decisao, MotivoDeDecisao, Solicitacao
from aprovacoes.tests.conftest import (
    APROVAR_TESTE,
    AUTO_APROVAR,
    SOLICITACOES,
    TIPO,
    TipoDeTeste,
    com_cargo,
    levar_a,
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


def _motivo(texto: str) -> MotivoDeDecisao:
    return MotivoDeDecisao.objects.get(texto=texto)


def _aprovar_corpo(**extra: Any) -> dict[str, Any]:
    return {"motivo_id": str(_motivo("Dentro do orçamento").id), **extra}


def _contestar_corpo(**extra: Any) -> dict[str, Any]:
    return {"motivo_id": str(_motivo("Valor acima do necessário").id), "mensagem": "Reveja o valor.", **extra}


def _recusar_corpo(**extra: Any) -> dict[str, Any]:
    return {"motivo_id": str(_motivo("Sem caixa disponível").id), **extra}


CORPOS = {"aprovar": _aprovar_corpo, "contestar": _contestar_corpo, "recusar": _recusar_corpo}


def _enviada(solicitante: Usuario, tipo: str = TIPO, indicado: Usuario | None = None) -> Solicitacao:
    solicitacao_id = public.enviar(
        tipo=tipo,
        conteudo=pedido(),
        solicitante_id=solicitante.id,
        aprovador_indicado_id=indicado.id if indicado else None,
    )
    return Solicitacao.objects.get(pk=solicitacao_id)


def _decidir(client: APIClient, solicitacao: Solicitacao, acao: str, **corpo: Any) -> Any:
    dados = CORPOS[acao](**corpo)
    return client.post(f"{SOLICITACOES}{solicitacao.id}/{acao}/", dados, format="json")


@pytest.fixture
def solicitante(tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario) -> Usuario:
    return diretor_com_cargo


@pytest.fixture
def client_aprovador(aprovador: Usuario) -> APIClient:
    return apoio.cliente_de(aprovador)


# --- CA-03: aprovar ---


def test_ca03_o_aprovador_aprova_com_motivo_e_a_decisao_guarda_tudo(
    solicitante: Usuario, aprovador: Usuario, client_aprovador: APIClient, tipo_de_teste: TipoDeTeste
) -> None:
    solicitacao = _enviada(solicitante)

    resposta = _decidir(client_aprovador, solicitacao, "aprovar", texto="Pode comprar.")

    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["situacao"] == "APROVADA"
    decisao = Decisao.objects.get(versao__solicitacao=solicitacao)
    assert (decisao.tipo, decisao.aprovador_id, decisao.versao.numero) == ("APROVAR", aprovador.id, 1)
    assert (decisao.motivo_id, decisao.motivo_texto) == (
        _motivo("Dentro do orçamento").id,
        "Dentro do orçamento",
    )
    assert (decisao.texto, decisao.mensagem, decisao.teto_sugerido) == ("Pode comprar.", "", None)
    assert decisao.aprovacao_propria is False
    assert decisao.criada_em is not None
    (mudanca,) = tipo_de_teste.recebidas
    assert mudanca == public.MudancaDeSolicitacao(
        solicitacao_id=solicitacao.id,
        tipo=TIPO,
        acontecimento=Acontecimento.APROVADA,
        versao=1,
        valor=Dinheiro("150.00"),
        ator_id=aprovador.id,
        teto_sugerido=None,
    )


# --- CA-04: motivo ---


@pytest.mark.parametrize("acao", ["aprovar", "contestar", "recusar"])
def test_ca04_decisao_sem_motivo_e_recusada(
    solicitante: Usuario, client_aprovador: APIClient, acao: str
) -> None:
    solicitacao = _enviada(solicitante)
    corpo = CORPOS[acao]()
    del corpo["motivo_id"]

    resposta = client_aprovador.post(f"{SOLICITACOES}{solicitacao.id}/{acao}/", corpo, format="json")

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert not Decisao.objects.exists()


def test_ca04_motivo_desativado_e_recusado(solicitante: Usuario, client_aprovador: APIClient) -> None:
    motivo = _motivo("Dentro do orçamento")
    motivo.desativar()
    motivo.save(update_fields=["ativo"])
    solicitacao = _enviada(solicitante)

    resposta = _decidir(client_aprovador, solicitacao, "aprovar")

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "motivo_id" in resposta.json()["error"]["details"]


def test_ca04_motivo_de_outro_tipo_de_decisao_e_recusado(
    solicitante: Usuario, client_aprovador: APIClient
) -> None:
    solicitacao = _enviada(solicitante)

    resposta = _decidir(
        client_aprovador, solicitacao, "aprovar", motivo_id=str(_motivo("Pedido duplicado").id)
    )

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "motivo_id" in resposta.json()["error"]["details"]
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_ANALISE"


# --- CA-05 e INV-SOL-01: só em análise ---


@pytest.mark.parametrize("acao", ["aprovar", "contestar", "recusar"])
@pytest.mark.parametrize(
    "situacao", ["RETIRADA", "CONTESTADA", "RECUSADA", "APROVADA", "EM_EXECUCAO", "ENCERRADA", "CANCELADA"]
)
def test_ca05_inv_sol_01_fora_de_analise_nao_se_decide(
    solicitante: Usuario, client_aprovador: APIClient, situacao: str, acao: str
) -> None:
    solicitacao = levar_a(_enviada(solicitante), situacao)
    decisoes_antes = Decisao.objects.count()

    assert _erro(_decidir(client_aprovador, solicitacao, acao)) == (422, "NAO_ESTA_EM_ANALISE")
    assert Decisao.objects.count() == decisoes_antes


def test_inv_sol_01_a_decisao_vale_para_a_versao_vigente(
    solicitante: Usuario, client_aprovador: APIClient
) -> None:
    solicitacao = _enviada(solicitante)
    _decidir(client_aprovador, solicitacao, "contestar")
    apoio.cliente_de(solicitante).post(
        f"{SOLICITACOES}{solicitacao.id}/reenviar/", {"conteudo": pedido("Bolas oficiais")}, format="json"
    )

    _decidir(client_aprovador, solicitacao, "aprovar")

    decisoes = {d.versao.numero: d.tipo for d in Decisao.objects.filter(versao__solicitacao=solicitacao)}
    assert decisoes == {1: "CONTESTAR", 2: "APROVAR"}


def test_inv_sol_03_a_versao_decidida_nao_recebe_outra_decisao(
    solicitante: Usuario, client_aprovador: APIClient
) -> None:
    solicitacao = _enviada(solicitante)
    _decidir(client_aprovador, solicitacao, "aprovar")

    assert _erro(_decidir(client_aprovador, solicitacao, "recusar")) == (422, "NAO_ESTA_EM_ANALISE")
    assert Decisao.objects.count() == 1


# --- CA-07 e CA-08: contestar ---


def test_ca07_o_aprovador_contesta_com_motivo_mensagem_e_teto(
    solicitante: Usuario, aprovador: Usuario, client_aprovador: APIClient, tipo_de_teste: TipoDeTeste
) -> None:
    solicitacao = _enviada(solicitante)

    resposta = _decidir(client_aprovador, solicitacao, "contestar", teto_sugerido="100.00")

    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["situacao"] == "CONTESTADA"
    decisao = Decisao.objects.get()
    assert (decisao.tipo, decisao.mensagem, decisao.teto_sugerido) == (
        "CONTESTAR",
        "Reveja o valor.",
        Decimal("100"),
    )
    (mudanca,) = tipo_de_teste.recebidas
    assert (mudanca.acontecimento, mudanca.teto_sugerido) == (Acontecimento.CONTESTADA, Dinheiro("100.00"))


def test_inv_sol_04_contestar_sem_teto_tambem_vale(solicitante: Usuario, client_aprovador: APIClient) -> None:
    solicitacao = _enviada(solicitante)

    assert _decidir(client_aprovador, solicitacao, "contestar").status_code == 200
    assert Decisao.objects.get().teto_sugerido is None


@pytest.mark.parametrize("mensagem", [None, "", "   "])
def test_ca08_inv_sol_04_contestar_sem_mensagem_e_recusado(
    solicitante: Usuario, client_aprovador: APIClient, mensagem: str | None
) -> None:
    solicitacao = _enviada(solicitante)
    corpo = _contestar_corpo()
    if mensagem is None:
        del corpo["mensagem"]
    else:
        corpo["mensagem"] = mensagem

    resposta = client_aprovador.post(f"{SOLICITACOES}{solicitacao.id}/contestar/", corpo, format="json")

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert not Decisao.objects.exists()


def test_ca08_inv_sol_07_teto_em_solicitacao_sem_valor_e_recusado(
    solicitante: Usuario, client_aprovador: APIClient
) -> None:
    def sem_valor(conteudo: dict[str, Any], solicitante_id: Any) -> public.ConteudoPreparado:
        return public.ConteudoPreparado(conteudo=conteudo, valor=None, resumo="Reserva do campo")

    public.registrar_tipo(
        codigo="teste.sem_valor",
        nome="Sem valor",
        permissao_de_aprovar=APROVAR_TESTE,
        tem_valor=False,
        preparar=sem_valor,
        ao_mudar=lambda mudanca: None,
    )
    try:
        solicitacao = _enviada(solicitante, "teste.sem_valor")
        com_teto = _decidir(client_aprovador, solicitacao, "contestar", teto_sugerido="50.00")
        sem_teto = _decidir(client_aprovador, solicitacao, "contestar")
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("teste.sem_valor")

    assert _erro(com_teto) == (422, "TETO_SEM_VALOR")
    assert sem_teto.status_code == 200


@pytest.mark.parametrize("teto", ["0", "0.00", "-1", "abc", "1.001"])
def test_inv_sol_07_teto_precisa_ser_maior_que_zero(
    solicitante: Usuario, client_aprovador: APIClient, teto: str
) -> None:
    solicitacao = _enviada(solicitante)

    assert _erro(_decidir(client_aprovador, solicitacao, "contestar", teto_sugerido=teto)) == (
        400,
        "VALIDATION_ERROR",
    )


def test_adendo_a12_teto_maior_que_o_valor_pedido_e_aceito(
    solicitante: Usuario, client_aprovador: APIClient
) -> None:
    solicitacao = _enviada(solicitante)

    assert _decidir(client_aprovador, solicitacao, "contestar", teto_sugerido="999.00").status_code == 200


# --- recusar ---


def test_o_aprovador_recusa_com_motivo_e_o_dono_e_avisado(
    solicitante: Usuario, client_aprovador: APIClient, tipo_de_teste: TipoDeTeste
) -> None:
    solicitacao = _enviada(solicitante)

    resposta = _decidir(client_aprovador, solicitacao, "recusar", texto="Fica para o ano que vem.")

    assert resposta.status_code == 200
    assert resposta.json()["situacao"] == "RECUSADA"
    assert Decisao.objects.get().motivo_texto == "Sem caixa disponível"
    assert [m.acontecimento for m in tipo_de_teste.recebidas] == [Acontecimento.RECUSADA]


# --- quem decide (CA-19, CA-21 a CA-25; INV-SOL-02, INV-SOL-10, INV-SOL-11; adendo 1, A2) ---


@pytest.mark.parametrize("acao", ["aprovar", "contestar", "recusar"])
def test_ca19_sem_a_permissao_nao_decide_o_proprio_nem_o_de_outro(solicitante: Usuario, acao: str) -> None:
    outro = com_cargo("outro")
    proprio = _enviada(solicitante)
    de_outro = _enviada(outro)
    client = apoio.cliente_de(solicitante)

    assert _erro(_decidir(client, proprio, acao)) == (403, "SOLICITANTE_NAO_DECIDE")
    assert _erro(_decidir(client, de_outro, acao)) == (403, "PERMISSION_DENIED")
    assert not Decisao.objects.exists()


def test_ca21_inv_sol_11_o_indicado_decide_aquela_solicitacao_e_nenhuma_outra(aprovador: Usuario) -> None:
    indicado = com_cargo("indicado")
    indicada = _enviada(aprovador, indicado=indicado)
    outra = _enviada(com_cargo("outro"))
    client = apoio.cliente_de(indicado)

    assert _erro(_decidir(client, outra, "aprovar")) == (403, "PERMISSION_DENIED")
    assert _decidir(client, indicada, "aprovar").status_code == 200
    assert Decisao.objects.get().aprovador_id == indicado.id


def test_inv_sol_11_a_indicacao_vale_para_as_versoes_seguintes(aprovador: Usuario) -> None:
    indicado = com_cargo("indicado")
    solicitacao = _enviada(aprovador, indicado=indicado)
    client = apoio.cliente_de(indicado)
    _decidir(client, solicitacao, "contestar")
    apoio.cliente_de(aprovador).post(
        f"{SOLICITACOES}{solicitacao.id}/reenviar/", {"conteudo": pedido()}, format="json"
    )

    assert _decidir(client, solicitacao, "aprovar").status_code == 200


def test_p3_com_indicado_os_demais_aprovadores_e_o_admin_continuam_decidindo(
    aprovador: Usuario, client_admin: APIClient
) -> None:
    indicado = com_cargo("indicado")
    outro_aprovador = apoio.cliente_de(com_cargo("eva", APROVAR_TESTE))
    primeira = _enviada(aprovador, indicado=indicado)
    segunda = _enviada(aprovador, indicado=indicado)

    assert _decidir(outro_aprovador, primeira, "aprovar").status_code == 200
    assert _decidir(client_admin, segunda, "aprovar").status_code == 200


@pytest.mark.parametrize("acao", ["aprovar", "contestar", "recusar"])
def test_ca22_inv_sol_02_quem_tem_a_permissao_sem_auto_aprovacao_nao_decide_o_proprio_mesmo_com_indicado(
    aprovador: Usuario, acao: str
) -> None:
    solicitacao = _enviada(aprovador, indicado=com_cargo("indicado"))

    assert _erro(_decidir(apoio.cliente_de(aprovador), solicitacao, acao)) == (403, "SOLICITANTE_NAO_DECIDE")


def test_ca23_inv_sol_02_com_auto_aprovacao_decide_o_proprio_marcado_como_aprovacao_propria(
    tipo_de_teste: TipoDeTeste,
) -> None:
    auto = com_cargo("auto", APROVAR_TESTE, AUTO_APROVAR)
    solicitacao = _enviada(auto)

    resposta = _decidir(apoio.cliente_de(auto), solicitacao, "aprovar")

    assert resposta.status_code == 200, resposta.content
    decisao = Decisao.objects.get()
    assert (decisao.aprovador_id, decisao.aprovacao_propria) == (auto.id, True)
    aprovada = [
        r for r in auditoria.historico_do_item("solicitacao", solicitacao.id) if r.acao.endswith("APROVADA")
    ]
    assert aprovada[0].dados["aprovacao_propria"] is True


def test_ca24_inv_sol_02_acesso_total_sem_auto_aprovacao_nao_decide_o_proprio(
    tipo_de_teste: TipoDeTeste,
) -> None:
    total = com_cargo("total", "acesso.total")
    solicitacao = _enviada(total, indicado=com_cargo("indicado"))

    assert _erro(_decidir(apoio.cliente_de(total), solicitacao, "aprovar")) == (403, "SOLICITANTE_NAO_DECIDE")


def test_ca24_acesso_total_decide_o_de_outro(solicitante: Usuario) -> None:
    total = com_cargo("total", "acesso.total")
    solicitacao = _enviada(solicitante)

    assert _decidir(apoio.cliente_de(total), solicitacao, "aprovar").status_code == 200


def test_ca25_inv_sol_02_o_admin_decide_qualquer_uma_inclusive_a_propria(
    solicitante: Usuario, admin: Usuario, client_admin: APIClient
) -> None:
    de_outro = _enviada(solicitante)
    propria = _enviada(admin)

    assert _decidir(client_admin, de_outro, "recusar").status_code == 200
    assert _decidir(client_admin, propria, "aprovar").status_code == 200
    marcas = {d.versao.solicitacao_id: d.aprovacao_propria for d in Decisao.objects.all()}
    assert marcas == {de_outro.id: False, propria.id: True}


def test_a2_quem_tem_a_permissao_e_nao_tem_cargo_nao_decide(solicitante: Usuario) -> None:
    sem_cargo = apoio.criar_diretor("sem.cargo")
    apoio.conceder(sem_cargo, APROVAR_TESTE)
    solicitacao = _enviada(solicitante)

    assert _erro(_decidir(apoio.cliente_de(sem_cargo), solicitacao, "aprovar")) == (403, "PERMISSION_DENIED")


def test_a2_o_servico_tambem_exige_a_leitura_de_gestao(solicitante: Usuario) -> None:
    from aprovacoes.services import decisoes
    from kernel.errors import BusinessError

    sem_cargo = apoio.criar_diretor("sem.cargo")
    apoio.conceder(sem_cargo, APROVAR_TESTE)
    solicitacao = _enviada(solicitante)

    with pytest.raises(BusinessError) as erro:
        decisoes.aprovar(
            ator_id=sem_cargo.id, solicitacao_id=solicitacao.id, motivo_id=_motivo("Dentro do orçamento").id
        )

    assert (erro.value.status, erro.value.code) == (403, "PERMISSION_DENIED")


def test_ca12_a_retirada_nao_pode_ser_decidida(solicitante: Usuario, client_aprovador: APIClient) -> None:
    solicitacao = _enviada(solicitante)
    apoio.cliente_de(solicitante).post(f"{SOLICITACOES}{solicitacao.id}/retirar/")

    assert _erro(_decidir(client_aprovador, solicitacao, "aprovar")) == (422, "NAO_ESTA_EM_ANALISE")


# --- transversais ---


def test_ca33_cada_decisao_gera_registro_de_auditoria(
    solicitante: Usuario, aprovador: Usuario, client_aprovador: APIClient
) -> None:
    solicitacao = _enviada(solicitante)
    _decidir(client_aprovador, solicitacao, "contestar")
    apoio.cliente_de(solicitante).post(
        f"{SOLICITACOES}{solicitacao.id}/reenviar/", {"conteudo": pedido()}, format="json"
    )
    _decidir(client_aprovador, solicitacao, "recusar")
    apoio.cliente_de(solicitante).post(
        f"{SOLICITACOES}{solicitacao.id}/reabrir/", {"justificativa": "Tem caixa agora"}, format="json"
    )
    _decidir(client_aprovador, solicitacao, "aprovar")

    registros = auditoria.historico_do_item("solicitacao", solicitacao.id)
    decisoes = [r for r in registros if r.ator_id == aprovador.id]
    assert [r.acao for r in decisoes] == [
        "SOLICITACAO_CONTESTADA",
        "SOLICITACAO_RECUSADA",
        "SOLICITACAO_APROVADA",
    ]
    assert [r.dados["versao"] for r in decisoes] == [1, 2, 3]
    assert decisoes[0].justificativa == "Valor acima do necessário"


def test_o_erro_no_aviso_ao_modulo_dono_desfaz_a_decisao(
    solicitante: Usuario, client_aprovador: APIClient
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
        resposta = _decidir(client_aprovador, solicitacao, "aprovar")
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("teste.falho")

    assert _erro(resposta) == (500, "INTERNAL_ERROR")
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_ANALISE"
    assert not Decisao.objects.exists()


@pytest.mark.parametrize(
    ("acao", "campo"), [("aprovar", "texto"), ("contestar", "mensagem"), ("recusar", "texto")]
)
def test_a11_textos_da_decisao_ate_1000_caracteres(
    solicitante: Usuario, client_aprovador: APIClient, acao: str, campo: str
) -> None:
    solicitacao = _enviada(solicitante)

    assert _erro(_decidir(client_aprovador, solicitacao, acao, **{campo: "a" * 1001})) == (
        400,
        "VALIDATION_ERROR",
    )


def test_decidir_solicitacao_inexistente(client_aprovador: APIClient) -> None:
    resposta = client_aprovador.post(
        f"{SOLICITACOES}{uuid.uuid7()}/aprovar/", _aprovar_corpo(), format="json"
    )

    assert _erro(resposta) == (404, "NOT_FOUND")
