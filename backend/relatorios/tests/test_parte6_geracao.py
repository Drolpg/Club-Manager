"""Parte 6: gerar o arquivo em segundo plano (spec técnica `relatorios/relatorios-pdf-e-csv`, "Gerar"; CA-05 a
CA-07, CA-27).
"""

import io
import logging
import uuid
import zipfile
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.core import mail
from django.core.files.storage import default_storage

from relatorios import tasks
from relatorios.domain.pedido import SituacaoDoPedido
from relatorios.models import PedidoDeRelatorio
from relatorios.services import geracao, pedidos
from relatorios.tests import apoio_pedidos as apoio_de_pedidos
from relatorios.tests.apoio_pedidos import FALHA, TIPO, ZIP, caixa, em, local, na_fila
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

AGORA = local(2026, 11, 20, 10, 0)
PRONTO = "relatorios.pronto"
FALHOU = "relatorios.falhou"


@pytest.fixture(autouse=True)
def _ambiente() -> Iterator[None]:
    with (
        apoio_de_pedidos.tipos_de_teste(),
        em(AGORA),
        mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()),
    ):
        yield


@pytest.fixture
def gestor(diretor: Usuario) -> Usuario:
    apoio.dar_cargo(diretor)
    return diretor


def _gerado(pedido: PedidoDeRelatorio) -> PedidoDeRelatorio:
    geracao.gerar(pedido.id)
    pedido.refresh_from_db()
    return pedido


def _arquivos() -> list[str]:
    try:
        _pastas, nomes = default_storage.listdir("relatorios")
    except FileNotFoundError:
        return []
    return sorted(nomes)


@pytest.fixture(autouse=True)
def _armazenamento_limpo() -> Iterator[None]:
    yield
    for nome in _arquivos():
        default_storage.delete(f"relatorios/{nome}")


def test_ca05_gerar_leva_o_pedido_a_pronto_com_o_pdf(gestor: Usuario) -> None:
    pedido = _gerado(na_fila(gestor))

    assert pedido.situacao == SituacaoDoPedido.PRONTO
    assert pedido.arquivo_chave == f"relatorios/{pedido.id}.pdf"
    assert pedido.arquivo_mime == "application/pdf"
    assert pedido.arquivo_nome.endswith(".pdf")
    with default_storage.open(pedido.arquivo_chave) as arquivo:
        conteudo = arquivo.read()
    assert conteudo.startswith(b"%PDF-")
    assert pedido.arquivo_tamanho == len(conteudo)
    assert (pedido.iniciado_em, pedido.concluido_em) == (AGORA, AGORA)
    assert pedido.expira_em == AGORA + timedelta(days=7)


def test_ca05_csv_sai_em_utf8_com_bom(gestor: Usuario) -> None:
    pedido = _gerado(na_fila(gestor, formato="CSV"))

    assert pedido.arquivo_chave == f"relatorios/{pedido.id}.csv"
    assert pedido.arquivo_mime == "text/csv; charset=utf-8"
    with default_storage.open(pedido.arquivo_chave) as arquivo:
        conteudo = arquivo.read()
    assert conteudo.startswith("﻿".encode())
    assert "Mensalidade;10,00" in conteudo.decode("utf-8-sig")


def test_ca05_mais_de_um_documento_sai_num_zip_de_csv(gestor: Usuario) -> None:
    pedido = _gerado(na_fila(gestor, tipo=ZIP, formato="CSV"))

    assert pedido.arquivo_chave == f"relatorios/{pedido.id}.zip"
    assert pedido.arquivo_mime == "application/zip"
    with default_storage.open(pedido.arquivo_chave) as arquivo:
        nomes = zipfile.ZipFile(io.BytesIO(arquivo.read())).namelist()
    assert len(nomes) == 2
    assert len(set(nomes)) == 2
    assert all(nome.endswith(".csv") for nome in nomes)


def test_ca05_quem_pediu_recebe_relatorio_pronto_sem_arquivo_nem_link(
    gestor: Usuario, admin: Usuario
) -> None:
    mail.outbox.clear()

    pedido = _gerado(na_fila(gestor))

    [aviso] = caixa(gestor, PRONTO)
    assert aviso["titulo"] == "Relatório pronto"
    assert "Relatório teste_da_geracao" in aviso["texto"]
    assert aviso["caminho"] == "/relatorios"
    assert caixa(admin, PRONTO) == []
    [email] = mail.outbox
    assert email.to == [gestor.email]
    assert email.attachments == []
    corpo = email.body + "".join(str(conteudo) for conteudo, _tipo in getattr(email, "alternatives", []))
    assert str(pedido.id) not in corpo
    assert "arquivo" not in corpo.lower()


def test_ca06_rodar_duas_vezes_deixa_um_arquivo_e_um_aviso(gestor: Usuario) -> None:
    pedido = _gerado(na_fila(gestor))
    concluido_em = pedido.concluido_em

    with em(AGORA + timedelta(minutes=5)):
        segunda = _gerado(pedido)

    assert segunda.concluido_em == concluido_em
    assert _arquivos() == [f"{pedido.id}.pdf"]
    assert len(caixa(gestor, PRONTO)) == 1


def test_ca07_erro_na_montagem_falha_sem_arquivo_e_avisa(
    gestor: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="relatorios")

    pedido = _gerado(na_fila(gestor, tipo=FALHA))

    assert pedido.situacao == SituacaoDoPedido.FALHOU
    assert pedido.codigo_da_falha == "ERRO_NA_GERACAO"
    assert pedido.arquivo_chave == ""
    assert _arquivos() == []
    [aviso] = caixa(gestor, FALHOU)
    assert aviso["titulo"] == "Não foi possível gerar o relatório"
    assert caixa(gestor, PRONTO) == []
    registros = [r for r in caplog.records if r.name.startswith("relatorios")]
    assert any(getattr(r, "pedido_id", None) == str(pedido.id) for r in registros)
    assert "Fulano" not in caplog.text
    assert all("Fulano" not in str(r.__dict__) for r in registros)


def test_pedido_que_falhou_enquanto_gerava_nao_fica_pronto_nem_deixa_arquivo(gestor: Usuario) -> None:
    """A rotina diária marcou o pedido como parado no meio da geração: o arquivo escrito sai."""
    pedido = na_fila(gestor)
    montar_original = geracao.montar_documentos

    def montar_e_ser_parado(*args: Any) -> Any:
        pedidos.falhar(pedido.id, "PARADO")
        return montar_original(*args)

    with mock.patch.object(geracao, "montar_documentos", side_effect=montar_e_ser_parado):
        pedido = _gerado(pedido)

    assert pedido.situacao == SituacaoDoPedido.FALHOU
    assert pedido.codigo_da_falha == "PARADO"
    assert _arquivos() == []
    assert caixa(gestor, PRONTO) == []


@pytest.mark.parametrize("situacao", [SituacaoDoPedido.PRONTO, SituacaoDoPedido.FALHOU])
def test_pedido_que_nao_esta_na_fila_nao_e_tocado(gestor: Usuario, situacao: SituacaoDoPedido) -> None:
    pedido = _gerado(na_fila(gestor, tipo=TIPO if situacao == SituacaoDoPedido.PRONTO else FALHA))
    antes = PedidoDeRelatorio.objects.values().get(id=pedido.id)

    with em(AGORA + timedelta(hours=2)):
        geracao.gerar(pedido.id)

    assert PedidoDeRelatorio.objects.values().get(id=pedido.id) == antes


def test_pedido_inexistente_nao_e_erro(gestor: Usuario) -> None:
    pedido = na_fila(gestor)

    geracao.gerar(uuid.UUID(int=0))

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.NA_FILA


def test_o_log_mede_duracao_e_memoria_sem_dado_pessoal(
    gestor: Usuario, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="relatorios")

    pedido = _gerado(na_fila(gestor))

    [registro] = [r for r in caplog.records if r.getMessage() == "relatorios.geracao.concluida"]
    assert registro.__dict__["pedido_id"] == str(pedido.id)
    assert (registro.__dict__["tipo"], registro.__dict__["formato"]) == (TIPO, "PDF")
    assert registro.__dict__["linhas"] == 1
    assert isinstance(registro.__dict__["duracao_ms"], int)
    assert "memoria_max_kb" in registro.__dict__
    assert gestor.nome not in str(registro.__dict__)
    assert gestor.email not in str(registro.__dict__)


def test_a_tarefa_so_chama_a_geracao(gestor: Usuario) -> None:
    pedido = na_fila(gestor)

    with mock.patch.object(geracao, "gerar") as gerar:
        tasks.gerar_relatorio(str(pedido.id))

    gerar.assert_called_once_with(pedido.id)


def test_pedir_com_a_fila_de_verdade_gera_na_hora_nos_testes(gestor: Usuario) -> None:
    """Com o Celery em modo imediato nos testes, pedir chega ao pronto: o caminho inteiro está ligado."""
    pedido = pedidos.pedir(gestor.id, tipo=TIPO, formato="CSV", parametros=dict(apoio_de_pedidos.MES))

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.PRONTO
