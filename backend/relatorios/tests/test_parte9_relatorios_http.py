"""Parte 9: as rotas de relatórios sob `/api/v1/relatorios/` (spec técnica, "Rotas"; CA-01 a CA-04, CA-09 a
CA-12, CA-27, CA-28).

Pedir, listar e ver os próprios pedidos, e baixar o arquivo pronto, só de quem pediu. Usa os tipos de teste
de `apoio_pedidos`, que passam pelo fluxo inteiro sem mudar a rota (CA-27).
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.core.files.storage import default_storage
from rest_framework.test import APIClient

from relatorios.models import PedidoDeRelatorio
from relatorios.services import geracao, rotina_diaria
from relatorios.tests import apoio_pedidos as apoio_de_pedidos
from relatorios.tests.apoio_pedidos import FALHA, TIPO, ZIP, em, local
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

BASE = "/api/v1/relatorios/"
PEDIDOS = f"{BASE}pedidos/"
AGORA = local(2026, 11, 20, 10, 0)
MES = {"mes": "2026-10"}


@pytest.fixture(autouse=True)
def _ambiente() -> Iterator[None]:
    with (
        apoio_de_pedidos.tipos_de_teste(),
        em(AGORA),
        mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()),
        mock.patch("relatorios.tasks.gerar_relatorio.delay"),
    ):
        yield


@pytest.fixture(autouse=True)
def _armazenamento_limpo() -> Iterator[None]:
    yield
    try:
        nomes = default_storage.listdir("relatorios")[1]
    except FileNotFoundError:
        return
    for nome in nomes:
        default_storage.delete(f"relatorios/{nome}")


def _cliente(usuario: Usuario) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return cliente


@pytest.fixture
def gestor(diretor: Usuario) -> Usuario:
    apoio.dar_cargo(diretor)
    return diretor


def _pedir(usuario: Usuario, tipo: str = TIPO, formato: str = "PDF", parametros: Any = None) -> Any:
    corpo = {"tipo": tipo, "formato": formato, "parametros": MES if parametros is None else parametros}
    return _cliente(usuario).post(PEDIDOS, corpo, format="json")


def _pronto(usuario: Usuario, **kwargs: Any) -> str:
    resposta = _pedir(usuario, **kwargs)
    assert resposta.status_code == 202, resposta.content
    geracao.gerar(resposta.json()["id"])
    return str(resposta.json()["id"])


def _codigo(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


# Sem sessão --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("get", "tipos/"),
        ("get", "pedidos/"),
        ("post", "pedidos/"),
        ("get", "pedidos/01a00000-0000-7000-8000-000000000000/"),
        ("get", "pedidos/01a00000-0000-7000-8000-000000000000/arquivo/"),
    ],
)
def test_sem_sessao_e_401(metodo: str, caminho: str) -> None:
    resposta = getattr(APIClient(), metodo)(f"{BASE}{caminho}")

    assert _codigo(resposta) == (401, "NOT_AUTHENTICATED")


# Tipos -------------------------------------------------------------------------------------------------


def test_tipos_do_diretor_sem_cargo_so_meus_dados() -> None:
    sem_cargo = apoio.criar_diretor("sem.cargo.http")

    tipos = _cliente(sem_cargo).get(f"{BASE}tipos/").json()

    assert [t["codigo"] for t in tipos] == ["MEUS_DADOS"]
    assert tipos[0] == {
        "codigo": "MEUS_DADOS",
        "nome": "Meus dados",
        "formatos": ["CSV"],
        "parametros": "NENHUM",
    }


def test_tipos_de_quem_le_a_gestao_com_a_forma_dos_parametros(gestor: Usuario) -> None:
    tipos = {t["codigo"]: t for t in _cliente(gestor).get(f"{BASE}tipos/").json()}

    assert tipos["EXTRATO"]["parametros"] == "PERIODO"
    assert tipos["PRESTACAO_DE_CONTAS"]["parametros"] == "PERIODO_E_PENDENTES"
    assert tipos["FLUXO_DE_CAIXA"]["parametros"] == "MESES"
    assert tipos["INADIMPLENCIA"]["parametros"] == "NENHUM"
    assert tipos["EXTRATO"]["formatos"] == ["PDF", "CSV"]


# Pedir (CA-01 a CA-04, CA-28) --------------------------------------------------------------------------


def test_ca01_ca28_pedir_responde_202_com_o_pedido_na_fila_sem_o_arquivo(gestor: Usuario) -> None:
    resposta = _pedir(gestor)

    assert resposta.status_code == 202
    corpo = resposta.json()
    assert set(corpo) == {
        "id",
        "tipo",
        "tipo_nome",
        "formato",
        "parametros",
        "situacao",
        "pedido_em",
        "concluido_em",
        "expira_em",
        "disponivel",
        "codigo_da_falha",
    }
    assert (corpo["situacao"], corpo["disponivel"], corpo["tipo_nome"]) == (
        "NA_FILA",
        False,
        "Relatório teste_da_geracao",
    )
    assert corpo["parametros"] == {"de": "2026-10-01", "ate": "2026-10-31"}


def test_ca02_sem_cargo_pedir_relatorio_do_clube_e_403() -> None:
    sem_cargo = apoio.criar_diretor("sem.cargo.pede")

    assert _codigo(_pedir(sem_cargo)) == (403, "PERMISSION_DENIED")
    assert _pedir(sem_cargo, tipo="MEUS_DADOS", formato="CSV", parametros={}).status_code == 202


@pytest.mark.parametrize(
    ("corpo", "campo"),
    [
        ({"tipo": "NAO_EXISTE", "formato": "PDF", "parametros": MES}, "tipo"),
        ({"tipo": ZIP, "formato": "PDF", "parametros": MES}, "formato"),
        ({"tipo": TIPO, "formato": "PDF", "parametros": {"mes": "2026-13"}}, "mes"),
        ({"tipo": TIPO, "formato": "PDF", "parametros": {"de": "2026-10-10", "ate": "2026-10-01"}}, "ate"),
        ({"tipo": TIPO, "formato": "PDF", "parametros": "texto"}, "parametros"),
        ({"formato": "PDF", "parametros": MES}, "tipo"),
    ],
)
def test_ca03_pedido_invalido_e_400_no_campo(gestor: Usuario, corpo: dict[str, Any], campo: str) -> None:
    resposta = _cliente(gestor).post(PEDIDOS, corpo, format="json")

    assert _codigo(resposta) == (400, "VALIDATION_ERROR")
    assert campo in resposta.json()["error"]["details"]
    assert not PedidoDeRelatorio.objects.exists()


def test_ca04_quarto_pedido_em_andamento_e_409(gestor: Usuario) -> None:
    for _ in range(3):
        assert _pedir(gestor).status_code == 202

    assert _codigo(_pedir(gestor)) == (409, "PEDIDOS_EM_ANDAMENTO")


# Lista e detalhe (CA-12) -------------------------------------------------------------------------------


def test_ca12_lista_so_os_proprios_mais_novos_primeiro_com_cursor(gestor: Usuario, admin: Usuario) -> None:
    primeiro = _pronto(gestor)
    with em(AGORA + timedelta(minutes=1)):
        segundo = _pronto(gestor, formato="CSV")
    _pronto(admin)

    pagina = _cliente(gestor).get(PEDIDOS, {"limite": "1"}).json()
    assert ([p["id"] for p in pagina["itens"]], pagina["tem_mais"]) == ([segundo], True)
    seguinte = _cliente(gestor).get(PEDIDOS, {"limite": "1", "antes": segundo}).json()
    assert ([p["id"] for p in seguinte["itens"]], seguinte["tem_mais"]) == ([primeiro], False)
    item = pagina["itens"][0]
    assert (item["situacao"], item["disponivel"], item["formato"]) == ("PRONTO", True, "CSV")
    assert item["expira_em"] is not None
    assert "arquivo_chave" not in item


@pytest.mark.parametrize("limite", ["0", "51", "abc"])
def test_limite_fora_da_faixa_e_400(gestor: Usuario, limite: str) -> None:
    assert _codigo(_cliente(gestor).get(PEDIDOS, {"limite": limite})) == (400, "VALIDATION_ERROR")


def test_cursor_de_outro_ou_inexistente_e_404(gestor: Usuario, admin: Usuario) -> None:
    do_admin = _pronto(admin)

    for antes in (do_admin, "01a00000-0000-7000-8000-000000000000", "nao-e-id"):
        assert _codigo(_cliente(gestor).get(PEDIDOS, {"antes": antes})) == (404, "NOT_FOUND")


def test_detalhe_so_do_proprio(gestor: Usuario, admin: Usuario) -> None:
    meu = _pronto(gestor)

    assert _cliente(gestor).get(f"{PEDIDOS}{meu}/").json()["id"] == meu
    assert _codigo(_cliente(admin).get(f"{PEDIDOS}{meu}/")) == (403, "PERMISSION_DENIED")


# Download (CA-09 a CA-11) ------------------------------------------------------------------------------


def test_ca09_baixar_o_proprio_pronto_com_os_cabecalhos_seguros(gestor: Usuario) -> None:
    pedido = _pronto(gestor)

    resposta = _cliente(gestor).get(f"{PEDIDOS}{pedido}/arquivo/")

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/pdf"
    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert resposta["Cache-Control"] == "private, no-store"
    assert resposta["Content-Disposition"].startswith('attachment; filename="')
    assert resposta.content.startswith(b"%PDF-")


@pytest.mark.parametrize(
    ("formato", "tipo", "mime"), [("CSV", TIPO, "text/csv; charset=utf-8"), ("CSV", ZIP, "application/zip")]
)
def test_ca09_o_tipo_do_conteudo_segue_o_formato(gestor: Usuario, formato: str, tipo: str, mime: str) -> None:
    pedido = _pronto(gestor, tipo=tipo, formato=formato)

    assert _cliente(gestor).get(f"{PEDIDOS}{pedido}/arquivo/")["Content-Type"] == mime


def test_ca09_pedido_de_outro_ou_inexistente_e_403_mesmo_para_o_admin(
    gestor: Usuario, admin: Usuario
) -> None:
    pedido = _pronto(gestor)

    assert _codigo(_cliente(admin).get(f"{PEDIDOS}{pedido}/arquivo/")) == (403, "PERMISSION_DENIED")
    inexistente = f"{PEDIDOS}01a00000-0000-7000-8000-000000000000/arquivo/"
    assert _codigo(_cliente(gestor).get(inexistente)) == (403, "PERMISSION_DENIED")


def test_ca10_quem_perdeu_o_cargo_nao_baixa_o_do_clube_mas_baixa_meus_dados(
    gestor: Usuario, admin: Usuario
) -> None:
    do_clube = _pronto(gestor)
    meus_dados = _pronto(gestor, tipo="MEUS_DADOS", formato="CSV", parametros={})
    sem_cargo: dict[str, Any] = {"cargo_id": None, "setor_ids": []}
    classificacao = f"/api/v1/permissoes/usuarios/{gestor.id}/classificacao/"
    assert _cliente(admin).put(classificacao, sem_cargo, format="json").status_code == 200

    assert _codigo(_cliente(gestor).get(f"{PEDIDOS}{do_clube}/arquivo/")) == (403, "PERMISSION_DENIED")
    assert _cliente(gestor).get(f"{PEDIDOS}{meus_dados}/arquivo/").status_code == 200


def test_ca11_arquivo_de_pedido_que_nao_esta_pronto_e_409_com_a_situacao(gestor: Usuario) -> None:
    na_fila = _pedir(gestor).json()["id"]
    falhou = _pronto(gestor, tipo=FALHA)

    for pedido, situacao in ((na_fila, "NA_FILA"), (falhou, "FALHOU")):
        resposta = _cliente(gestor).get(f"{PEDIDOS}{pedido}/arquivo/")
        assert _codigo(resposta) == (409, "RELATORIO_NAO_DISPONIVEL")
        assert resposta.json()["error"]["details"] == {"situacao": situacao}


def test_ca27_tipo_de_teste_expira_e_deixa_de_ser_baixado(gestor: Usuario) -> None:
    pedido = _pronto(gestor)

    rotina_diaria.executar(AGORA + timedelta(days=8))

    resposta = _cliente(gestor).get(f"{PEDIDOS}{pedido}/arquivo/")
    assert _codigo(resposta) == (409, "RELATORIO_NAO_DISPONIVEL")
    assert resposta.json()["error"]["details"] == {"situacao": "EXPIRADO"}
    assert _cliente(gestor).get(f"{PEDIDOS}{pedido}/").json()["disponivel"] is False


# OpenAPI -----------------------------------------------------------------------------------------------


def test_as_rotas_estao_no_openapi(admin: Usuario) -> None:
    caminhos = _cliente(admin).get("/api/v1/schema/", {"format": "json"}).json()["paths"]

    for caminho in ("tipos/", "pedidos/", "pedidos/{pedido_id}/", "pedidos/{pedido_id}/arquivo/"):
        assert f"{BASE}{caminho}" in caminhos
