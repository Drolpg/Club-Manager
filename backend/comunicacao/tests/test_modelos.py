"""Modelos de `comunicacao`: constraints, únicos e gatilhos no banco (spec técnica do M9, "Modelo de dados").

Não há aggregate: as regras estão nos serviços. Aqui fica a segunda barreira, no banco: o que não se apaga e o
que não muda depois de gravado (CA-29).
"""

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from comunicacao.models import (
    CategoriaDeDocumento,
    Comentario,
    Comunicado,
    Documento,
    Imutavel,
    Reacao,
    VersaoDeComentario,
    VersaoDeComunicado,
    VersaoDeDocumento,
    VinculoDeDocumento,
)

pytestmark = pytest.mark.django_db

AUTOR = uuid.uuid4()
DIRETOR = uuid.uuid4()


def _categoria(nome: str | None = None) -> CategoriaDeDocumento:
    return CategoriaDeDocumento.objects.create(nome=nome or f"Categoria {uuid.uuid4().hex[:8]}")


def _comunicado(**campos: Any) -> Comunicado:
    base: dict[str, Any] = {
        "tipo": "COMUNICADO",
        "titulo": "Reunião",
        "texto": "Sábado, às 10h.",
        "autor_id": AUTOR,
        "publicado_em": timezone.now(),
    }
    base.update(campos)
    return Comunicado.objects.create(**base)


def _documento(**campos: Any) -> Documento:
    base: dict[str, Any] = {
        "tipo": "DOCUMENTO",
        "titulo": "Estatuto",
        "categoria": _categoria(),
        "categoria_nome": "Institucional",
        "enviado_por_id": AUTOR,
    }
    base.update(campos)
    return Documento.objects.create(**base)


def _versao_de_documento(documento: Documento, numero: int = 1, **campos: Any) -> VersaoDeDocumento:
    base: dict[str, Any] = {
        "documento": documento,
        "numero": numero,
        "chave": f"documentos/{uuid.uuid4()}.pdf",
        "nome": "estatuto.pdf",
        "mime": "application/pdf",
        "tamanho": 10,
        "motivo": "" if numero == 1 else "Correção",
        "enviada_por_id": AUTOR,
    }
    base.update(campos)
    return VersaoDeDocumento.objects.create(**base)


def _comentario(comunicado: Comunicado, **campos: Any) -> Comentario:
    base: dict[str, Any] = {"comunicado": comunicado, "autor_id": DIRETOR, "texto": "Ciente."}
    base.update(campos)
    return Comentario.objects.create(**base)


# --- constraints --------------------------------------------------------------------------------------------


def test_comunicado_fixado_so_se_publicado() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _comunicado(situacao="DESPUBLICADO", motivo_da_despublicacao="Duplicado", fixado_em=timezone.now())


def test_comunicado_despublicado_tem_motivo() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _comunicado(situacao="DESPUBLICADO")


def test_comunicado_com_tipo_ou_situacao_desconhecidos_e_recusado() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _comunicado(tipo="NOTICIA")
    with pytest.raises(IntegrityError), transaction.atomic():
        _comunicado(situacao="ARQUIVADO")


def test_comentario_ocultado_pela_gerencia_tem_motivo_e_esta_oculto() -> None:
    comunicado = _comunicado()

    with pytest.raises(IntegrityError), transaction.atomic():
        _comentario(comunicado, oculto_pela_gerencia=True, situacao="OCULTO")
    with pytest.raises(IntegrityError), transaction.atomic():
        _comentario(comunicado, oculto_pela_gerencia=True, motivo_da_ocultacao="Ofensivo")
    assert _comentario(
        comunicado, oculto_pela_gerencia=True, situacao="OCULTO", motivo_da_ocultacao="Ofensivo"
    ).pk


def test_ata_tem_data_e_nao_tem_categoria() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _documento(tipo="ATA")  # sem data e com categoria
    with pytest.raises(IntegrityError), transaction.atomic():
        _documento(tipo="ATA", categoria=None, categoria_nome="")  # sem data
    with pytest.raises(IntegrityError), transaction.atomic():
        _documento(tipo="ATA", data_da_reuniao=date(2026, 11, 20))  # com categoria
    assert _documento(tipo="ATA", categoria=None, categoria_nome="", data_da_reuniao=date(2026, 11, 20)).pk


def test_documento_comum_tem_categoria_e_nao_tem_data_da_reuniao() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _documento(categoria=None, categoria_nome="")
    with pytest.raises(IntegrityError), transaction.atomic():
        _documento(data_da_reuniao=date(2026, 11, 20))


def test_versao_de_documento_depois_da_primeira_exige_motivo() -> None:
    documento = _documento()
    _versao_de_documento(documento, 1)

    with pytest.raises(IntegrityError), transaction.atomic():
        _versao_de_documento(documento, 2, motivo="")
    assert _versao_de_documento(documento, 2).pk


# --- únicos -------------------------------------------------------------------------------------------------


def test_uma_reacao_por_diretor_e_comunicado() -> None:
    comunicado = _comunicado()
    Reacao.objects.create(comunicado=comunicado, diretor_id=DIRETOR, tipo="CIENTE")

    with pytest.raises(IntegrityError), transaction.atomic():
        Reacao.objects.create(comunicado=comunicado, diretor_id=DIRETOR, tipo="DUVIDA")
    assert Reacao.objects.create(comunicado=comunicado, diretor_id=uuid.uuid4(), tipo="DUVIDA").pk


def test_reacao_com_tipo_fora_do_conjunto_e_recusada() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Reacao.objects.create(comunicado=_comunicado(), diretor_id=DIRETOR, tipo="CURTIDA")


def test_numero_de_versao_e_unico_por_documento_comunicado_e_comentario() -> None:
    documento = _documento()
    _versao_de_documento(documento, 1)
    comunicado = _comunicado()
    VersaoDeComunicado.objects.create(
        comunicado=comunicado, numero=1, titulo="a", texto="b", autor_da_versao_id=AUTOR
    )
    comentario = _comentario(comunicado)
    VersaoDeComentario.objects.create(comentario=comentario, numero=1, texto="c")

    with pytest.raises(IntegrityError), transaction.atomic():
        _versao_de_documento(documento, 1)
    with pytest.raises(IntegrityError), transaction.atomic():
        VersaoDeComunicado.objects.create(
            comunicado=comunicado, numero=1, titulo="a", texto="b", autor_da_versao_id=AUTOR
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        VersaoDeComentario.objects.create(comentario=comentario, numero=1, texto="c")


def test_nome_da_categoria_e_unico_sem_diferenciar_maiusculas() -> None:
    _categoria("Jurídico")

    with pytest.raises(IntegrityError), transaction.atomic():
        _categoria("JURÍDICO")


def test_so_um_vinculo_ativo_por_comunicado_e_documento_mas_pode_revincular() -> None:
    comunicado = _comunicado()
    documento = _documento()
    vinculo = VinculoDeDocumento.objects.create(comunicado=comunicado, documento=documento)

    with pytest.raises(IntegrityError), transaction.atomic():
        VinculoDeDocumento.objects.create(comunicado=comunicado, documento=documento)

    vinculo.desvinculado_em = timezone.now()
    vinculo.save(update_fields=["desvinculado_em"])
    assert VinculoDeDocumento.objects.create(comunicado=comunicado, documento=documento).pk


# --- nada é apagado -----------------------------------------------------------------------------------------


def _cenario() -> dict[str, Any]:
    comunicado = _comunicado()
    documento = _documento()
    comentario = _comentario(comunicado)
    return {
        "categoria": documento.categoria,
        "comunicado": comunicado,
        "versao_de_comunicado": VersaoDeComunicado.objects.create(
            comunicado=comunicado, numero=1, titulo="a", texto="b", autor_da_versao_id=AUTOR
        ),
        "vinculo": VinculoDeDocumento.objects.create(comunicado=comunicado, documento=documento),
        "reacao": Reacao.objects.create(comunicado=comunicado, diretor_id=DIRETOR, tipo="CIENTE"),
        "comentario": comentario,
        "versao_de_comentario": VersaoDeComentario.objects.create(comentario=comentario, numero=1, texto="c"),
        "documento": documento,
        "versao_de_documento": _versao_de_documento(documento, 1),
    }


@pytest.mark.parametrize(
    "chave",
    [
        "categoria",
        "comunicado",
        "versao_de_comunicado",
        "vinculo",
        "reacao",
        "comentario",
        "versao_de_comentario",
        "documento",
        "versao_de_documento",
    ],
)
def test_os_modelos_recusam_exclusao_pelo_metodo(chave: str) -> None:
    objeto = _cenario()[chave]

    with pytest.raises(Imutavel):
        objeto.delete()


@pytest.mark.parametrize(
    "chave",
    [
        "categoria",
        "comunicado",
        "versao_de_comunicado",
        "vinculo",
        "reacao",
        "comentario",
        "versao_de_comentario",
        "documento",
        "versao_de_documento",
    ],
)
def test_o_banco_recusa_exclusao_por_sql_direto(chave: str) -> None:
    objeto = _cenario()[chave]
    tabela = objeto._meta.db_table

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {tabela} WHERE id = %s", [objeto.pk])  # noqa: S608

    assert type(objeto).objects.filter(pk=objeto.pk).exists()


@pytest.mark.parametrize(
    ("chave", "coluna", "valor"),
    [
        ("versao_de_comunicado", "texto", "adulterado"),
        ("versao_de_comentario", "texto", "adulterado"),
        ("versao_de_documento", "chave", "documentos/outra.pdf"),
    ],
)
def test_o_banco_recusa_alterar_uma_versao(chave: str, coluna: str, valor: str) -> None:
    objeto = _cenario()[chave]
    tabela = objeto._meta.db_table

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"UPDATE {tabela} SET {coluna} = %s WHERE id = %s", [valor, objeto.pk])  # noqa: S608


def test_o_banco_permite_alterar_o_que_nao_e_versao() -> None:
    comunicado = _cenario()["comunicado"]

    comunicado.titulo = "Novo título"
    comunicado.save(update_fields=["titulo"])

    comunicado.refresh_from_db()
    assert comunicado.titulo == "Novo título"


def test_o_queryset_tambem_nao_apaga_porque_o_banco_recusa() -> None:
    _comunicado()
    apagar: Callable[[], Any] = Comunicado.objects.all().delete

    with pytest.raises((DatabaseError, Imutavel)), transaction.atomic():
        apagar()

    assert Comunicado.objects.exists()
