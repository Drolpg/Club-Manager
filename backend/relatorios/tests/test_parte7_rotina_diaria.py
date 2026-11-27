"""Parte 7: a rotina diária de `relatorios` (spec técnica `relatorios/relatorios-pdf-e-csv`, "Rotina diária";
CA-08, CA-13 a CA-15; ADR-020).

Expira os arquivos prontos há 7 dias e marca como falha o que está gerando há mais de uma hora. Idempotente, e
só apaga chaves de `relatorios/`.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from unittest import mock

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from auditoria import public as auditoria
from relatorios import tasks
from relatorios.domain.pedido import SituacaoDoPedido
from relatorios.models import PedidoDeRelatorio
from relatorios.services import geracao, pedidos, rotina_diaria
from relatorios.tests import apoio_pedidos as apoio_de_pedidos
from relatorios.tests.apoio_pedidos import TIPO, caixa, em, local, na_fila
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

AGORA = local(2026, 11, 27, 3, 0)
OUTROS = ("financeiro/comprovantes/a.pdf", "financeiro/cotacoes/b.pdf", "comunicacao/documentos/c.pdf")


@pytest.fixture(autouse=True)
def _ambiente() -> Iterator[None]:
    with (
        apoio_de_pedidos.tipos_de_teste(),
        mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()),
    ):
        yield


@pytest.fixture(autouse=True)
def _armazenamento_limpo() -> Iterator[None]:
    yield
    for pasta in ("relatorios", "financeiro/comprovantes", "financeiro/cotacoes", "comunicacao/documentos"):
        try:
            nomes = default_storage.listdir(pasta)[1]
        except FileNotFoundError:
            continue
        for nome in nomes:
            default_storage.delete(f"{pasta}/{nome}")


@pytest.fixture
def gestor(diretor: Usuario) -> Usuario:
    apoio.dar_cargo(diretor)
    return diretor


def _pronto_em(usuario: Usuario, instante: datetime) -> PedidoDeRelatorio:
    with em(instante):
        pedido = na_fila(usuario)
        geracao.gerar(pedido.id)
    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.PRONTO
    return pedido


def _gerando_desde(usuario: Usuario, instante: datetime) -> PedidoDeRelatorio:
    with em(instante):
        pedido = na_fila(usuario)
        pedidos.iniciar_geracao(pedido.id)
    pedido.refresh_from_db()
    return pedido


def _rodar(instante: datetime = AGORA) -> dict[str, int]:
    with em(instante):
        return rotina_diaria.executar(instante)


def _expiracoes(pedido: PedidoDeRelatorio) -> list[auditoria.Registro]:
    registros = auditoria.historico_do_item("pedido_de_relatorio", pedido.id)
    return [r for r in registros if r.acao == "RELATORIO_EXPIRADO"]


def test_ca13_pronto_ha_mais_de_sete_dias_expira_e_o_arquivo_sai(gestor: Usuario) -> None:
    pedido = _pronto_em(gestor, AGORA - timedelta(days=7, minutes=1))
    chave = pedido.arquivo_chave

    contagem = _rodar()

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.EXPIRADO
    assert pedido.expirado_em == AGORA
    assert not default_storage.exists(chave)
    assert pedido.arquivo_chave == chave
    assert (pedido.tipo, pedido.parametros, pedido.pedido_por_id) == (
        TIPO,
        {"de": "2026-10-01", "ate": "2026-10-31"},
        gestor.id,
    )
    [registro] = _expiracoes(pedido)
    assert registro.ator_id is None
    assert registro.dados == {"tipo": TIPO}
    assert contagem["expirados"] == 1


def test_ca13_pronto_ha_seis_dias_nao_muda(gestor: Usuario) -> None:
    pedido = _pronto_em(gestor, AGORA - timedelta(days=6))

    _rodar()

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.PRONTO
    assert default_storage.exists(pedido.arquivo_chave)


def test_ca13_rodar_duas_vezes_nao_muda_nada_na_segunda(gestor: Usuario) -> None:
    pedido = _pronto_em(gestor, AGORA - timedelta(days=8))
    _gerando_desde(gestor, AGORA - timedelta(hours=2))
    _rodar()
    antes = list(PedidoDeRelatorio.objects.order_by("id").values())

    segunda = _rodar(AGORA + timedelta(minutes=30))

    assert segunda == {"expirados": 0, "parados": 0, "erros": 0}
    assert list(PedidoDeRelatorio.objects.order_by("id").values()) == antes
    assert len(_expiracoes(pedido)) == 1
    assert len(caixa(gestor, "relatorios.falhou")) == 1


def test_ca08_gerando_ha_mais_de_uma_hora_falha_e_avisa(gestor: Usuario) -> None:
    pedido = _gerando_desde(gestor, AGORA - timedelta(hours=1, minutes=1))

    contagem = _rodar()

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.FALHOU
    assert pedido.codigo_da_falha == "PARADO"
    [aviso] = caixa(gestor, "relatorios.falhou")
    assert aviso["titulo"] == "Não foi possível gerar o relatório"
    assert contagem["parados"] == 1


def test_ca08_gerando_ha_menos_de_uma_hora_nao_muda(gestor: Usuario) -> None:
    pedido = _gerando_desde(gestor, AGORA - timedelta(minutes=59))

    _rodar()

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.GERANDO
    assert caixa(gestor, "relatorios.falhou") == []


def test_ca14_so_os_arquivos_de_relatorio_expirados_saem(gestor: Usuario) -> None:
    for chave in OUTROS:
        default_storage.save(chave, ContentFile(b"%PDF-1.4 anexo original"))
    expirado = _pronto_em(gestor, AGORA - timedelta(days=10))
    recente = _pronto_em(gestor, AGORA - timedelta(days=1))

    _rodar()

    assert all(default_storage.exists(chave) for chave in OUTROS)
    assert not default_storage.exists(expirado.arquivo_chave)
    assert default_storage.exists(recente.arquivo_chave)


def test_ca14_chave_fora_de_relatorios_nunca_e_apagada(gestor: Usuario) -> None:
    """Defesa em profundidade (ADR-020): mesmo um pedido com a chave de outro contexto não apaga o anexo."""
    pedido = _pronto_em(gestor, AGORA - timedelta(days=10))
    default_storage.delete(pedido.arquivo_chave)
    default_storage.save(OUTROS[0], ContentFile(b"%PDF-1.4 comprovante"))
    PedidoDeRelatorio.objects.filter(id=pedido.id).update(arquivo_chave=OUTROS[0])

    _rodar()

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.EXPIRADO
    assert default_storage.exists(OUTROS[0])


def test_ca15_repetir_um_expirado_cria_um_pedido_novo_com_os_mesmos_parametros(gestor: Usuario) -> None:
    expirado = _pronto_em(gestor, AGORA - timedelta(days=8))
    _rodar()

    with em(AGORA), mock.patch("relatorios.tasks.gerar_relatorio.delay"):
        novo = pedidos.pedir(
            gestor.id, tipo=expirado.tipo, formato=expirado.formato, parametros=expirado.parametros
        )

    assert novo.id != expirado.id
    assert (novo.situacao, novo.parametros) == (SituacaoDoPedido.NA_FILA, expirado.parametros)
    expirado.refresh_from_db()
    assert expirado.situacao == SituacaoDoPedido.EXPIRADO


def test_a_tarefa_diaria_so_chama_a_rotina() -> None:
    with em(AGORA), mock.patch.object(rotina_diaria, "executar", return_value={}) as executar:
        tasks.processar_rotina_diaria()

    executar.assert_called_once_with(AGORA)


def test_a_rotina_roda_as_tres_da_manha() -> None:
    agenda = settings.CELERY_BEAT_SCHEDULE["relatorios.processar_rotina_diaria"]
    assert agenda["task"] == "relatorios.processar_rotina_diaria"
    assert (agenda["schedule"].hour, agenda["schedule"].minute) == ({3}, {0})
