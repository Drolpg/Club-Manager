"""CA-06: duas decisões simultâneas sobre a mesma versão; só uma vale.

Cada thread tem a própria conexão e a própria transação (`transaction=True`). O resultado esperado não depende
da ordem em que o banco atende as duas: se correrem juntas, a segunda espera o bloqueio da linha e encontra a
solicitação fora de análise; se correrem em série, a segunda também. Por isso o teste não depende de tempo.
Os dados são criados aqui: um teste transacional anterior pode ter esvaziado os motivos semeados.
"""

import threading
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.db import connection

from aprovacoes import public
from aprovacoes.models import Decisao, MotivoDeDecisao, Solicitacao
from aprovacoes.services import decisoes
from aprovacoes.tests.conftest import APROVAR_TESTE, TIPO, TipoDeTeste, com_cargo, pedido
from kernel.errors import BusinessError

_ESPERA = 30


def _motivo(tipo_de_decisao: str) -> uuid.UUID:
    motivo, _ = MotivoDeDecisao.objects.get_or_create(
        tipo_de_decisao=tipo_de_decisao, texto=f"Motivo de concorrência {tipo_de_decisao}"
    )
    return motivo.id


@pytest.mark.django_db(transaction=True)
def test_ca06_duas_decisoes_simultaneas_so_uma_vale(tipo_de_teste: TipoDeTeste) -> None:
    solicitante = com_cargo("caio")
    primeiro = com_cargo("dora", APROVAR_TESTE)
    segundo = com_cargo("eva", APROVAR_TESTE)
    solicitacao_id = public.enviar(tipo=TIPO, conteudo=pedido(), solicitante_id=solicitante.id)
    pedidos: list[tuple[Callable[..., Any], uuid.UUID, uuid.UUID]] = [
        (decisoes.aprovar, primeiro.id, _motivo("solicitacao.aprovar")),
        (decisoes.recusar, segundo.id, _motivo("solicitacao.recusar")),
    ]
    barreira = threading.Barrier(len(pedidos))
    resultados: list[str] = []
    trava = threading.Lock()

    def decidir(comando: Callable[..., Any], ator_id: uuid.UUID, motivo_id: uuid.UUID) -> None:
        try:
            barreira.wait(timeout=_ESPERA)
            comando(ator_id=ator_id, solicitacao_id=solicitacao_id, motivo_id=motivo_id)
            resultado = "sucesso"
        except BusinessError as erro:
            resultado = erro.code
        finally:
            connection.close()
        with trava:
            resultados.append(resultado)

    threads = [threading.Thread(target=decidir, args=pedido_) for pedido_ in pedidos]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=_ESPERA)

    assert not any(thread.is_alive() for thread in threads)
    assert sorted(resultados) == ["NAO_ESTA_EM_ANALISE", "sucesso"]
    assert Decisao.objects.filter(versao__solicitacao_id=solicitacao_id).count() == 1
    assert Solicitacao.objects.get(pk=solicitacao_id).situacao in ("APROVADA", "RECUSADA")
