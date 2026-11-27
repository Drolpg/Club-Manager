"""Parte 5: pedir um relatório (spec técnica `relatorios/relatorios-pdf-e-csv`, "Pedir"; CA-01 a CA-04, CA-15,
CA-28).

Usa um tipo registrado só no teste: o pedido não conhece os sete tipos do clube (CA-27).
"""

from collections.abc import Iterator
from datetime import date, datetime
from typing import Any
from unittest import mock

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from auditoria import public as auditoria
from kernel.errors import BusinessError
from permissoes import public as permissoes
from relatorios import tipos
from relatorios.domain import parametros
from relatorios.domain.documento import Documento
from relatorios.domain.pedido import Formato, SituacaoDoPedido
from relatorios.models import PedidoDeRelatorio, PedidoNaoEApagado
from relatorios.services import pedidos
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

TIPO = "TESTE_DO_PEDIDO"
SO_CSV = "TESTE_SO_CSV"
MES = {"mes": "2026-10"}


def _montar(_parametros: dict[str, Any], _contexto: tipos.Contexto) -> list[Documento]:
    return [Documento(titulo="Relatório de teste", parametros="", resumo=(), tabelas=())]


@pytest.fixture(autouse=True)
def tipos_de_teste() -> Iterator[None]:
    tipos.registrar_tipo_de_relatorio(
        tipos.TipoDeRelatorio(
            codigo=TIPO,
            nome="Relatório de teste",
            formatos=(Formato.PDF, Formato.CSV),
            pode_gerar=permissoes.le_gestao,
            validar_parametros=parametros.periodo,
            montar=_montar,
        )
    )
    tipos.registrar_tipo_de_relatorio(
        tipos.TipoDeRelatorio(
            codigo=SO_CSV,
            nome="Só CSV, de todo usuário",
            formatos=(Formato.CSV,),
            pode_gerar=lambda _usuario_id: True,
            validar_parametros=parametros.nenhum,
            montar=_montar,
        )
    )
    yield
    tipos.remover_tipo_de_relatorio(TIPO)
    tipos.remover_tipo_de_relatorio(SO_CSV)


@pytest.fixture(autouse=True)
def tarefa() -> Iterator[mock.MagicMock]:
    """A geração tem testes próprios: aqui importa só que a tarefa é agendada, com o ID, depois do commit."""
    with mock.patch("relatorios.tasks.gerar_relatorio.delay") as delay:
        yield delay


@pytest.fixture
def gestor(diretor: Usuario) -> Usuario:
    apoio.dar_cargo(diretor)
    return diretor


@pytest.fixture(autouse=True)
def hoje() -> Iterator[None]:
    """Hoje é 20/11/2026: o mês 2026-10 é passado, e 2026-12 é futuro, sem depender do relógio."""
    agora = timezone.make_aware(datetime(2026, 11, 20, 10, 0))
    with mock.patch("django.utils.timezone.now", return_value=agora):
        yield


def _pedir(
    usuario: Usuario, tipo: str = TIPO, formato: str = "PDF", parametros: dict[str, Any] | None = None
) -> PedidoDeRelatorio:
    with mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()):
        return pedidos.pedir(
            usuario.id, tipo=tipo, formato=formato, parametros=MES if parametros is None else parametros
        )


def _erro(usuario: Usuario, **kwargs: Any) -> BusinessError:
    with pytest.raises(BusinessError) as erro:
        _pedir(usuario, **kwargs)
    return erro.value


def test_ca01_pedido_valido_entra_na_fila_com_os_parametros_normalizados(gestor: Usuario) -> None:
    pedido = _pedir(gestor)

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.NA_FILA
    assert (pedido.tipo, pedido.formato, pedido.pedido_por_id) == (TIPO, "PDF", gestor.id)
    assert pedido.parametros == {"de": "2026-10-01", "ate": "2026-10-31"}
    assert pedido.pedido_em == timezone.now()
    assert (pedido.arquivo_chave, pedido.concluido_em, pedido.expira_em) == ("", None, None)


def test_ca01_admin_tambem_pede(admin: Usuario) -> None:
    assert _pedir(admin, formato="CSV").situacao == SituacaoDoPedido.NA_FILA


def test_ca01_pedido_fica_na_auditoria_sem_conteudo(gestor: Usuario) -> None:
    pedido = _pedir(gestor, formato="CSV")

    [registro] = auditoria.historico_do_item("pedido_de_relatorio", pedido.id)
    assert (registro.acao, registro.ator_id) == ("RELATORIO_PEDIDO", gestor.id)
    assert registro.dados == {
        "tipo": TIPO,
        "formato": "CSV",
        "parametros": {"de": "2026-10-01", "ate": "2026-10-31"},
    }


def test_ca28_a_tarefa_recebe_so_o_id_do_pedido(gestor: Usuario, tarefa: mock.MagicMock) -> None:
    pedido = _pedir(gestor)

    tarefa.assert_called_once_with(str(pedido.id))


@pytest.mark.sem_atalho_de_commit
def test_ca28_a_tarefa_so_e_agendada_depois_do_commit(
    gestor: Usuario, tarefa: mock.MagicMock, django_capture_on_commit_callbacks: Any
) -> None:
    with django_capture_on_commit_callbacks(execute=False) as pendentes:
        pedido = pedidos.pedir(gestor.id, tipo=TIPO, formato="PDF", parametros=MES)
        tarefa.assert_not_called()

    assert len(pendentes) == 1
    pendentes[0]()
    tarefa.assert_called_once_with(str(pedido.id))


def test_ca02_diretor_sem_cargo_nao_pede_relatorio_do_clube(diretor: Usuario, tarefa: mock.MagicMock) -> None:
    erro = _erro(diretor)

    assert (erro.status, erro.code) == (403, "PERMISSION_DENIED")
    assert not PedidoDeRelatorio.objects.exists()
    tarefa.assert_not_called()


def test_ca02_sem_cargo_pede_o_tipo_que_e_de_todo_usuario(diretor: Usuario) -> None:
    pedido = _pedir(diretor, tipo=SO_CSV, formato="CSV", parametros={})

    assert pedido.situacao == SituacaoDoPedido.NA_FILA
    assert pedido.parametros == {}


def test_usuario_desativado_nao_pede(gestor: Usuario) -> None:
    Usuario.objects.filter(id=gestor.id).update(situacao="DESATIVADO")

    assert _erro(gestor).code == "PERMISSION_DENIED"


@pytest.mark.parametrize(
    ("pedido", "campo"),
    [
        ({"tipo": "NAO_EXISTE"}, "tipo"),
        ({"tipo": SO_CSV, "formato": "PDF"}, "formato"),
        ({"formato": "XLSX"}, "formato"),
        ({"de": "2026-10-10", "ate": "2026-10-01"}, "ate"),
        ({"de": "2026-11-21", "ate": "2026-11-30"}, "de"),
        ({"mes": "2026-12"}, "mes"),
        ({"mes": "2026-13"}, "mes"),
        ({"mes": "2026-10", "usuario_id": "outro"}, "usuario_id"),
    ],
)
def test_ca03_pedido_invalido_aponta_o_campo_e_nao_entra_na_fila(
    gestor: Usuario, tarefa: mock.MagicMock, pedido: dict[str, str], campo: str
) -> None:
    tipo = pedido.pop("tipo", TIPO)
    formato = pedido.pop("formato", "CSV")

    erro = _erro(gestor, tipo=tipo, formato=formato, parametros=pedido or MES)

    assert (erro.status, erro.code) == (400, "VALIDATION_ERROR")
    assert set(erro.details) == {campo}
    assert not PedidoDeRelatorio.objects.exists()
    tarefa.assert_not_called()


def test_ca03_tipo_que_o_usuario_nao_pode_e_negado_antes_de_validar_os_parametros(diretor: Usuario) -> None:
    assert _erro(diretor, parametros={"mes": "2026-13"}).code == "PERMISSION_DENIED"


def test_ca04_quarto_pedido_em_andamento_e_recusado(gestor: Usuario, tarefa: mock.MagicMock) -> None:
    for _ in range(3):
        _pedir(gestor)
    tarefa.reset_mock()

    erro = _erro(gestor)

    assert (erro.status, erro.code) == (409, "PEDIDOS_EM_ANDAMENTO")
    assert PedidoDeRelatorio.objects.filter(pedido_por_id=gestor.id).count() == 3
    tarefa.assert_not_called()


def test_ca04_quando_um_termina_o_proximo_e_aceito(gestor: Usuario) -> None:
    andamento = [_pedir(gestor) for _ in range(3)]
    gerando = pedidos.iniciar_geracao(andamento[0].id)
    assert gerando is not None
    assert gerando.situacao == SituacaoDoPedido.GERANDO
    assert _erro(gestor).code == "PEDIDOS_EM_ANDAMENTO"

    pedidos.falhar(andamento[0].id, "ERRO_NA_GERACAO")

    assert _pedir(gestor).situacao == SituacaoDoPedido.NA_FILA


def test_ca04_o_limite_e_por_usuario(gestor: Usuario, admin: Usuario) -> None:
    for _ in range(3):
        _pedir(gestor)

    assert _pedir(admin).situacao == SituacaoDoPedido.NA_FILA


def test_ca15_repetir_e_um_pedido_novo_com_os_mesmos_parametros(gestor: Usuario) -> None:
    original = _pedir(gestor, parametros={"de": "2026-09-01", "ate": "2026-09-15"})
    pedidos.iniciar_geracao(original.id)
    pedidos.falhar(original.id, "ERRO_NA_GERACAO")

    novo = _pedir(gestor, parametros=original.parametros)

    assert novo.id != original.id
    assert novo.parametros == original.parametros
    original.refresh_from_db()
    assert original.situacao == SituacaoDoPedido.FALHOU


def test_transicao_fora_de_ordem_nao_muda_o_pedido(gestor: Usuario) -> None:
    pedido = _pedir(gestor)

    assert pedidos.falhar(pedido.id, "ERRO_NA_GERACAO") is None
    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoDoPedido.NA_FILA


def test_o_pedido_nao_e_apagado(gestor: Usuario) -> None:
    pedido = _pedir(gestor)

    with pytest.raises(PedidoNaoEApagado):
        pedido.delete()
    assert PedidoDeRelatorio.objects.filter(id=pedido.id).exists()


def test_o_banco_exige_arquivo_no_pedido_pronto(gestor: Usuario) -> None:
    pedido = _pedir(gestor)
    with pytest.raises(IntegrityError), transaction.atomic():
        PedidoDeRelatorio.objects.filter(id=pedido.id).update(situacao=SituacaoDoPedido.PRONTO)


def test_hoje_e_a_data_local(gestor: Usuario) -> None:
    """O teste fixa o relógio; o período pode ir até hoje, e não além."""
    assert timezone.localdate() == date(2026, 11, 20)
    assert (
        _pedir(gestor, parametros={"de": "2026-11-20", "ate": "2026-11-20"}).parametros["de"] == "2026-11-20"
    )


@pytest.mark.django_db(transaction=True)
def test_migracao_dos_pedidos_e_reversivel() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("relatorios", None)])
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('relatorios_pedidoderelatorio')")
        assert cursor.fetchone() == (None,)

    try:
        call_command("migrate", "relatorios", verbosity=0)
    finally:
        call_command("migrate", verbosity=0)
    assert PedidoDeRelatorio.objects.count() == 0
