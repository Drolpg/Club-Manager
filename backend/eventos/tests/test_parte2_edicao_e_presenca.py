"""Parte 2: edição (CA-15 a CA-17, INV-EVT-03) e presença (CA-13, CA-14; regra 12).

Editar grava os dados novos no evento antes de pedir a versão nova ao motor: o `preparar` monta o retrato a
partir do evento gravado. Mudar a data zera as presenças (P3) sem apagar as respostas antigas.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from eventos.domain.situacao import SituacaoDoEvento
from eventos.models import Evento, Presenca
from eventos.services import eventos, presencas
from eventos.tests.conftest import (
    aprovar,
    caixa,
    categoria,
    decidir,
    itens_do_orcamento,
    proposta,
    recarregado,
)
from kernel.errors import BusinessError
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

S = SituacaoDoEvento


def _meio_dia(dias: int) -> datetime:
    """Meio-dia local daqui a `dias` dias: mexer na hora não muda a data do evento."""
    return timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=dias)


def _propor(papeis: dict[str, Usuario], **mudar: Any) -> Evento:
    return eventos.propor(papeis["proponente"].id, **proposta(inicio=_meio_dia(7), **mudar))


def _publicado(papeis: dict[str, Usuario]) -> Evento:
    evento = _propor(papeis)
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    evento = recarregado(evento)
    assert evento.situacao == S.PUBLICADO
    return evento


def _edicao(evento: Evento, **mudar: Any) -> dict[str, Any]:
    dados: dict[str, Any] = {
        "titulo": evento.titulo,
        "descricao": evento.descricao,
        "inicio": evento.inicio,
        "local": evento.local,
        "categoria_id": evento.categoria_id,
        "envolve_custo": evento.envolve_custo,
    }
    dados.update(mudar)
    return dados


def _editar(ator: Usuario, evento: Evento, justificativa: str = "", **mudar: Any) -> Evento:
    return eventos.editar(ator.id, evento.id, **_edicao(evento, **mudar), justificativa=justificativa)


def _acoes(evento: Evento) -> list[str]:
    return [r.acao for r in auditoria.historico_do_item("evento", evento.id)]


# --- edição (CA-15 a CA-17) ---


def test_ca15_publicado_editado_sai_do_calendario_com_a_versao_nova_em_analise(
    papeis: dict[str, Usuario],
) -> None:
    evento = _publicado(papeis)
    nova_data = _meio_dia(9)

    _editar(papeis["proponente"], evento, titulo="Amistoso remarcado", inicio=nova_data, local="Estádio")

    evento = recarregado(evento)
    assert evento.situacao == S.EM_APROVACAO
    solicitacao = aprovacoes.obter_solicitacao(evento.id_da_solicitacao_do_evento)
    assert (solicitacao.situacao, solicitacao.versao_atual) == (aprovacoes.Situacao.EM_ANALISE, 2)
    assert solicitacao.conteudo["titulo"] == "Amistoso remarcado"
    assert solicitacao.conteudo["local"] == "Estádio"
    assert solicitacao.conteudo["inicio"] == timezone.localtime(nova_data).isoformat()
    registro = next(r for r in auditoria.historico_do_item("evento", evento.id) if r.acao == "EVENTO_EDITADO")
    assert set(registro.dados["campos"]) == {"titulo", "inicio", "local"}

    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    assert recarregado(evento).situacao == S.PUBLICADO


def test_em_analise_a_edicao_gera_versao_nova_ainda_em_analise(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)

    _editar(papeis["proponente"], evento, titulo="Outro título")

    solicitacao = aprovacoes.obter_solicitacao(evento.id_da_solicitacao_do_evento)
    assert (solicitacao.situacao, solicitacao.versao_atual) == (aprovacoes.Situacao.EM_ANALISE, 2)
    assert solicitacao.conteudo["titulo"] == "Outro título"
    assert recarregado(evento).situacao == S.EM_APROVACAO


def test_contestado_e_editado_volta_a_analise(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)
    assert decidir(papeis["aprovador"], evento.id_da_solicitacao_do_evento, "contestar").status_code == 200

    _editar(papeis["proponente"], evento, local="Campo novo")

    solicitacao = aprovacoes.obter_solicitacao(evento.id_da_solicitacao_do_evento)
    assert (solicitacao.situacao, solicitacao.conteudo["local"]) == (
        aprovacoes.Situacao.EM_ANALISE,
        "Campo novo",
    )


def test_recusado_so_e_editado_com_justificativa(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)
    assert decidir(papeis["aprovador"], evento.id_da_solicitacao_do_evento, "recusar").status_code == 200

    with pytest.raises(BusinessError) as sem_justificativa:
        _editar(papeis["proponente"], evento, titulo="Outro")
    assert sem_justificativa.value.code == "VALIDATION_ERROR"
    assert recarregado(evento).titulo == "Amistoso contra o Vila"

    _editar(papeis["proponente"], evento, titulo="Outro", justificativa="Mudamos o adversário")
    assert recarregado(evento).situacao == S.EM_APROVACAO


def test_quem_aprova_eventos_edita_evento_de_outra_pessoa_e_terceiro_nao(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)

    with pytest.raises(BusinessError) as negado:
        _editar(papeis["comum"], evento, titulo="Invasão")
    assert negado.value.code == "PERMISSION_DENIED"

    _editar(papeis["aprovador"], evento, titulo="Ajuste do responsável")
    solicitacao = aprovacoes.obter_solicitacao(evento.id_da_solicitacao_do_evento)
    assert solicitacao.conteudo["titulo"] == "Ajuste do responsável"
    assert solicitacao.solicitante_id == papeis["proponente"].id


def test_edicao_invalida_e_recusada_sem_mudar_nada(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis)

    with pytest.raises(BusinessError) as recusa:
        _editar(papeis["proponente"], evento, titulo=" ", inicio=timezone.now() - timedelta(hours=1))

    assert set(recusa.value.details) == {"titulo", "inicio"}
    assert aprovacoes.obter_solicitacao(evento.id_da_solicitacao_do_evento).versao_atual == 1


def test_tirar_o_custo_com_orcamento_vinculado_e_recusado(papeis: dict[str, Usuario]) -> None:
    evento = _propor(papeis, envolve_custo=True)
    eventos.abrir_orcamento(papeis["aprovador"].id, evento.id, **itens_do_orcamento())

    with pytest.raises(BusinessError) as recusa:
        _editar(papeis["proponente"], recarregado(evento), envolve_custo=False)

    assert recusa.value.code == "ORCAMENTO_JA_VINCULADO"


def test_ca16_mudar_a_data_zera_presencas_avisa_quem_ia_e_a_republicacao_avisa_todos(
    papeis: dict[str, Usuario],
) -> None:
    evento = _publicado(papeis)
    vai, nao_vai = papeis["comum"], papeis["gastos"]
    presencas.responder(vai.id, evento.id, "VOU")
    presencas.responder(nao_vai.id, evento.id, "NAO_VOU")

    _editar(papeis["proponente"], evento, inicio=_meio_dia(12))

    evento = recarregado(evento)
    assert len(caixa(vai, "eventos.despublicado")) == 1
    assert caixa(nao_vai, "eventos.despublicado") == []
    assert evento.ciclo_de_presenca == 2
    assert Presenca.objects.filter(evento=evento).count() == 2
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    quadro = presencas.quadro(papeis["proponente"].id, evento.id)
    assert quadro["vou"] == []
    assert quadro["nao_vou"] == []
    publicados = caixa(vai, "eventos.publicado")
    assert len(publicados) == 2
    assert f"{_meio_dia(12):%d/%m/%Y}" in publicados[0]["texto"]


def test_mudar_outro_campo_nao_zera_as_presencas(papeis: dict[str, Usuario]) -> None:
    evento = _publicado(papeis)
    presencas.responder(papeis["comum"].id, evento.id, "VOU")

    _editar(papeis["proponente"], evento, local="Outro campo", inicio=evento.inicio + timedelta(hours=2))

    assert recarregado(evento).ciclo_de_presenca == 1
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    assert [p["id"] for p in presencas.quadro(papeis["proponente"].id, evento.id)["vou"]] == [
        papeis["comum"].id
    ]


@pytest.mark.parametrize("como", ["realizado", "cancelado"])
def test_ca17_evento_encerrado_nao_e_editado(papeis: dict[str, Usuario], como: str) -> None:
    evento = _publicado(papeis)
    if como == "cancelado":
        evento.cancelar(motivo="Chuva", ator_id=papeis["proponente"].id)
    else:
        hoje = timezone.localdate()
        evento.confirmar_realizacao(
            data_real=hoje, motivo="Antecipado", ator_id=papeis["proponente"].id, hoje=hoje
        )

    with pytest.raises(BusinessError) as encerrado:
        _editar(papeis["proponente"], evento, titulo="Tarde demais")

    assert encerrado.value.code == "EVENTO_ENCERRADO"


# --- presença (CA-13, CA-14) ---


def test_ca13_vale_a_ultima_resposta_e_o_quadro_mostra_quem_vai_quem_nao_vai_e_quem_nao_respondeu(
    papeis: dict[str, Usuario],
) -> None:
    evento = _publicado(papeis)

    presencas.responder(papeis["comum"].id, evento.id, "VOU")
    presencas.responder(papeis["comum"].id, evento.id, "NAO_VOU")
    presencas.responder(papeis["gastos"].id, evento.id, "VOU")

    quadro = presencas.quadro(papeis["comum"].id, evento.id)
    assert [p["id"] for p in quadro["vou"]] == [papeis["gastos"].id]
    assert [p["id"] for p in quadro["nao_vou"]] == [papeis["comum"].id]
    assert {p["id"] for p in quadro["sem_resposta"]} == {papeis["proponente"].id, papeis["aprovador"].id}
    assert quadro["minha"] == "NAO_VOU"
    assert quadro["vou"][0]["nome"] == "Diretor apr.gastos"
    assert _acoes(evento).count("PRESENCA_RESPONDIDA") == 3


def test_ca14_presenca_so_em_publicado_e_de_diretor_com_cargo(papeis: dict[str, Usuario]) -> None:
    em_aprovacao = _propor(papeis)
    with pytest.raises(BusinessError) as fora:
        presencas.responder(papeis["comum"].id, em_aprovacao.id, "VOU")
    assert fora.value.code == "NAO_ESTA_PUBLICADO"

    publicado = _publicado(papeis)
    sem_cargo = apoio.criar_diretor("sem.cargo")
    admin_sem_cargo = apoio.criar_admin("admin.sem.cargo")
    for usuario in (sem_cargo, admin_sem_cargo):
        with pytest.raises(BusinessError) as negado:
            presencas.responder(usuario.id, publicado.id, "VOU")
        assert negado.value.code == "PERMISSION_DENIED"
    with pytest.raises(BusinessError) as invalida:
        presencas.responder(papeis["comum"].id, publicado.id, "TALVEZ")
    assert invalida.value.code == "VALIDATION_ERROR"
    assert not Presenca.objects.exists()


def test_evento_inexistente_e_404_depois_da_leitura_de_gestao(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as inexistente:
        presencas.responder(papeis["comum"].id, uuid.uuid7(), "VOU")
    assert inexistente.value.code == "NOT_FOUND"
    with pytest.raises(BusinessError) as sem_leitura:
        presencas.responder(apoio.criar_diretor("sem.leitura").id, uuid.uuid7(), "VOU")
    assert sem_leitura.value.code == "PERMISSION_DENIED"


def test_categoria_inativa_atual_continua_aceita_e_trocar_por_outra_inativa_nao(
    papeis: dict[str, Usuario],
) -> None:
    evento = _propor(papeis, categoria_id=categoria("Festa").id)
    categoria("Festa").desativar()
    categoria("Reunião").desativar()

    _editar(papeis["proponente"], evento, titulo="Festa de fim de ano")
    assert recarregado(evento).titulo == "Festa de fim de ano"

    with pytest.raises(BusinessError) as trocar:
        _editar(papeis["proponente"], recarregado(evento), categoria_id=categoria("Reunião").id)
    assert "categoria_id" in trocar.value.details
