"""Parte 6: rotas HTTP sob `/api/v1/eventos/` (spec técnica do M8, "Rotas"; CA-01, CA-11, CA-12, CA-26).

Ordem das conferências: leitura de gestão (403) → entrada (400) → existência (404) → quem pode (403) →
situação (422). O campo `acoes` do detalhe sai da mesma função que as rotas usam; um teste de paridade compara
os dois.
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from eventos.domain.situacao import SituacaoDoEvento
from eventos.models import CategoriaDeEvento, Evento
from eventos.services import eventos
from eventos.tests.conftest import aprovar, decidir, diretor, itens_do_orcamento, proposta, recarregado
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

S = SituacaoDoEvento
BASE = "/api/v1/eventos/"


def _cliente(usuario: Usuario) -> APIClient:
    return apoio.cliente_de(usuario)


def _codigo(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def _corpo_da_proposta(**mudar: Any) -> dict[str, Any]:
    dados = proposta(**mudar)
    dados["inicio"] = dados["inicio"].isoformat()
    dados["categoria_id"] = str(dados["categoria_id"])
    return dados


def _propor(papeis: dict[str, Usuario], **mudar: Any) -> Evento:
    return eventos.propor(papeis["proponente"].id, **proposta(**mudar))


def _publicado(papeis: dict[str, Usuario], **mudar: Any) -> Evento:
    evento = _propor(papeis, **mudar)
    aprovar(papeis["aprovador"], evento.id_da_solicitacao_do_evento)
    return recarregado(evento)


def _em(evento: Evento, inicio: datetime) -> Evento:
    Evento.objects.filter(pk=evento.pk).update(inicio=inicio)
    return recarregado(evento)


# --- acesso ---


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("get", "referencias/"),
        ("get", "calendario/?mes=2026-12"),
        ("get", ""),
        ("post", ""),
        ("get", f"{uuid.uuid4()}/"),
        ("get", f"{uuid.uuid4()}/historico/"),
        ("post", f"{uuid.uuid4()}/cancelar/"),
        ("get", "categorias/"),
    ],
)
def test_sem_cargo_e_sem_sessao_sao_negados(papeis: dict[str, Usuario], metodo: str, caminho: str) -> None:
    sem_cargo = _cliente(apoio.criar_diretor("sem.cargo"))

    assert getattr(sem_cargo, metodo)(BASE + caminho, {}, format="json").status_code == 403
    assert getattr(APIClient(), metodo)(BASE + caminho, {}, format="json").status_code in (401, 403)


# --- referências ---


def test_referencias_trazem_categorias_aprovadores_e_se_precisa_indicar(papeis: dict[str, Usuario]) -> None:
    do_setor = diretor("setor.eventos", "eventos.propor", "eventos.aprovar")

    comum = _cliente(papeis["proponente"]).get(BASE + "referencias/").json()
    do_setor_resp = _cliente(do_setor).get(BASE + "referencias/").json()

    assert {c["nome"] for c in comum["categorias"]} == {"Jogo", "Reunião", "Festa", "Outros"}
    assert {a["id"] for a in comum["aprovadores_eventos"]} >= {str(papeis["aprovador"].id), str(do_setor.id)}
    assert comum["precisa_indicar_aprovador"] is False
    assert do_setor_resp["precisa_indicar_aprovador"] is True


# --- proposta ---


def test_propor_cria_e_devolve_o_detalhe(papeis: dict[str, Usuario]) -> None:
    resposta = _cliente(papeis["proponente"]).post(BASE, _corpo_da_proposta(), format="json")

    assert resposta.status_code == 201, resposta.content
    corpo = resposta.json()
    assert (corpo["situacao"], corpo["titulo"], corpo["proponente"]["id"]) == (
        "EM_APROVACAO",
        "Amistoso contra o Vila",
        str(papeis["proponente"].id),
    )
    assert corpo["solicitacao_do_evento"]["situacao"] == "EM_ANALISE"
    assert corpo["orcamento"] is None


def test_propor_sem_permissao_403_antes_da_entrada_e_entrada_invalida_400(papeis: dict[str, Usuario]) -> None:
    assert _codigo(_cliente(papeis["comum"]).post(BASE, {}, format="json")) == (403, "PERMISSION_DENIED")

    resposta = _cliente(papeis["proponente"]).post(BASE, _corpo_da_proposta(titulo=" "), format="json")
    assert _codigo(resposta) == (400, "VALIDATION_ERROR")
    assert "titulo" in resposta.json()["error"]["details"]
    sem_campos = _cliente(papeis["proponente"]).post(BASE, {"titulo": "x"}, format="json")
    assert _codigo(sem_campos) == (400, "VALIDATION_ERROR")


# --- calendário (CA-11) ---


def test_ca11_calendario_do_mes_so_com_publicados_e_realizados_pela_data_local(
    papeis: dict[str, Usuario],
) -> None:
    dia = date(2026, 12, 31)
    publicado = _em(
        _publicado(papeis, titulo="Réveillon"), timezone.make_aware(datetime(2026, 12, 31, 23, 30))
    )
    realizado = _publicado(papeis, titulo="Jogo realizado")
    hoje = timezone.localdate()
    eventos.realizar(papeis["proponente"].id, realizado.id, data=hoje, motivo="Antecipado")
    em_aprovacao = _em(_propor(papeis, titulo="Em aprovação"), timezone.make_aware(datetime(2026, 12, 5, 10)))
    cancelado = _propor(papeis, titulo="Cancelado")
    eventos.cancelar(papeis["proponente"].id, cancelado.id, motivo="Chuva")

    dezembro = _cliente(papeis["comum"]).get(BASE + "calendario/", {"mes": "2026-12"}).json()
    janeiro = _cliente(papeis["comum"]).get(BASE + "calendario/", {"mes": "2027-01"}).json()

    assert [e["titulo"] for e in dezembro] == ["Réveillon"]
    assert dezembro[0]["inicio"].startswith(f"{dia.isoformat()}T23:30")
    assert janeiro == []
    mes_do_realizado = recarregado(realizado).data_do_evento.strftime("%Y-%m")
    do_realizado = _cliente(papeis["comum"]).get(BASE + "calendario/", {"mes": mes_do_realizado}).json()
    assert {"Jogo realizado"} <= {e["titulo"] for e in do_realizado}
    assert next(e for e in do_realizado if e["titulo"] == "Jogo realizado")["situacao"] == "REALIZADO"
    assert em_aprovacao.titulo not in {e["titulo"] for e in dezembro}
    assert publicado.id


def test_calendario_exige_o_mes(papeis: dict[str, Usuario]) -> None:
    for parametros in ({}, {"mes": "2026-13"}, {"mes": "dezembro"}):
        resposta = _cliente(papeis["comum"]).get(BASE + "calendario/", parametros)
        assert _codigo(resposta) == (400, "VALIDATION_ERROR"), parametros


# --- histórico (CA-26) ---


def test_ca26_historico_com_todos_e_os_filtros(papeis: dict[str, Usuario]) -> None:
    jogo = _publicado(papeis, titulo="Jogo A")
    festa = _propor(papeis, titulo="Festa B", categoria_id=CategoriaDeEvento.objects.get(nome="Festa").id)
    cancelado = _propor(papeis, titulo="Cancelado C")
    eventos.cancelar(papeis["proponente"].id, cancelado.id, motivo="Chuva")
    cliente = _cliente(papeis["comum"])

    todos = cliente.get(BASE).json()
    assert {e["titulo"] for e in todos["itens"]} == {"Jogo A", "Festa B", "Cancelado C"}
    assert todos["tem_mais"] is False
    assert [e["titulo"] for e in cliente.get(BASE, {"situacao": "CANCELADO"}).json()["itens"]] == [
        "Cancelado C"
    ]
    festas = cliente.get(BASE, {"categoria_id": str(festa.categoria_id)}).json()["itens"]
    assert [e["titulo"] for e in festas] == ["Festa B"]
    longe = _em(jogo, timezone.make_aware(datetime(2027, 3, 1, 10)))
    marco = cliente.get(BASE, {"de": "2027-03-01", "ate": "2027-03-31"}).json()["itens"]
    assert [e["id"] for e in marco] == [str(longe.id)]

    primeira = cliente.get(BASE, {"limite": 2}).json()
    assert (len(primeira["itens"]), primeira["tem_mais"]) == (2, True)
    resto = cliente.get(BASE, {"limite": 2, "antes": primeira["itens"][-1]["id"]}).json()
    assert len(resto["itens"]) == 1
    assert {e["id"] for e in primeira["itens"] + resto["itens"]} == {
        str(jogo.id),
        str(festa.id),
        str(cancelado.id),
    }


# --- detalhe e histórico de auditoria (CA-12) ---


def test_ca12_detalhe_com_dados_proponente_solicitacoes_orcamento_presencas_e_acoes(
    papeis: dict[str, Usuario],
) -> None:
    evento = _publicado(papeis, envolve_custo=True)
    eventos.abrir_orcamento(papeis["aprovador"].id, evento.id, **itens_do_orcamento())
    evento = recarregado(evento)
    aprovar(papeis["gastos"], evento.solicitacao_orcamentaria_id)  # type: ignore[arg-type]
    cliente = _cliente(papeis["comum"])
    assert cliente.post(f"{BASE}{evento.id}/presenca/", {"resposta": "VOU"}, format="json").status_code == 200

    corpo = cliente.get(f"{BASE}{evento.id}/").json()

    assert corpo["situacao"] == "PUBLICADO"
    assert corpo["proponente"] == {"id": str(papeis["proponente"].id), "nome": "Diretor prop"}
    assert corpo["solicitacao_do_evento"] == {
        "id": str(evento.solicitacao_do_evento_id),
        "situacao": "APROVADA",
    }
    assert corpo["orcamento"] == {
        "solicitacao_id": str(evento.solicitacao_orcamentaria_id),
        "situacao": "APROVADA",
    }
    assert [p["id"] for p in corpo["presencas"]["vou"]] == [str(papeis["comum"].id)]
    assert corpo["presencas"]["minha"] == "VOU"
    assert corpo["acoes"] == ["responder_presenca"]
    assert (corpo["realizacao"], corpo["cancelamento"]) == (None, None)
    historico = cliente.get(f"{BASE}{evento.id}/historico/").json()
    assert {"EVENTO_PROPOSTO", "ORCAMENTO_VINCULADO", "EVENTO_PUBLICADO", "PRESENCA_RESPONDIDA"} <= {
        r["acao"] for r in historico
    }


def test_detalhe_de_evento_inexistente_e_404(papeis: dict[str, Usuario]) -> None:
    resposta = _cliente(papeis["comum"]).get(f"{BASE}{uuid.uuid4()}/")

    assert _codigo(resposta) == (404, "NOT_FOUND")


def test_detalhe_do_cancelado_e_do_realizado(papeis: dict[str, Usuario]) -> None:
    cancelado = _propor(papeis)
    eventos.cancelar(papeis["proponente"].id, cancelado.id, motivo="Chuva")
    realizado = _publicado(papeis)
    eventos.realizar(papeis["aprovador"].id, realizado.id, data=timezone.localdate(), motivo="Antes")
    cliente = _cliente(papeis["comum"])

    do_cancelado = cliente.get(f"{BASE}{cancelado.id}/").json()["cancelamento"]
    do_realizado = cliente.get(f"{BASE}{realizado.id}/").json()["realizacao"]

    assert (do_cancelado["motivo"], do_cancelado["pelo_sistema"], do_cancelado["por"]["id"]) == (
        "Chuva",
        False,
        str(papeis["proponente"].id),
    )
    assert (do_realizado["data"], do_realizado["motivo"], do_realizado["por"]["id"]) == (
        timezone.localdate().isoformat(),
        "Antes",
        str(papeis["aprovador"].id),
    )


# --- comandos ---


def test_editar_reabrir_orcamento_presenca_realizar_e_cancelar_pelas_rotas(
    papeis: dict[str, Usuario],
) -> None:
    proponente = _cliente(papeis["proponente"])
    evento = _propor(papeis, envolve_custo=True)
    corpo = _corpo_da_proposta(envolve_custo=True, titulo="Amistoso ajustado")
    del corpo["envolve_custo"]

    sem_campo = proponente.post(f"{BASE}{evento.id}/editar/", corpo, format="json")
    assert _codigo(sem_campo) == (400, "VALIDATION_ERROR")
    editado = proponente.post(f"{BASE}{evento.id}/editar/", {**corpo, "envolve_custo": True}, format="json")
    assert (editado.status_code, editado.json()["titulo"]) == (200, "Amistoso ajustado")

    orcamento = {**itens_do_orcamento(), "categoria_id": "", "setor_id": ""}
    orcamento["categoria_id"] = str(itens_do_orcamento()["categoria_id"])
    orcamento["setor_id"] = str(itens_do_orcamento()["setor_id"])
    negado = proponente.post(f"{BASE}{evento.id}/orcamento/", orcamento, format="json")
    assert _codigo(negado) == (403, "PERMISSION_DENIED")
    aberto = _cliente(papeis["aprovador"]).post(f"{BASE}{evento.id}/orcamento/", orcamento, format="json")
    assert aberto.status_code == 201, aberto.content
    assert aberto.json()["orcamento"]["situacao"] == "EM_ANALISE"

    assert (
        decidir(papeis["aprovador"], recarregado(evento).id_da_solicitacao_do_evento, "recusar").status_code
        == 200
    )
    sem_justificativa = proponente.post(f"{BASE}{evento.id}/reabrir/", {"justificativa": ""}, format="json")
    assert _codigo(sem_justificativa) == (400, "VALIDATION_ERROR")
    reaberto = proponente.post(f"{BASE}{evento.id}/reabrir/", {"justificativa": "Novo local"}, format="json")
    assert (reaberto.status_code, reaberto.json()["situacao"]) == (200, "EM_APROVACAO")

    fora = _cliente(papeis["comum"]).post(f"{BASE}{evento.id}/presenca/", {"resposta": "VOU"}, format="json")
    assert _codigo(fora) == (422, "NAO_ESTA_PUBLICADO")
    nao_realiza = proponente.post(f"{BASE}{evento.id}/realizar/", {"motivo": "x"}, format="json")
    assert _codigo(nao_realiza) == (422, "NAO_ESTA_PUBLICADO")

    sem_motivo = proponente.post(f"{BASE}{evento.id}/cancelar/", {"motivo": ""}, format="json")
    assert _codigo(sem_motivo) == (400, "VALIDATION_ERROR")
    cancelado = proponente.post(f"{BASE}{evento.id}/cancelar/", {"motivo": "Desistimos"}, format="json")
    assert (cancelado.status_code, cancelado.json()["situacao"]) == (200, "CANCELADO")
    de_novo = proponente.post(f"{BASE}{evento.id}/cancelar/", {"motivo": "De novo"}, format="json")
    assert _codigo(de_novo) == (422, "EVENTO_ENCERRADO")


def test_realizar_pela_rota_com_data_e_motivo(papeis: dict[str, Usuario]) -> None:
    evento = _publicado(papeis)
    cliente = _cliente(papeis["proponente"])
    amanha = (timezone.localdate() + timedelta(days=1)).isoformat()

    futura = cliente.post(f"{BASE}{evento.id}/realizar/", {"data": amanha, "motivo": "x"}, format="json")
    assert _codigo(futura) == (422, "DATA_FUTURA")
    feito = cliente.post(f"{BASE}{evento.id}/realizar/", {"motivo": "Antecipado"}, format="json")
    assert (feito.status_code, feito.json()["situacao"]) == (200, "REALIZADO")


def test_presenca_pela_rota(papeis: dict[str, Usuario]) -> None:
    evento = _publicado(papeis)
    cliente = _cliente(papeis["comum"])

    invalida = cliente.post(f"{BASE}{evento.id}/presenca/", {"resposta": "TALVEZ"}, format="json")
    assert _codigo(invalida) == (400, "VALIDATION_ERROR")
    resposta = cliente.post(f"{BASE}{evento.id}/presenca/", {"resposta": "NAO_VOU"}, format="json")
    assert resposta.status_code == 200
    assert resposta.json()["minha"] == "NAO_VOU"


# --- paridade acoes ↔ rotas ---

_COMANDOS: dict[str, tuple[str, Any]] = {
    "editar": ("editar/", None),
    "reabrir": ("reabrir/", {"justificativa": "Reveja"}),
    "vincular_orcamento": ("orcamento/", None),
    "confirmar_realizacao": ("realizar/", {"motivo": "Antecipado"}),
    "cancelar": ("cancelar/", {"motivo": "Teste"}),
    "responder_presenca": ("presenca/", {"resposta": "VOU"}),
}


def _corpo(comando: str, evento: Evento) -> dict[str, Any]:
    corpo = _COMANDOS[comando][1]
    if comando == "editar":
        dados = _corpo_da_proposta(envolve_custo=evento.envolve_custo, titulo=evento.titulo)
        dados["categoria_id"] = str(evento.categoria_id)
        dados["justificativa"] = "Reveja"  # obrigatória quando a solicitação do evento está recusada
        return dados
    if comando == "vincular_orcamento":
        dados = itens_do_orcamento()
        return {**dados, "categoria_id": str(dados["categoria_id"]), "setor_id": str(dados["setor_id"])}
    return dict(corpo)


def _aceita(cliente: APIClient, evento: Evento, comando: str) -> bool:
    caminho = _COMANDOS[comando][0]
    with transaction.atomic():
        resposta = cliente.post(f"{BASE}{evento.id}/{caminho}", _corpo(comando, evento), format="json")
        transaction.set_rollback(True)
    return 200 <= resposta.status_code < 300


def test_paridade_entre_acoes_e_o_que_as_rotas_aceitam(papeis: dict[str, Usuario]) -> None:
    pode_cancelar = diretor("pode.cancelar", "eventos.cancelar")
    admin = apoio.criar_admin("admin.paridade")
    recusado = _propor(papeis, titulo="Recusado")
    assert decidir(papeis["aprovador"], recusado.id_da_solicitacao_do_evento, "recusar").status_code == 200
    cancelado = _propor(papeis, titulo="Cancelado")
    eventos.cancelar(papeis["proponente"].id, cancelado.id, motivo="Chuva")
    cenarios = [
        _propor(papeis, envolve_custo=True),
        _publicado(papeis),
        recarregado(recusado),
        recarregado(cancelado),
    ]

    for usuario in (papeis["proponente"], papeis["aprovador"], papeis["comum"], pode_cancelar, admin):
        cliente = _cliente(usuario)
        for evento in cenarios:
            acoes = cliente.get(f"{BASE}{evento.id}/").json()["acoes"]
            for comando in _COMANDOS:
                assert _aceita(cliente, evento, comando) is (comando in acoes), (
                    usuario.nome_de_usuario,
                    evento.titulo,
                    evento.situacao,
                    comando,
                )


# --- categorias (CA-01) ---


def test_ca01_admin_mantem_as_categorias_e_os_outros_sao_negados(papeis: dict[str, Usuario]) -> None:
    admin = _cliente(apoio.criar_admin("admin.categorias"))
    comum = _cliente(papeis["comum"])

    assert _codigo(comum.post(BASE + "categorias/", {"nome": "Treino"}, format="json")) == (
        403,
        "PERMISSION_DENIED",
    )
    criada = admin.post(BASE + "categorias/", {"nome": "Treino"}, format="json")
    assert criada.status_code == 201, criada.content
    categoria_id = criada.json()["id"]
    assert _codigo(admin.post(BASE + "categorias/", {"nome": "treino"}, format="json")) == (
        409,
        "CATEGORIA_JA_EXISTE",
    )
    assert _codigo(admin.post(BASE + "categorias/", {"nome": " "}, format="json")) == (
        400,
        "VALIDATION_ERROR",
    )

    renomeada = admin.post(
        f"{BASE}categorias/{categoria_id}/editar/", {"nome": "Treino aberto"}, format="json"
    )
    assert renomeada.json()["nome"] == "Treino aberto"
    assert admin.post(f"{BASE}categorias/{categoria_id}/desativar/").json()["ativa"] is False
    assert "Treino aberto" not in {c["nome"] for c in comum.get(BASE + "categorias/", {"todas": "1"}).json()}
    assert "Treino aberto" in {c["nome"] for c in admin.get(BASE + "categorias/", {"todas": "1"}).json()}
    assert admin.post(f"{BASE}categorias/{categoria_id}/reativar/").json()["ativa"] is True
    for acao in ("editar/", "desativar/", "reativar/"):
        assert (
            comum.post(f"{BASE}categorias/{categoria_id}/{acao}", {"nome": "x"}, format="json").status_code
            == 403
        )
    inexistente = admin.post(f"{BASE}categorias/{uuid.uuid4()}/desativar/")
    assert _codigo(inexistente) == (404, "NOT_FOUND")
