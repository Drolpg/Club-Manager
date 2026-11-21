"""Parte 1: proposta, aprovação, orçamento e publicação (CA-02 a CA-10; adendo 1 da funcional).

O evento é aprovado pelo motor (`eventos.evento`) e, com custo, também pelo orçamento (`financeiro.gasto`), em
qualquer ordem. A situação é recalculada na mesma transação de cada decisão.
"""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from eventos import handlers
from eventos.domain.situacao import SituacaoDoEvento
from eventos.models import Evento, Presenca, RespostaDePresenca
from eventos.services import eventos
from eventos.tests.conftest import (
    SOLICITACOES,
    aprovar,
    caixa,
    categoria,
    conteudo_da_tela,
    decidir,
    diretor,
    itens_do_orcamento,
    proposta,
    recarregado,
)
from kernel.errors import BusinessError
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

S = SituacaoDoEvento


def _propor(papeis: dict[str, Usuario], **mudar: Any) -> Evento:
    return eventos.propor(papeis["proponente"].id, **proposta(**mudar))


def _orcamento(papeis: dict[str, Usuario], evento: Evento, valor: str = "400.00") -> uuid.UUID:
    eventos.abrir_orcamento(papeis["aprovador"].id, evento.id, **itens_do_orcamento(valor))
    orcamento = recarregado(evento).solicitacao_orcamentaria_id
    assert orcamento is not None
    return orcamento


def _acoes(evento: Evento) -> list[str]:
    return [r.acao for r in auditoria.historico_do_item("evento", evento.id)]


# --- proposta (CA-02, CA-03) ---


def test_ca02_proposta_fica_em_aprovacao_e_quem_aprova_eventos_e_avisado(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)

    assert evento.situacao == S.EM_APROVACAO
    assert evento.solicitacao_do_evento_id is not None
    solicitacao = aprovacoes.obter_solicitacao(evento.id_da_solicitacao_do_evento)
    assert (solicitacao.tipo, solicitacao.situacao) == ("eventos.evento", aprovacoes.Situacao.EM_ANALISE)
    assert solicitacao.solicitante_id == papeis["proponente"].id
    assert solicitacao.conteudo["titulo"] == "Amistoso contra o Vila"
    assert solicitacao.conteudo["evento_id"] == str(evento.id)
    assert len(caixa(papeis["aprovador"], "aprovacoes.para_decidir")) == 1
    assert "EVENTO_PROPOSTO" in _acoes(evento)


@pytest.mark.parametrize(
    ("campo", "mudar"),
    [
        ("titulo", {"titulo": "  "}),
        ("inicio", {"inicio": timezone.now() - timedelta(hours=1)}),
        ("categoria_id", {"categoria_id": uuid.uuid4()}),
    ],
)
def test_ca03_proposta_invalida_e_recusada(
    papeis: dict[str, Usuario], campo: str, mudar: dict[str, Any]
) -> None:
    with pytest.raises(BusinessError) as recusa:
        _propor(papeis, **mudar)

    assert recusa.value.code == "VALIDATION_ERROR"
    assert campo in recusa.value.details
    assert not Evento.objects.exists()


def test_ca03_categoria_inativa_e_recusada(papeis: dict[str, Usuario]) -> None:
    festa = categoria("Festa")
    festa.desativar()

    with pytest.raises(BusinessError) as recusa:
        _propor(papeis, categoria_id=festa.id)

    assert "categoria_id" in recusa.value.details


def test_ca03_quem_nao_pode_propor_e_negado(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as negado:
        eventos.propor(papeis["comum"].id, **proposta())

    assert negado.value.code == "PERMISSION_DENIED"
    assert not Evento.objects.exists()


def test_quem_aprovaria_o_proprio_evento_indica_outro_aprovador(papeis: dict[str, Usuario]) -> None:
    do_setor = diretor("setor.eventos", "eventos.propor", "eventos.aprovar")

    with pytest.raises(BusinessError) as sem_indicacao:
        eventos.propor(do_setor.id, **proposta())
    assert sem_indicacao.value.code == "APROVADOR_NAO_INDICADO"

    evento = eventos.propor(do_setor.id, **proposta(), aprovador_indicado_id=papeis["aprovador"].id)
    assert evento.situacao == S.EM_APROVACAO


def test_preparar_devolve_o_retrato_do_evento_e_recusa_outro_solicitante(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)

    preparado = handlers.preparar_solicitacao_do_evento(
        {"evento_id": str(evento.id), "titulo": "ignorado"}, papeis["proponente"].id
    )
    assert (preparado.resumo, preparado.valor, preparado.conteudo["titulo"]) == (
        "Amistoso contra o Vila",
        None,
        "Amistoso contra o Vila",
    )
    for conteudo, solicitante in (
        ({"evento_id": str(evento.id)}, papeis["comum"].id),
        ({"evento_id": str(uuid.uuid4())}, papeis["proponente"].id),
        ({}, papeis["proponente"].id),
    ):
        with pytest.raises(BusinessError) as recusa:
            handlers.preparar_solicitacao_do_evento(conteudo, solicitante)
        assert "evento_id" in recusa.value.details


# --- publicação (CA-04 a CA-10) ---


def test_ca04_sem_custo_aprovado_e_publicado_e_todos_os_diretores_avisados_uma_vez(
    papeis: dict[str, Usuario],
) -> None:
    evento = _propor(papeis)

    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)

    evento = recarregado(evento)
    assert (evento.situacao, evento.publicacoes) == (S.PUBLICADO, 1)
    for papel in ("proponente", "aprovador", "gastos", "comum"):
        assert len(caixa(papeis[papel], "eventos.publicado")) == 1
    assert "EVENTO_PUBLICADO" in _acoes(evento)


def test_ca05_com_custo_so_o_evento_aprovado_fica_fora_e_avisa_para_montar_o_orcamento(
    papeis: dict[str, Usuario],
) -> None:
    evento = _propor(papeis, envolve_custo=True)

    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)

    assert recarregado(evento).situacao == S.EM_APROVACAO
    assert len(caixa(papeis["aprovador"], "eventos.montar_orcamento")) == 1
    assert caixa(papeis["comum"], "eventos.publicado") == []


def test_ca06_orcamento_por_quem_aprova_eventos_um_so_e_so_com_custo(papeis: dict[str, Usuario]) -> None:
    com_custo = _propor(papeis, envolve_custo=True)
    sem_custo = _propor(papeis, titulo="Reunião", categoria_id=categoria("Reunião").id)

    with pytest.raises(BusinessError) as negado:
        eventos.abrir_orcamento(papeis["proponente"].id, com_custo.id, **itens_do_orcamento())
    assert negado.value.code == "PERMISSION_DENIED"

    orcamento = _orcamento(papeis, com_custo)
    info = aprovacoes.obter_solicitacao(orcamento)
    assert (info.tipo, info.solicitante_id) == ("financeiro.gasto", papeis["aprovador"].id)
    assert "ORCAMENTO_VINCULADO" in _acoes(com_custo)

    with pytest.raises(BusinessError) as segundo:
        eventos.abrir_orcamento(papeis["aprovador"].id, com_custo.id, **itens_do_orcamento())
    assert segundo.value.code == "ORCAMENTO_JA_VINCULADO"
    with pytest.raises(BusinessError) as sem:
        eventos.abrir_orcamento(papeis["aprovador"].id, sem_custo.id, **itens_do_orcamento())
    assert sem.value.code == "EVENTO_SEM_CUSTO"


@pytest.mark.parametrize("primeiro", ["evento", "orcamento"])
def test_ca07_com_as_duas_aprovacoes_em_qualquer_ordem_e_publicado(
    papeis: dict[str, Usuario], primeiro: str
) -> None:
    evento = _propor(papeis, envolve_custo=True)
    orcamento = _orcamento(papeis, evento)
    ordem = [
        (papeis["aprovador"], evento.id_da_solicitacao_do_evento),
        (papeis["gastos"], orcamento),
    ]
    if primeiro == "orcamento":
        ordem.reverse()

    aprovar(*ordem[0])
    assert recarregado(evento).situacao == S.EM_APROVACAO
    aprovar(*ordem[1])

    assert recarregado(evento).situacao == S.PUBLICADO
    assert len(caixa(papeis["comum"], "eventos.publicado")) == 1


def test_ca08_orcamento_contestado_com_teto_reenviado_e_aprovado_publica(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis, envolve_custo=True)
    orcamento = _orcamento(papeis, evento, "500.00")
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)

    contestar = decidir(papeis["gastos"], orcamento, "contestar", teto_sugerido="350.00")
    assert contestar.status_code == 200, contestar.content
    reenviar = apoio.cliente_de(papeis["aprovador"]).post(
        f"{SOLICITACOES}{orcamento}/reenviar/", {"conteudo": conteudo_da_tela("350.00")}, format="json"
    )
    assert reenviar.status_code == 200, reenviar.content
    assert recarregado(evento).situacao == S.EM_APROVACAO
    aprovar(papeis["gastos"], orcamento)

    assert recarregado(evento).situacao == S.PUBLICADO


def test_ca09_recusado_e_reaberto_segue_o_caminho_normal(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)
    recusa = decidir(papeis["aprovador"], evento.id_da_solicitacao_do_evento, "recusar")
    assert recusa.status_code == 200, recusa.content
    assert recarregado(evento).situacao == S.RECUSADO
    assert "EVENTO_RECUSADO" in _acoes(evento)

    with pytest.raises(BusinessError) as sem_justificativa:
        eventos.reabrir(papeis["proponente"].id, evento.id, justificativa=" ")
    assert sem_justificativa.value.code == "VALIDATION_ERROR"
    with pytest.raises(BusinessError) as terceiro:
        eventos.reabrir(papeis["comum"].id, evento.id, justificativa="Quero")
    assert terceiro.value.code == "PERMISSION_DENIED"

    eventos.reabrir(papeis["proponente"].id, evento.id, justificativa="Mudamos o local")
    assert recarregado(evento).situacao == S.EM_APROVACAO
    registro = next(
        r for r in auditoria.historico_do_item("evento", evento.id) if r.acao == "EVENTO_REABERTO"
    )
    assert registro.justificativa == "Mudamos o local"
    with pytest.raises(BusinessError) as de_novo:
        eventos.reabrir(papeis["proponente"].id, evento.id, justificativa="De novo")
    assert de_novo.value.code == "NAO_ESTA_RECUSADO"

    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    assert recarregado(evento).situacao == S.PUBLICADO


def test_ca10_proponente_que_aprova_eventos_nao_decide_o_proprio(papeis: dict[str, Usuario]) -> None:
    do_setor = diretor("setor.eventos", "eventos.propor", "eventos.aprovar")
    evento = eventos.propor(do_setor.id, **proposta(), aprovador_indicado_id=papeis["aprovador"].id)

    resposta = decidir(do_setor, evento.id_da_solicitacao_do_evento, "aprovar")

    assert resposta.status_code == 403, resposta.content
    assert resposta.json()["error"]["code"] == "SOLICITANTE_NAO_DECIDE"
    assert recarregado(evento).situacao == S.EM_APROVACAO


# --- orçamento mudando por fora ---


def test_orcamento_cancelado_por_quem_o_abriu_se_desliga_e_aceita_outro(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis, envolve_custo=True)
    primeiro = _orcamento(papeis, evento)

    aprovacoes.cancelar(primeiro, ator_id=papeis["aprovador"].id, motivo="Orçamento errado")

    evento = recarregado(evento)
    assert evento.solicitacao_orcamentaria_id is None
    assert evento.situacao == S.EM_APROVACAO
    assert "ORCAMENTO_DESVINCULADO" in _acoes(evento)
    assert len(caixa(papeis["aprovador"], "eventos.montar_orcamento")) == 1
    segundo = _orcamento(papeis, evento)
    assert segundo != primeiro


def test_orcamento_editado_depois_de_publicado_tira_do_calendario_ate_nova_aprovacao(
    papeis: dict[str, Usuario],
) -> None:
    evento = _propor(papeis, envolve_custo=True)
    orcamento = _orcamento(papeis, evento)
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    aprovar(papeis["gastos"], orcamento)
    Presenca.responder(recarregado(evento), diretor_id=papeis["comum"].id, resposta=RespostaDePresenca.VOU)

    editar = apoio.cliente_de(papeis["aprovador"]).post(
        f"{SOLICITACOES}{orcamento}/editar/", {"conteudo": conteudo_da_tela("450.00")}, format="json"
    )
    assert editar.status_code == 200, editar.content

    assert recarregado(evento).situacao == S.EM_APROVACAO
    assert len(caixa(papeis["comum"], "eventos.despublicado")) == 1
    assert caixa(papeis["gastos"], "eventos.despublicado") == []
    assert "EVENTO_DESPUBLICADO" in _acoes(evento)

    aprovar(papeis["gastos"], orcamento)
    evento = recarregado(evento)
    assert (evento.situacao, evento.publicacoes) == (S.PUBLICADO, 2)
    assert len(caixa(papeis["comum"], "eventos.publicado")) == 2


def test_rota_generica_do_motor_nao_abre_solicitacao_de_evento(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)

    resposta = apoio.cliente_de(papeis["proponente"]).post(
        SOLICITACOES, {"tipo": "eventos.evento", "conteudo": {"evento_id": str(evento.id)}}, format="json"
    )

    assert resposta.status_code == 422, resposta.content
    assert resposta.json()["error"]["code"] == "COMANDO_DO_MODULO_DONO"


@pytest.mark.sem_atalho_de_commit
def test_o_email_da_publicacao_so_e_enfileirado_depois_do_commit(
    papeis: dict[str, Usuario], django_capture_on_commit_callbacks: Any
) -> None:
    evento = _propor(papeis)

    with django_capture_on_commit_callbacks(execute=False) as pendentes:
        aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)

    assert recarregado(evento).situacao == S.PUBLICADO
    assert pendentes, "a publicação agenda os e-mails para depois do commit"
