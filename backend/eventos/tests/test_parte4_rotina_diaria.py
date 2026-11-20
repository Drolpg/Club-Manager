"""Parte 4: rotina diária (CA-18, CA-25; P2, P4; regra 13).

Idempotente: rodar de novo no mesmo dia não repete nada. Cada evento na própria transação. As datas são as do
fuso do sistema (`America/Sao_Paulo`): "a data passou" é a data local do evento antes de hoje.
"""

from datetime import date, datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from eventos import tasks
from eventos.domain.situacao import SituacaoDoEvento
from eventos.models import Evento
from eventos.services import eventos, rotina_diaria
from eventos.tests.conftest import aprovar, caixa, decidir, itens_do_orcamento, proposta, recarregado
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

S = SituacaoDoEvento
HOJE = date(2026, 12, 10)


def _local(dia: date, hora: int, minuto: int = 0) -> datetime:
    return timezone.make_aware(datetime(dia.year, dia.month, dia.day, hora, minuto))


def _em(evento: Evento, inicio: datetime) -> Evento:
    """Põe o evento noutra data sem passar pelos métodos (só para montar o cenário)."""
    Evento.objects.filter(pk=evento.pk).update(inicio=inicio)
    return recarregado(evento)


def _propor(papeis: dict[str, Usuario], **mudar: Any) -> Evento:
    return eventos.propor(papeis["proponente"].id, **proposta(**mudar))


def _publicado(papeis: dict[str, Usuario]) -> Evento:
    evento = _propor(papeis)
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    return recarregado(evento)


# --- cancelamento pela data (CA-25) ---


def test_ca25_em_aprovacao_e_recusado_com_a_data_passada_sao_cancelados_uma_vez(
    papeis: dict[str, Usuario],
) -> None:
    em_aprovacao = _em(_propor(papeis), _local(HOJE - timedelta(days=1), 20))
    recusado = _propor(papeis, titulo="Festa")
    assert decidir(papeis["aprovador"], recusado.id_da_solicitacao_do_evento, "recusar").status_code == 200
    recusado = _em(recusado, _local(HOJE - timedelta(days=2), 20))
    publicado = _em(_publicado(papeis), _local(HOJE - timedelta(days=1), 20))
    de_hoje = _em(_propor(papeis, titulo="Reunião"), _local(HOJE, 8))

    primeira = rotina_diaria.executar(HOJE)
    segunda = rotina_diaria.executar(HOJE)

    assert (primeira["cancelados"], segunda["cancelados"]) == (2, 0)
    for evento in (em_aprovacao, recusado):
        evento = recarregado(evento)
        assert (evento.situacao, evento.cancelado_pelo_sistema, evento.cancelado_por_id) == (
            S.CANCELADO,
            True,
            None,
        )
        assert evento.cancelamento_motivo == "A data passou sem aprovação"
        solicitacao = aprovacoes.situacao_de(evento.id_da_solicitacao_do_evento)
        assert solicitacao == aprovacoes.Situacao.CANCELADA
        registro = next(
            r for r in auditoria.historico_do_item("evento", evento.id) if r.acao == "EVENTO_CANCELADO"
        )
        assert (registro.ator_id, registro.dados["pelo_sistema"]) == (None, True)
    assert recarregado(publicado).situacao == S.PUBLICADO
    assert recarregado(de_hoje).situacao == S.EM_APROVACAO
    assert len(caixa(papeis["proponente"], "eventos.cancelado_pela_data")) == 2
    assert caixa(papeis["comum"], "eventos.cancelado") == []
    assert caixa(papeis["comum"], "eventos.cancelado_pela_data") == []


def test_ca25_o_orcamento_do_evento_cancelado_pela_data_tambem_e_cancelado(
    papeis: dict[str, Usuario],
) -> None:
    evento = _propor(papeis, envolve_custo=True)
    eventos.abrir_orcamento(papeis["aprovador"].id, evento.id, **itens_do_orcamento())
    evento = _em(evento, _local(HOJE - timedelta(days=1), 20))
    orcamento = evento.solicitacao_orcamentaria_id
    assert orcamento is not None

    rotina_diaria.executar(HOJE)

    assert aprovacoes.situacao_de(orcamento) == aprovacoes.Situacao.CANCELADA


def test_virada_de_dia_no_fuso_local(papeis: dict[str, Usuario]) -> None:
    """23h30 em São Paulo já é o dia seguinte em UTC: a data do evento é a local."""
    evento = _em(_propor(papeis), _local(HOJE - timedelta(days=1), 23, 30))
    assert evento.data_do_evento == HOJE - timedelta(days=1)
    de_hoje = _em(_propor(papeis, titulo="Outro"), _local(HOJE, 0, 15))

    rotina_diaria.executar(HOJE)

    assert recarregado(evento).situacao == S.CANCELADO
    assert recarregado(de_hoje).situacao == S.EM_APROVACAO


# --- aviso na data e lembretes (CA-18) ---


def test_ca18_aviso_na_data_e_lembretes_de_1_e_3_dias_uma_vez_cada(papeis: dict[str, Usuario]) -> None:
    admin = apoio.criar_admin("admin.lembra")
    evento = _em(_publicado(papeis), _local(HOJE, 19))

    for dia, esperado in ((-1, 0), (0, 1), (0, 0), (1, 1), (2, 0), (3, 1), (4, 0)):
        resultado = rotina_diaria.executar(HOJE + timedelta(days=dia))
        assert resultado["avisos"] == esperado, dia

    for usuario in (papeis["proponente"], papeis["aprovador"], admin):
        assert len(caixa(usuario, "eventos.realizacao_pendente")) == 3
    assert caixa(papeis["comum"], "eventos.realizacao_pendente") == []
    acoes = [r.acao for r in auditoria.historico_do_item("evento", evento.id)]
    assert acoes.count("AVISO_DE_REALIZACAO_ENVIADO") == 3


def test_ca18_evento_realizado_para_os_lembretes(papeis: dict[str, Usuario]) -> None:
    hoje = timezone.localdate()
    evento = _em(_publicado(papeis), timezone.localtime().replace(hour=0, minute=30))
    rotina_diaria.executar(hoje)
    eventos.realizar(papeis["proponente"].id, evento.id)

    assert rotina_diaria.executar(hoje + timedelta(days=1))["avisos"] == 0
    assert len(caixa(papeis["proponente"], "eventos.realizacao_pendente")) == 1


def test_atraso_de_varios_dias_manda_as_etapas_devidas_de_uma_vez(papeis: dict[str, Usuario]) -> None:
    _em(_publicado(papeis), _local(HOJE, 19))

    assert rotina_diaria.executar(HOJE + timedelta(days=5))["avisos"] == 3
    assert rotina_diaria.executar(HOJE + timedelta(days=5))["avisos"] == 0


def test_erro_num_evento_nao_impede_os_outros(papeis: dict[str, Usuario]) -> None:
    primeiro = _em(_propor(papeis), _local(HOJE - timedelta(days=1), 20))
    segundo = _em(_propor(papeis, titulo="Segundo"), _local(HOJE - timedelta(days=1), 21))
    original = eventos.cancelar_pelo_sistema

    def falha_no_primeiro(evento_id: Any, hoje: date) -> bool:
        if evento_id == primeiro.id:
            raise RuntimeError("falha simulada")
        return original(evento_id, hoje)

    with mock.patch.object(eventos, "cancelar_pelo_sistema", side_effect=falha_no_primeiro):
        resultado = rotina_diaria.executar(HOJE)

    assert (resultado["cancelados"], resultado["erros"]) == (1, 1)
    assert recarregado(primeiro).situacao == S.EM_APROVACAO
    assert recarregado(segundo).situacao == S.CANCELADO


def test_a_tarefa_so_chama_o_servico_com_a_data_local() -> None:
    with mock.patch.object(rotina_diaria, "executar", return_value={"cancelados": 0}) as executar:
        assert tasks.processar_rotina_diaria() == {"cancelados": 0}

    executar.assert_called_once_with(timezone.localdate())
