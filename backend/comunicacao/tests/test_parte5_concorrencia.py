"""Comandos simultâneos sobre o mesmo item, cada um na própria conexão (`transaction=True`).

O que se exige é o estado final coerente, qualquer que seja a ordem em que o banco atende: o bloqueio da linha
do comunicado, do comentário e do documento serializa os comandos. Os dados são criados aqui, porque um teste
transacional anterior pode ter esvaziado os dados semeados.
"""

import threading
import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection

from comunicacao.domain.autorizacao import (
    PERM_ENVIAR_DOCUMENTOS,
    PERM_GERENCIAR,
    PERM_PUBLICAR,
)
from comunicacao.models import (
    CategoriaDeDocumento,
    Comentario,
    Comunicado,
    Documento,
    Reacao,
    VersaoDeComunicado,
    VersaoDeDocumento,
)
from comunicacao.services import comentarios, comunicados, documentos, reacoes
from comunicacao.tests.conftest import diretor
from kernel.errors import BusinessError

pytestmark = pytest.mark.django_db(transaction=True)

_ESPERA = 30
_PDF = b"%PDF-1.4\nconcorrencia\n"


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


def _arquivo() -> Any:
    return SimpleUploadedFile("a.pdf", _PDF, content_type="application/pdf")


def _comunicado(autor_id: uuid.UUID) -> Comunicado:
    return comunicados.publicar(autor_id, tipo="COMUNICADO", titulo="Aviso", texto="Texto", documentos_ids=[])


def test_duas_edicoes_do_mesmo_comunicado_se_serializam_e_deixam_as_duas_versoes() -> None:
    autor = diretor("conc.autor", PERM_PUBLICAR)
    comunicado = _comunicado(autor.id)

    resultados = _em_paralelo(
        lambda: comunicados.editar(autor.id, comunicado.id, titulo="A", texto="texto A", documentos_ids=[]),
        lambda: comunicados.editar(autor.id, comunicado.id, titulo="B", texto="texto B", documentos_ids=[]),
    )

    assert resultados == ["sucesso", "sucesso"]
    final = Comunicado.objects.get(pk=comunicado.pk)
    numeros = list(VersaoDeComunicado.objects.filter(comunicado=final).values_list("numero", flat=True))
    assert final.versao == 3
    assert sorted(numeros) == [1, 2, 3]
    ultima = VersaoDeComunicado.objects.get(comunicado=final, numero=3)
    assert (final.titulo, final.texto) == (ultima.titulo, ultima.texto)


def test_duas_versoes_do_mesmo_documento_ganham_numeros_seguidos_sem_duplicar() -> None:
    envia = diretor("conc.envia", PERM_ENVIAR_DOCUMENTOS)
    categoria, _ = CategoriaDeDocumento.objects.get_or_create(nome="Concorrência")
    documento = documentos.enviar_documento(
        envia.id, titulo="Estatuto", descricao="", categoria_id=categoria.id, arquivo=_arquivo()
    )

    resultados = _em_paralelo(
        lambda: documentos.nova_versao(envia.id, documento.id, arquivo=_arquivo(), motivo="Primeira"),
        lambda: documentos.nova_versao(envia.id, documento.id, arquivo=_arquivo(), motivo="Segunda"),
    )

    assert resultados == ["sucesso", "sucesso"]
    numeros = sorted(VersaoDeDocumento.objects.filter(documento=documento).values_list("numero", flat=True))
    assert numeros == [1, 2, 3]
    assert Documento.objects.get(pk=documento.pk).versao_atual == 3


def test_duas_reacoes_do_mesmo_diretor_deixam_uma_so() -> None:
    autor = diretor("conc.autor2", PERM_PUBLICAR)
    leitor = diretor("conc.leitor")
    comunicado = _comunicado(autor.id)

    resultados = _em_paralelo(
        lambda: reacoes.reagir(leitor.id, comunicado.id, "CIENTE"),
        lambda: reacoes.reagir(leitor.id, comunicado.id, "DUVIDA"),
    )

    assert resultados == ["sucesso", "sucesso"]
    linhas = Reacao.objects.filter(comunicado=comunicado, diretor_id=leitor.id)
    assert linhas.count() == 1
    assert linhas.get().retirada_em is None


def test_dois_ocultamentos_do_mesmo_comentario_um_vale_e_o_outro_e_recusado() -> None:
    autor = diretor("conc.autor3", PERM_PUBLICAR)
    leitor = diretor("conc.leitor2")
    gerente = diretor("conc.gerente", PERM_GERENCIAR)
    comunicado = _comunicado(autor.id)
    comentario = comentarios.comentar(leitor.id, comunicado.id, "oi")

    resultados = _em_paralelo(
        lambda: comentarios.ocultar(gerente.id, comentario.id, "Motivo um"),
        lambda: comentarios.ocultar(gerente.id, comentario.id, "Motivo dois"),
    )

    assert resultados == ["COMENTARIO_JA_OCULTO", "sucesso"]
    final = Comentario.objects.get(pk=comentario.pk)
    assert final.situacao == "OCULTO"
    assert final.motivo_da_ocultacao in {"Motivo um", "Motivo dois"}


def test_duas_despublicacoes_do_mesmo_comunicado_uma_vale_e_a_outra_e_recusada() -> None:
    autor = diretor("conc.autor4", PERM_PUBLICAR)
    comunicado = _comunicado(autor.id)

    resultados = _em_paralelo(
        lambda: comunicados.despublicar(autor.id, comunicado.id, motivo="Erro um"),
        lambda: comunicados.despublicar(autor.id, comunicado.id, motivo="Erro dois"),
    )

    assert resultados == ["COMUNICADO_JA_DESPUBLICADO", "sucesso"]


def test_a_data_da_ata_e_a_do_envio_mesmo_com_versoes_simultaneas() -> None:
    atas = diretor("conc.atas", "comunicacao.registrar_atas")
    ata = documentos.registrar_ata(
        atas.id, titulo="Ata", descricao="", data_da_reuniao=date(2026, 10, 30), arquivo=_arquivo()
    )

    _em_paralelo(
        lambda: documentos.nova_versao(atas.id, ata.id, arquivo=_arquivo(), motivo="Um"),
        lambda: documentos.nova_versao(atas.id, ata.id, arquivo=_arquivo(), motivo="Dois"),
    )

    assert Documento.objects.get(pk=ata.pk).data_da_reuniao == date(2026, 10, 30)
