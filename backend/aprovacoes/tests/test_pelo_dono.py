"""Comandos do módulo dono e tipo só pelo dono (adendo 2 da spec técnica do motor).

`nova_versao_pelo_dono` e `cancelar_pelo_dono` não conferem quem age: o módulo dono já conferiu. O motor
confere a existência, o tipo e a situação, audita, avisa quem decide e avisa o dono, como nos comandos de
hoje. Um tipo registrado com `so_pelo_modulo_dono=True` recusa, pelas rotas genéricas, o envio e os comandos
do solicitante.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from aprovacoes import public
from aprovacoes.models import Solicitacao
from aprovacoes.tests.conftest import (
    APROVAR_TESTE,
    SOLICITACOES,
    TIPO,
    TipoDeTeste,
    com_cargo,
    decisor_do_cenario,
    enviada,
    levar_a,
    pedido,
    preparar_pedido,
)
from auditoria import public as auditoria
from kernel.errors import BusinessError
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

TIPO_DO_DONO = "teste.do_dono"
CAIXA = "/api/v1/notificacoes/"


@pytest.fixture
def tipo_do_dono(tipo_de_teste: TipoDeTeste) -> Iterator[TipoDeTeste]:
    """Um tipo só pelo dono, decidido com a mesma permissão do tipo de teste."""
    tipo = TipoDeTeste(TIPO_DO_DONO)
    public.registrar_tipo(
        codigo=TIPO_DO_DONO,
        nome="Pedido só pelo dono",
        permissao_de_aprovar=APROVAR_TESTE,
        tem_valor=True,
        preparar=preparar_pedido,
        ao_mudar=tipo.recebidas.append,
        so_pelo_modulo_dono=True,
    )
    try:
        yield tipo
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste(TIPO_DO_DONO)


def _acoes_auditadas(solicitacao: Any) -> list[tuple[str, Any]]:
    return [(r.acao, r.ator_id) for r in auditoria.historico_do_item("solicitacao", solicitacao.id)]


def _caixa(usuario: Usuario) -> list[dict[str, Any]]:
    resposta = apoio.cliente_de(usuario).get(CAIXA, {"limite": 50})
    assert resposta.status_code == 200, resposta.content
    return list(resposta.json()["itens"])


# --- nova_versao_pelo_dono ---


def test_aprovada_volta_a_analise_como_edicao_feita_por_quem_nao_e_o_solicitante(
    tipo_de_teste: TipoDeTeste,
) -> None:
    solicitante, editor = com_cargo("sol"), com_cargo("editor")
    solicitacao = levar_a(enviada(solicitante), "APROVADA", avisos=tipo_de_teste.recebidas)

    public.nova_versao_pelo_dono(
        solicitacao.id, tipo=TIPO, ator_id=editor.id, conteudo=pedido("Bolas novas"), justificativa="Data"
    )

    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_ANALISE"
    assert solicitacao.numero_da_versao_atual == 2
    assert solicitacao.versao_atual.autor_id == editor.id
    assert solicitacao.versao_atual.resumo == "Bolas novas"
    assert solicitacao.solicitante_id == solicitante.id
    assert [m.acontecimento for m in tipo_de_teste.recebidas] == [public.Acontecimento.EDITADA]
    assert tipo_de_teste.recebidas[0].ator_id == editor.id
    assert ("SOLICITACAO_EDITADA", editor.id) in _acoes_auditadas(solicitacao)


@pytest.mark.parametrize("situacao", ["CONTESTADA", "RETIRADA"])
def test_contestada_ou_retirada_e_reenviada(tipo_de_teste: TipoDeTeste, situacao: str) -> None:
    solicitante, editor = com_cargo("sol"), com_cargo("editor")
    solicitacao = levar_a(enviada(solicitante), situacao, avisos=tipo_de_teste.recebidas)

    public.nova_versao_pelo_dono(solicitacao.id, tipo=TIPO, ator_id=editor.id, conteudo=pedido("Corrigido"))

    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_ANALISE"
    assert solicitacao.numero_da_versao_atual == 2
    assert solicitacao.versao_atual.autor_id == editor.id
    assert ("SOLICITACAO_REENVIADA", editor.id) in _acoes_auditadas(solicitacao)
    # O reenvio continua sem aviso ao dono (adendo 1, "Fora deste adendo").
    assert tipo_de_teste.recebidas == []


def test_recusada_e_reaberta_so_com_justificativa(tipo_de_teste: TipoDeTeste) -> None:
    solicitante, editor = com_cargo("sol"), com_cargo("editor")
    solicitacao = levar_a(enviada(solicitante), "RECUSADA", avisos=tipo_de_teste.recebidas)

    with pytest.raises(BusinessError) as falta:
        public.nova_versao_pelo_dono(solicitacao.id, tipo=TIPO, ator_id=editor.id, conteudo=pedido())
    assert falta.value.code == "VALIDATION_ERROR"
    assert "justificativa" in (falta.value.details or {})

    public.nova_versao_pelo_dono(
        solicitacao.id, tipo=TIPO, ator_id=editor.id, conteudo=pedido(), justificativa="Mudou a data"
    )

    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_ANALISE"
    assert solicitacao.numero_da_versao_atual == 2
    assert [m.acontecimento for m in tipo_de_teste.recebidas] == [public.Acontecimento.REABERTA]
    registro = next(
        r
        for r in auditoria.historico_do_item("solicitacao", solicitacao.id)
        if r.acao == "SOLICITACAO_REABERTA"
    )
    assert (registro.ator_id, registro.justificativa) == (editor.id, "Mudou a data")


def test_em_analise_e_retirada_e_reenviada_na_mesma_chamada(tipo_de_teste: TipoDeTeste) -> None:
    solicitante, editor = com_cargo("sol"), com_cargo("editor")
    solicitacao = enviada(solicitante)

    public.nova_versao_pelo_dono(solicitacao.id, tipo=TIPO, ator_id=editor.id, conteudo=pedido("Outro"))

    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "EM_ANALISE"
    assert solicitacao.numero_da_versao_atual == 2
    assert solicitacao.versao_atual.resumo == "Outro"
    acoes = [acao for acao, _ in _acoes_auditadas(solicitacao)]
    assert acoes[-2:] == ["SOLICITACAO_RETIRADA", "SOLICITACAO_REENVIADA"]
    assert [m.acontecimento for m in tipo_de_teste.recebidas] == [public.Acontecimento.RETIRADA]


@pytest.mark.parametrize("situacao", ["CANCELADA", "EM_EXECUCAO", "ENCERRADA"])
def test_situacao_sem_versao_nova_e_recusada(tipo_de_teste: TipoDeTeste, situacao: str) -> None:
    solicitacao = levar_a(enviada(com_cargo("sol")), situacao, avisos=tipo_de_teste.recebidas)

    with pytest.raises(BusinessError) as recusa:
        public.nova_versao_pelo_dono(
            solicitacao.id, tipo=TIPO, ator_id=com_cargo("editor").id, conteudo=pedido(), justificativa="x"
        )

    assert recusa.value.code == "NAO_PODE_EDITAR"
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == situacao


def test_conteudo_passa_pela_validacao_do_tipo(tipo_de_teste: TipoDeTeste) -> None:
    solicitacao = levar_a(enviada(com_cargo("sol")), "APROVADA", avisos=tipo_de_teste.recebidas)

    with pytest.raises(BusinessError) as recusa:
        public.nova_versao_pelo_dono(
            solicitacao.id,
            tipo=TIPO,
            ator_id=com_cargo("editor").id,
            conteudo={"descricao": "", "valor": "1"},
        )

    assert recusa.value.code == "VALIDATION_ERROR"
    solicitacao.refresh_from_db()
    assert (solicitacao.situacao, solicitacao.numero_da_versao_atual) == ("APROVADA", 1)


# --- cancelar_pelo_dono ---


def test_o_sistema_cancela_com_motivo_e_ator_nulo(tipo_de_teste: TipoDeTeste) -> None:
    solicitante = com_cargo("sol")
    decisor = decisor_do_cenario()
    solicitacao = enviada(solicitante)

    public.cancelar_pelo_dono(solicitacao.id, tipo=TIPO, ator_id=None, motivo="A data passou")

    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "CANCELADA"
    registro = next(
        r
        for r in auditoria.historico_do_item("solicitacao", solicitacao.id)
        if r.acao == "SOLICITACAO_CANCELADA"
    )
    assert (registro.ator_id, registro.justificativa) == (None, "A data passou")
    assert [(m.acontecimento, m.ator_id) for m in tipo_de_teste.recebidas] == [
        (public.Acontecimento.CANCELADA, None)
    ]
    saiu = [n for n in _caixa(decisor) if n["tipo"] == "aprovacoes.saiu_da_fila"]
    assert len(saiu) == 1


def test_quem_nao_e_o_solicitante_cancela_pelo_dono(tipo_de_teste: TipoDeTeste) -> None:
    solicitacao = levar_a(enviada(com_cargo("sol")), "APROVADA", avisos=tipo_de_teste.recebidas)
    outro = com_cargo("outro")

    public.cancelar_pelo_dono(solicitacao.id, tipo=TIPO, ator_id=outro.id, motivo="Evento cancelado")

    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "CANCELADA"
    assert ("SOLICITACAO_CANCELADA", outro.id) in _acoes_auditadas(solicitacao)


def test_cancelar_pelo_dono_exige_motivo_e_situacao_cancelavel(tipo_de_teste: TipoDeTeste) -> None:
    em_analise = enviada(com_cargo("sol"))
    with pytest.raises(BusinessError) as sem_motivo:
        public.cancelar_pelo_dono(em_analise.id, tipo=TIPO, ator_id=None, motivo="  ")
    assert sem_motivo.value.code == "VALIDATION_ERROR"

    encerrada = levar_a(enviada(com_cargo("sol2")), "ENCERRADA", avisos=tipo_de_teste.recebidas)
    with pytest.raises(BusinessError) as fora:
        public.cancelar_pelo_dono(encerrada.id, tipo=TIPO, ator_id=None, motivo="Tarde")
    assert fora.value.code == "NAO_PODE_CANCELAR"


def test_tipo_diferente_e_erro_de_programacao_e_inexistente_e_404(tipo_do_dono: TipoDeTeste) -> None:
    solicitacao = enviada(com_cargo("sol"))
    with pytest.raises(ValueError, match="do tipo"):
        public.cancelar_pelo_dono(solicitacao.id, tipo=TIPO_DO_DONO, ator_id=None, motivo="x")
    with pytest.raises(ValueError, match="do tipo"):
        public.nova_versao_pelo_dono(
            solicitacao.id, tipo=TIPO_DO_DONO, ator_id=solicitacao.solicitante_id, conteudo=pedido()
        )

    import uuid

    with pytest.raises(BusinessError) as inexistente:
        public.cancelar_pelo_dono(uuid.uuid4(), tipo=TIPO, ator_id=None, motivo="x")
    assert inexistente.value.code == "NOT_FOUND"
    assert Solicitacao.objects.get(pk=solicitacao.id).situacao == "EM_ANALISE"


# --- tipo só pelo dono nas rotas genéricas ---


def _post(usuario: Usuario, caminho: str, corpo: dict[str, Any]) -> Any:
    return apoio.cliente_de(usuario).post(caminho, corpo, format="json")


def test_rota_de_envio_recusa_o_tipo_so_pelo_dono_e_a_api_publica_aceita(tipo_do_dono: TipoDeTeste) -> None:
    solicitante = com_cargo("sol")

    resposta = _post(solicitante, SOLICITACOES, {"tipo": TIPO_DO_DONO, "conteudo": pedido()})

    assert resposta.status_code == 422, resposta.content
    assert resposta.json()["error"]["code"] == "COMANDO_DO_MODULO_DONO"
    assert not Solicitacao.objects.filter(tipo=TIPO_DO_DONO).exists()
    enviada(solicitante, tipo=TIPO_DO_DONO)
    assert Solicitacao.objects.filter(tipo=TIPO_DO_DONO).count() == 1


@pytest.mark.parametrize(
    ("situacao", "acao", "corpo"),
    [
        ("EM_ANALISE", "retirar", {}),
        ("CONTESTADA", "reenviar", {"conteudo": pedido()}),
        ("RECUSADA", "reabrir", {"justificativa": "Reveja"}),
        ("APROVADA", "editar", {"conteudo": pedido()}),
        ("EM_ANALISE", "cancelar", {"motivo": "Desisti"}),
    ],
)
def test_comandos_do_solicitante_sao_recusados_pela_rota(
    tipo_do_dono: TipoDeTeste, situacao: str, acao: str, corpo: dict[str, Any]
) -> None:
    solicitante = com_cargo("sol")
    solicitacao = levar_a(enviada(solicitante, tipo=TIPO_DO_DONO), situacao, avisos=tipo_do_dono.recebidas)

    resposta = _post(solicitante, f"{SOLICITACOES}{solicitacao.id}/{acao}/", corpo)

    assert resposta.status_code == 422, resposta.content
    assert resposta.json()["error"]["code"] == "COMANDO_DO_MODULO_DONO"
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == situacao


def test_decisoes_continuam_pela_rota_e_acoes_so_mostram_as_decisoes(tipo_do_dono: TipoDeTeste) -> None:
    solicitante, aprovador = com_cargo("sol"), com_cargo("apr", APROVAR_TESTE)
    solicitacao = enviada(solicitante, tipo=TIPO_DO_DONO)

    detalhe_do_solicitante = apoio.cliente_de(solicitante).get(f"{SOLICITACOES}{solicitacao.id}/").json()
    assert detalhe_do_solicitante["acoes"] == []
    detalhe_do_aprovador = apoio.cliente_de(aprovador).get(f"{SOLICITACOES}{solicitacao.id}/").json()
    assert detalhe_do_aprovador["acoes"] == ["aprovar", "contestar", "recusar"]

    from aprovacoes.models import MotivoDeDecisao

    motivo = MotivoDeDecisao.objects.filter(tipo_de_decisao="solicitacao.aprovar", ativo=True).first()
    assert motivo is not None
    resposta = _post(
        aprovador, f"{SOLICITACOES}{solicitacao.id}/aprovar/", {"motivo_id": str(motivo.id), "texto": ""}
    )
    assert resposta.status_code == 200, resposta.content
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "APROVADA"
    assert [m.acontecimento for m in tipo_do_dono.recebidas] == [public.Acontecimento.APROVADA]
