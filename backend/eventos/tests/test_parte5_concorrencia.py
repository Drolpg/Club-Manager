"""Parte 5: comandos simultâneos sobre o mesmo evento, cada um na própria conexão (`transaction=True`).

O que se exige é o estado final coerente, qualquer que seja a ordem em que o banco atende. Cancelar e decidir
ao mesmo tempo podem dar impasse de bloqueio: o banco desfaz uma das duas (risco aceito, decisão Q3 do dono).
Os dados são criados aqui: um teste transacional anterior pode ter esvaziado os dados semeados.
"""

import threading
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.db import DatabaseError, connection

from aprovacoes import public as aprovacoes
from eventos.models import CategoriaDeEvento, Evento, Presenca
from eventos.services import eventos, presencas
from eventos.tests.conftest import daqui_a, diretor
from kernel.errors import BusinessError
from tests import apoio

pytestmark = pytest.mark.django_db(transaction=True)

_ESPERA = 30


def _em_paralelo(*tarefas: Callable[[], Any]) -> list[str]:
    barreira = threading.Barrier(len(tarefas))
    resultados: list[str] = []
    trava = threading.Lock()

    def rodar(tarefa: Callable[[], Any]) -> None:
        try:
            barreira.wait(timeout=_ESPERA)
            tarefa()
            resultado = "sucesso"
        except BusinessError as erro:
            resultado = erro.code
        except DatabaseError:
            resultado = "IMPASSE"
        finally:
            connection.close()
        with trava:
            resultados.append(resultado)

    threads = [threading.Thread(target=rodar, args=(tarefa,)) for tarefa in tarefas]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=_ESPERA)
    assert not any(thread.is_alive() for thread in threads)
    return sorted(resultados)


def _categoria() -> uuid.UUID:
    categoria, _ = CategoriaDeEvento.objects.get_or_create(nome="Jogo")
    return categoria.id


def _evento(proponente_id: uuid.UUID, *, envolve_custo: bool = False) -> Evento:
    return eventos.propor(
        proponente_id,
        titulo="Amistoso",
        descricao="",
        inicio=daqui_a(),
        local="Campo",
        categoria_id=_categoria(),
        envolve_custo=envolve_custo,
    )


def _motivo_de_aprovar() -> str:
    admin = apoio.criar_admin("admin.concorrencia")
    resposta = apoio.cliente_de(admin).post(
        "/api/v1/aprovacoes/motivos/",
        {"tipo_de_decisao": "solicitacao.aprovar", "texto": f"Concorrência {uuid.uuid4().hex[:6]}"},
        format="json",
    )
    assert resposta.status_code == 201, resposta.content
    return str(resposta.json()["id"])


def test_cancelar_e_aprovar_ao_mesmo_tempo_terminam_coerentes() -> None:
    proponente = diretor("prop", "eventos.propor")
    aprovador = diretor("resp", "eventos.aprovar")
    evento = _evento(proponente.id)
    motivo = _motivo_de_aprovar()
    solicitacao_id = evento.id_da_solicitacao_do_evento

    def aprovar() -> None:
        resposta = apoio.cliente_de(aprovador).post(
            f"/api/v1/aprovacoes/solicitacoes/{solicitacao_id}/aprovar/",
            {"motivo_id": motivo, "texto": ""},
            format="json",
        )
        if resposta.status_code != 200:
            raise BusinessError(resposta.json()["error"]["code"], "recusada", status=resposta.status_code)

    resultados = _em_paralelo(
        lambda: eventos.cancelar(proponente.id, evento.id, motivo="Chuva"),
        aprovar,
    )

    final = Evento.objects.get(pk=evento.pk)
    solicitacao = aprovacoes.situacao_de(solicitacao_id)
    assert (final.situacao, solicitacao) in {
        ("CANCELADO", aprovacoes.Situacao.CANCELADA),
        ("PUBLICADO", aprovacoes.Situacao.APROVADA),
    }, resultados
    assert "sucesso" in resultados


def test_duas_respostas_de_presenca_simultaneas_do_mesmo_diretor_deixam_uma() -> None:
    proponente = diretor("prop", "eventos.propor")
    aprovador = diretor("resp", "eventos.aprovar")
    comum = diretor("comum")
    evento = _evento(proponente.id)
    motivo = _motivo_de_aprovar()
    resposta = apoio.cliente_de(aprovador).post(
        f"/api/v1/aprovacoes/solicitacoes/{evento.id_da_solicitacao_do_evento}/aprovar/",
        {"motivo_id": motivo, "texto": ""},
        format="json",
    )
    assert resposta.status_code == 200, resposta.content

    resultados = _em_paralelo(
        lambda: presencas.responder(comum.id, evento.id, "VOU"),
        lambda: presencas.responder(comum.id, evento.id, "NAO_VOU"),
    )

    assert resultados == ["sucesso", "sucesso"]
    assert Presenca.objects.filter(evento=evento, diretor_id=comum.id).count() == 1


def test_dois_orcamentos_simultaneos_deixam_um_so() -> None:
    proponente = diretor("prop", "eventos.propor")
    aprovador = diretor("resp", "eventos.aprovar")
    evento = _evento(proponente.id, envolve_custo=True)
    admin = apoio.cliente_de(apoio.criar_admin("admin.orcamento"))
    criada = admin.post(
        "/api/v1/financeiro/categorias/",
        {"nome": f"Saída {uuid.uuid4().hex[:6]}", "natureza": "SAIDA"},
        format="json",
    )
    assert criada.status_code == 201, criada.content
    setores = admin.get("/api/v1/permissoes/setores/").json()
    if not setores:
        setores = [admin.post("/api/v1/permissoes/setores/", {"nome": "Eventos"}, format="json").json()]
    dados: dict[str, Any] = {
        "descricao": "Orçamento",
        "categoria_id": uuid.UUID(criada.json()["id"]),
        "setor_id": uuid.UUID(setores[0]["id"]),
        "itens": [{"descricao": "Arbitragem", "valor": "100.00"}],
    }

    resultados = _em_paralelo(
        lambda: eventos.abrir_orcamento(aprovador.id, evento.id, **dados),
        lambda: eventos.abrir_orcamento(aprovador.id, evento.id, **dados),
    )

    assert resultados == ["ORCAMENTO_JA_VINCULADO", "sucesso"]
    assert Evento.objects.get(pk=evento.pk).solicitacao_orcamentaria_id is not None
