"""Parte 3: realização (CA-19 a CA-21) e cancelamento (CA-22 a CA-24).

Cancelar marca o evento antes de cancelar as solicitações: os tratadores, chamados de volta no meio,
encontram o evento encerrado e não fazem nada.
"""

from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from eventos.domain.situacao import SituacaoDoEvento
from eventos.models import Evento
from eventos.services import eventos, presencas
from eventos.tests.conftest import aprovar, caixa, diretor, itens_do_orcamento, proposta, recarregado
from kernel.errors import BusinessError
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

S = SituacaoDoEvento
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _publicado(papeis: dict[str, Usuario], *, envolve_custo: bool = False) -> Evento:
    evento = eventos.propor(papeis["proponente"].id, **proposta(envolve_custo=envolve_custo))
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    if envolve_custo:
        eventos.abrir_orcamento(papeis["aprovador"].id, evento.id, **itens_do_orcamento("300.00"))
        aprovar(papeis["gastos"], recarregado(evento).solicitacao_orcamentaria_id)  # type: ignore[arg-type]
    evento = recarregado(evento)
    assert evento.situacao == S.PUBLICADO
    return evento


def _para_hoje(evento: Evento) -> date:
    """Traz a data do evento para hoje, sem passar pelos métodos (só para montar o cenário)."""
    agora = timezone.localtime()
    Evento.objects.filter(pk=evento.pk).update(inicio=agora.replace(hour=0, minute=30))
    return agora.date()


def _acoes(evento: Evento) -> list[str]:
    return [r.acao for r in auditoria.historico_do_item("evento", evento.id)]


@pytest.fixture
def financeiro_do_clube(db: None) -> dict[str, Usuario]:
    return {
        "envia": diretor("envia.recurso", "saidas.enviar"),
        "liquida": diretor("liquida.saida", "saidas.liquidar"),
    }


# --- realização (CA-19 a CA-21) ---


@pytest.mark.parametrize("quem", ["proponente", "aprovador", "admin"])
def test_ca19_proponente_aprovador_ou_admin_realiza_e_a_solicitacao_e_encerrada(
    papeis: dict[str, Usuario], quem: str
) -> None:
    evento = _publicado(papeis)
    hoje = _para_hoje(evento)
    ator = apoio.criar_admin("admin.realiza") if quem == "admin" else papeis[quem]

    eventos.realizar(ator.id, evento.id)

    evento = recarregado(evento)
    assert (evento.situacao, evento.realizado_em_data, evento.realizado_por_id) == (
        S.REALIZADO,
        hoje,
        ator.id,
    )
    assert aprovacoes.situacao_de(evento.id_da_solicitacao_do_evento) == aprovacoes.Situacao.ENCERRADA
    assert "EVENTO_REALIZADO" in _acoes(evento)
    avisos = caixa(papeis["proponente"], "eventos.realizado")
    assert len(avisos) == (0 if quem == "proponente" else 1)


def test_ca19_outro_diretor_nao_realiza(papeis: dict[str, Usuario]) -> None:
    evento = _publicado(papeis)
    _para_hoje(evento)

    with pytest.raises(BusinessError) as negado:
        eventos.realizar(papeis["comum"].id, evento.id)

    assert negado.value.code == "PERMISSION_DENIED"


def test_ca20_data_diferente_exige_motivo_futura_e_recusada_e_a_aprovacao_nao_reabre(
    papeis: dict[str, Usuario],
) -> None:
    evento = _publicado(papeis)
    hoje = timezone.localdate()

    with pytest.raises(BusinessError) as sem_motivo:
        eventos.realizar(papeis["proponente"].id, evento.id, data=hoje)
    assert (sem_motivo.value.code, list(sem_motivo.value.details)) == ("VALIDATION_ERROR", ["motivo"])
    with pytest.raises(BusinessError) as futura:
        eventos.realizar(papeis["proponente"].id, evento.id, data=hoje + timedelta(days=1), motivo="x")
    assert futura.value.code == "DATA_FUTURA"

    eventos.realizar(papeis["proponente"].id, evento.id, data=hoje, motivo="Antecipamos por causa da chuva")

    evento = recarregado(evento)
    assert (evento.realizado_em_data, evento.realizacao_motivo) == (hoje, "Antecipamos por causa da chuva")
    assert evento.data_do_evento != hoje
    solicitacao = aprovacoes.obter_solicitacao(evento.id_da_solicitacao_do_evento)
    assert (solicitacao.situacao, solicitacao.versao_atual) == (aprovacoes.Situacao.ENCERRADA, 1)


def test_ca20_so_publicado_e_realizado(papeis: dict[str, Usuario]) -> None:
    evento = eventos.propor(papeis["proponente"].id, **proposta())

    with pytest.raises(BusinessError) as fora:
        eventos.realizar(papeis["proponente"].id, evento.id, motivo="x")

    assert fora.value.code == "NAO_ESTA_PUBLICADO"


def test_ca21_realizado_com_a_saida_em_prestacao_de_contas_encerra_so_o_evento(
    papeis: dict[str, Usuario], financeiro_do_clube: dict[str, Usuario]
) -> None:
    evento = _publicado(papeis, envolve_custo=True)
    orcamento = evento.solicitacao_orcamentaria_id
    assert orcamento is not None
    _enviar_recurso(evento, financeiro_do_clube["envia"])  # a saída espera a prestação de contas
    _para_hoje(evento)

    eventos.realizar(papeis["aprovador"].id, evento.id)

    assert recarregado(evento).situacao == S.REALIZADO
    assert aprovacoes.situacao_de(orcamento) == aprovacoes.Situacao.EM_EXECUCAO


# --- cancelamento (CA-22 a CA-24) ---


def test_ca22_proponente_cancela_com_motivo_e_todos_os_diretores_sao_avisados(
    papeis: dict[str, Usuario],
) -> None:
    evento = _publicado(papeis)

    with pytest.raises(BusinessError) as sem_motivo:
        eventos.cancelar(papeis["proponente"].id, evento.id, motivo=" ")
    assert sem_motivo.value.code == "VALIDATION_ERROR"

    eventos.cancelar(papeis["proponente"].id, evento.id, motivo="Campo interditado")

    evento = recarregado(evento)
    assert (evento.situacao, evento.cancelamento_motivo) == (S.CANCELADO, "Campo interditado")
    assert aprovacoes.situacao_de(evento.id_da_solicitacao_do_evento) == aprovacoes.Situacao.CANCELADA
    for papel in ("aprovador", "gastos", "comum"):
        assert len(caixa(papeis[papel], "eventos.cancelado")) == 1
    assert caixa(papeis["proponente"], "eventos.cancelado") == []
    registro = next(
        r for r in auditoria.historico_do_item("evento", evento.id) if r.acao == "EVENTO_CANCELADO"
    )
    assert (registro.justificativa, registro.dados["pelo_sistema"]) == ("Campo interditado", False)


@pytest.mark.parametrize(
    ("quem", "pode"),
    [("comum", False), ("aprovador", False), ("cancela", True), ("admin", True)],
)
def test_ca23_evento_de_outra_pessoa_so_com_admin_ou_a_permissao(
    papeis: dict[str, Usuario], quem: str, pode: bool
) -> None:
    evento = eventos.propor(papeis["proponente"].id, **proposta())
    atores = {
        "cancela": lambda: diretor("pode.cancelar", "eventos.cancelar"),
        "admin": lambda: apoio.criar_admin("admin.cancela"),
    }
    ator = atores[quem]() if quem in atores else papeis[quem]

    if pode:
        eventos.cancelar(ator.id, evento.id, motivo="Decisão da diretoria")
        assert recarregado(evento).situacao == S.CANCELADO
    else:
        with pytest.raises(BusinessError) as negado:
            eventos.cancelar(ator.id, evento.id, motivo="Não posso")
        assert negado.value.code == "PERMISSION_DENIED"


def test_cancelar_evento_publicado_nao_dispara_os_tratadores(papeis: dict[str, Usuario]) -> None:
    evento = _publicado(papeis)
    presencas.responder(papeis["comum"].id, evento.id, "VOU")

    eventos.cancelar(papeis["proponente"].id, evento.id, motivo="Chuva")

    assert caixa(papeis["comum"], "eventos.despublicado") == []
    assert "EVENTO_DESPUBLICADO" not in _acoes(recarregado(evento))


def test_evento_encerrado_nao_e_cancelado(papeis: dict[str, Usuario]) -> None:
    evento = _publicado(papeis)
    _para_hoje(evento)
    eventos.realizar(papeis["proponente"].id, evento.id)

    with pytest.raises(BusinessError) as encerrado:
        eventos.cancelar(papeis["proponente"].id, evento.id, motivo="Tarde")

    assert encerrado.value.code == "EVENTO_ENCERRADO"


def _enviar_recurso(evento: Evento, quem_envia: Usuario, valor: str = "300.00") -> None:
    """Pelas rotas do financeiro, como faria quem envia recursos."""
    cliente = apoio.cliente_de(quem_envia)
    saidas = cliente.get("/api/v1/financeiro/saidas/", {"evento_id": str(evento.id)}).json()["itens"]
    assert len(saidas) == 1
    comprovante = SimpleUploadedFile("ted.pdf", PDF, content_type="application/pdf")
    resposta = cliente.post(
        f"/api/v1/financeiro/saidas/{saidas[0]['id']}/envios/",
        {"valor": valor, "comprovante": comprovante},
        format="multipart",
    )
    assert resposta.status_code == 201, resposta.content


def test_ca24_orcamento_em_analise_e_cancelado_junto(papeis: dict[str, Usuario]) -> None:
    evento = eventos.propor(papeis["proponente"].id, **proposta(envolve_custo=True))
    eventos.abrir_orcamento(papeis["aprovador"].id, evento.id, **itens_do_orcamento())
    orcamento = recarregado(evento).solicitacao_orcamentaria_id
    assert orcamento is not None

    eventos.cancelar(papeis["proponente"].id, evento.id, motivo="Desistimos")

    assert aprovacoes.situacao_de(orcamento) == aprovacoes.Situacao.CANCELADA
    assert recarregado(evento).solicitacao_orcamentaria_id == orcamento


def test_ca24_orcamento_aprovado_sem_envio_e_cancelado_e_quem_liquida_nao_e_avisado(
    papeis: dict[str, Usuario], financeiro_do_clube: dict[str, Usuario]
) -> None:
    evento = _publicado(papeis, envolve_custo=True)
    orcamento = evento.solicitacao_orcamentaria_id
    assert orcamento is not None

    eventos.cancelar(papeis["proponente"].id, evento.id, motivo="Desistimos")

    assert aprovacoes.situacao_de(orcamento) == aprovacoes.Situacao.CANCELADA
    assert caixa(financeiro_do_clube["liquida"], "financeiro.orcamento_de_evento_cancelado") == []


def test_ca24_com_recurso_enviado_a_saida_continua_e_quem_liquida_e_avisado(
    papeis: dict[str, Usuario], financeiro_do_clube: dict[str, Usuario]
) -> None:
    evento = _publicado(papeis, envolve_custo=True)
    orcamento = evento.solicitacao_orcamentaria_id
    assert orcamento is not None
    _enviar_recurso(evento, financeiro_do_clube["envia"])

    eventos.cancelar(papeis["proponente"].id, evento.id, motivo="Adversário desistiu")

    assert recarregado(evento).situacao == S.CANCELADO
    assert aprovacoes.situacao_de(orcamento) == aprovacoes.Situacao.EM_EXECUCAO
    avisos = caixa(financeiro_do_clube["liquida"], "financeiro.orcamento_de_evento_cancelado")
    assert len(avisos) == 1
    assert "Amistoso contra o Vila" in avisos[0]["texto"]
