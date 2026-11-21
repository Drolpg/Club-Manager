"""Documentos e atas: enviar, registrar a ata, nova versão, arquivar e a leitura (CA-21 a CA-26).

Banco real e armazenamento em memória (`settings_test`). A auditoria leva a referência do arquivo, nunca o
conteúdo.
"""

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from comunicacao.domain.autorizacao import PERM_ENVIAR_DOCUMENTOS
from comunicacao.models import CategoriaDeDocumento, Documento, VersaoDeDocumento, VinculoDeDocumento
from comunicacao.services import comunicados, consulta, documentos
from comunicacao.tests.conftest import acoes_de, categoria, diretor, registros_de
from kernel.errors import BusinessError
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8


def _arquivo(nome: str = "estatuto.pdf", conteudo: bytes = PDF, tipo: str = "application/pdf") -> Any:
    return SimpleUploadedFile(nome, conteudo, content_type=tipo)


def _enviar(papeis: dict[str, Usuario], quem: str = "envia", **mudar: Any) -> Documento:
    dados: dict[str, Any] = {
        "titulo": "Estatuto",
        "descricao": "Versão registrada em cartório.",
        "categoria_id": categoria().id,
        "arquivo": _arquivo(),
    }
    dados.update(mudar)
    return documentos.enviar_documento(papeis[quem].id, **dados)


def _ata(papeis: dict[str, Usuario], quem: str = "atas", **mudar: Any) -> Documento:
    dados: dict[str, Any] = {
        "titulo": "Ata de outubro",
        "descricao": "",
        "data_da_reuniao": date(2026, 10, 30),
        "arquivo": _arquivo("ata.pdf"),
    }
    dados.update(mudar)
    return documentos.registrar_ata(papeis[quem].id, **dados)


def _codigo(excecao: pytest.ExceptionInfo[BusinessError]) -> str:
    return excecao.value.code


# --- enviar documento (CA-21) ---------------------------------------------------------------------------


def test_ca21_envia_documento_com_a_versao_1(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    assert documento.tipo == "DOCUMENTO"
    assert documento.situacao == "VIGENTE"
    assert documento.versao_atual == 1
    assert documento.categoria_nome == "Institucional"
    assert documento.enviado_por_id == papeis["envia"].id
    versao = VersaoDeDocumento.objects.get(documento=documento)
    assert (versao.numero, versao.mime, versao.nome) == (1, "application/pdf", "estatuto.pdf")
    assert versao.chave.startswith("documentos/")
    assert default_storage.exists(versao.chave)


@pytest.mark.parametrize(
    ("nome", "conteudo", "tipo", "mime"),
    [
        ("a.pdf", PDF, "application/pdf", "application/pdf"),
        ("a.png", PNG, "image/png", "image/png"),
        ("a.jpg", JPEG, "image/jpeg", "image/jpeg"),
        ("a.webp", WEBP, "image/webp", "image/webp"),
    ],
)
def test_ca21_aceita_pdf_png_jpeg_e_webp(
    papeis: dict[str, Usuario], nome: str, conteudo: bytes, tipo: str, mime: str
) -> None:
    documento = _enviar(papeis, arquivo=_arquivo(nome, conteudo, tipo))

    assert VersaoDeDocumento.objects.get(documento=documento).mime == mime


def test_ca21_a_auditoria_leva_a_referencia_e_nunca_o_conteudo(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    (registro,) = registros_de("documento", documento.id, "DOCUMENTO_ENVIADO")
    versao = VersaoDeDocumento.objects.get(documento=documento)
    assert registro.dados["chave"] == versao.chave
    assert registro.dados["mime"] == "application/pdf"
    assert registro.dados["tamanho"] == versao.tamanho
    assert "%PDF" not in str(registro.dados)
    assert "Versão registrada" not in str(registro.dados)


def test_ca21_arquivo_de_tipo_nao_aceito_e_recusado_com_o_campo_arquivo(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        _enviar(papeis, arquivo=_arquivo("nota.txt", b"texto puro", "text/plain"))

    assert _codigo(erro) == "VALIDATION_ERROR"
    assert "arquivo" in erro.value.details
    assert Documento.objects.count() == 0


def test_ca21_arquivo_vazio_e_recusado(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        _enviar(papeis, arquivo=_arquivo("vazio.pdf", b""))

    assert "arquivo" in erro.value.details


def test_ca21_acima_de_5_mb_e_recusado_com_texto_de_documento(papeis: dict[str, Usuario]) -> None:
    grande = _arquivo("grande.pdf", PDF + b"0" * (5 * 1024 * 1024))

    with pytest.raises(BusinessError) as erro:
        _enviar(papeis, arquivo=grande)

    assert erro.value.details == {"arquivo": ["O documento excede o limite de 5 MB."]}


def test_ca21_sem_arquivo_e_recusado(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        _enviar(papeis, arquivo=None)

    assert erro.value.details == {"arquivo": ["Envie um arquivo de documento válido."]}


@pytest.mark.parametrize("quem", ["leitor", "autor", "atas", "sem_cargo"])
def test_ca21_sem_a_permissao_de_enviar_e_negado(papeis: dict[str, Usuario], quem: str) -> None:
    with pytest.raises(BusinessError) as erro:
        _enviar(papeis, quem=quem)

    assert _codigo(erro) == "PERMISSION_DENIED"
    assert Documento.objects.count() == 0


def test_ca21_o_admin_envia(papeis: dict[str, Usuario]) -> None:
    assert _enviar(papeis, quem="admin").enviado_por_id == papeis["admin"].id


def test_ca21_titulo_em_branco_e_descricao_longa_sao_recusados(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        _enviar(papeis, titulo="  ", descricao="x" * 1001)

    assert set(erro.value.details) == {"titulo", "descricao"}


def test_ca21_categoria_inativa_e_recusada_e_inexistente_e_invalida(papeis: dict[str, Usuario]) -> None:
    inativa = categoria("Outros")
    inativa.ativa = False
    inativa.save()

    with pytest.raises(BusinessError) as erro:
        _enviar(papeis, categoria_id=inativa.id)
    with pytest.raises(BusinessError) as outro:
        _enviar(papeis, categoria_id=uuid.uuid4())

    assert _codigo(erro) == "CATEGORIA_INATIVA"
    assert _codigo(outro) == "VALIDATION_ERROR"
    assert "categoria_id" in outro.value.details
    assert Documento.objects.count() == 0


def test_ca21_o_texto_e_guardado_como_veio(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis, titulo="<b>Estatuto</b>", descricao="<script>x</script>")

    documento.refresh_from_db()
    assert (documento.titulo, documento.descricao) == ("<b>Estatuto</b>", "<script>x</script>")


# --- ata (CA-22) ----------------------------------------------------------------------------------------


def test_ca22_registra_ata_com_data_e_sem_categoria(papeis: dict[str, Usuario]) -> None:
    ata = _ata(papeis)

    assert ata.tipo == "ATA"
    assert ata.categoria_id is None
    assert ata.data_da_reuniao == date(2026, 10, 30)
    assert acoes_de("documento", ata.id) == ["ATA_REGISTRADA"]


def test_ca22_a_ata_de_hoje_vale_e_a_futura_e_recusada(papeis: dict[str, Usuario]) -> None:
    hoje = timezone.localdate()

    assert _ata(papeis, data_da_reuniao=hoje).data_da_reuniao == hoje
    with pytest.raises(BusinessError) as erro:
        _ata(papeis, data_da_reuniao=hoje + timedelta(days=1))

    assert _codigo(erro) == "DATA_FUTURA"


def test_ca22_ata_sem_data_e_recusada(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        _ata(papeis, data_da_reuniao=None)

    assert _codigo(erro) == "VALIDATION_ERROR"
    assert "data_da_reuniao" in erro.value.details


@pytest.mark.parametrize("quem", ["envia", "leitor", "autor", "sem_cargo"])
def test_ca22_so_a_permissao_de_atas_registra(papeis: dict[str, Usuario], quem: str) -> None:
    with pytest.raises(BusinessError) as erro:
        _ata(papeis, quem=quem)

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ca22_quem_so_registra_atas_nao_envia_documento_comum(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        _enviar(papeis, quem="atas")

    assert _codigo(erro) == "PERMISSION_DENIED"


# --- nova versão (CA-24) --------------------------------------------------------------------------------


def test_ca24_nova_versao_vira_a_vigente_e_a_anterior_fica(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)
    primeira = VersaoDeDocumento.objects.get(documento=documento, numero=1)

    documentos.nova_versao(
        papeis["envia"].id, documento.id, arquivo=_arquivo("v2.png", PNG, "image/png"), motivo="Correção"
    )

    documento.refresh_from_db()
    assert documento.versao_atual == 2
    segunda = VersaoDeDocumento.objects.get(documento=documento, numero=2)
    assert (segunda.motivo, segunda.mime) == ("Correção", "image/png")
    assert VersaoDeDocumento.objects.get(pk=primeira.pk).chave == primeira.chave
    assert default_storage.exists(primeira.chave)
    assert default_storage.exists(segunda.chave)
    assert acoes_de("documento", documento.id) == ["DOCUMENTO_ENVIADO", "VERSAO_ENVIADA"]


def test_ca24_a_versao_sem_motivo_e_recusada(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    with pytest.raises(BusinessError) as erro:
        documentos.nova_versao(papeis["envia"].id, documento.id, arquivo=_arquivo(), motivo=" ")

    assert _codigo(erro) == "VALIDATION_ERROR"
    assert "motivo" in erro.value.details
    assert VersaoDeDocumento.objects.filter(documento=documento).count() == 1


def test_ca24_arquivo_invalido_na_nova_versao_nao_muda_nada(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    with pytest.raises(BusinessError) as erro:
        documentos.nova_versao(
            papeis["envia"].id, documento.id, arquivo=_arquivo("x.txt", b"abc", "text/plain"), motivo="m"
        )

    assert "arquivo" in erro.value.details
    documento.refresh_from_db()
    assert documento.versao_atual == 1


def test_ca24_a_auditoria_da_versao_leva_so_a_referencia(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    documentos.nova_versao(papeis["envia"].id, documento.id, arquivo=_arquivo(), motivo="Motivo secreto?")

    (registro,) = registros_de("documento", documento.id, "VERSAO_ENVIADA")
    assert registro.dados["versao"] == 2
    assert "chave" in registro.dados
    assert registro.justificativa == "Motivo secreto?"


@pytest.mark.parametrize("quem", ["leitor", "autor", "atas", "sem_cargo", "outro_que_envia"])
def test_ca24_terceiro_sem_gerenciar_e_negado(papeis: dict[str, Usuario], quem: str) -> None:
    documento = _enviar(papeis)
    papeis["outro_que_envia"] = diretor("envia.outro", PERM_ENVIAR_DOCUMENTOS)

    with pytest.raises(BusinessError) as erro:
        documentos.nova_versao(papeis[quem].id, documento.id, arquivo=_arquivo(), motivo="m")

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ca24_quem_gerencia_e_o_admin_podem_enviar_versao_de_outro(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    documentos.nova_versao(papeis["gerente"].id, documento.id, arquivo=_arquivo(), motivo="Gerência")
    documentos.nova_versao(papeis["admin"].id, documento.id, arquivo=_arquivo(), motivo="Admin")

    documento.refresh_from_db()
    assert documento.versao_atual == 3


def test_ca24_quem_enviou_e_perdeu_a_permissao_do_tipo_nao_envia_versao(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)
    Documento.objects.filter(pk=documento.pk).update(enviado_por_id=papeis["leitor"].id)

    with pytest.raises(BusinessError) as erro:
        documentos.nova_versao(papeis["leitor"].id, documento.id, arquivo=_arquivo(), motivo="m")

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ca24_documento_arquivado_recusa_nova_versao(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)
    documentos.arquivar(papeis["envia"].id, documento.id)

    with pytest.raises(BusinessError) as erro:
        documentos.nova_versao(papeis["envia"].id, documento.id, arquivo=_arquivo(), motivo="m")

    assert _codigo(erro) == "DOCUMENTO_ARQUIVADO"


def test_ca24_a_data_da_ata_nao_muda_na_nova_versao(papeis: dict[str, Usuario]) -> None:
    ata = _ata(papeis)

    documentos.nova_versao(papeis["atas"].id, ata.id, arquivo=_arquivo("ata2.pdf"), motivo="Assinada")

    ata.refresh_from_db()
    assert ata.data_da_reuniao == date(2026, 10, 30)
    assert ata.versao_atual == 2


def test_ca24_documento_inexistente_e_404(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        documentos.nova_versao(papeis["envia"].id, uuid.uuid4(), arquivo=_arquivo(), motivo="m")

    assert _codigo(erro) == "NOT_FOUND"


def test_a_leitura_de_gestao_vem_antes_da_existencia(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        documentos.nova_versao(papeis["sem_cargo"].id, uuid.uuid4(), arquivo=_arquivo(), motivo="m")

    assert _codigo(erro) == "PERMISSION_DENIED"


# --- o comunicado que indexa o documento (CA-25) --------------------------------------------------------


def test_ca25_o_comunicado_continua_apontando_para_o_documento_na_nova_versao(
    papeis: dict[str, Usuario],
) -> None:
    documento = _enviar(papeis)
    comunicado = comunicados.publicar(
        papeis["autor"].id, tipo="COMUNICADO", titulo="t", texto="x", documentos_ids=[documento.id]
    )
    vinculo = VinculoDeDocumento.objects.get(comunicado=comunicado, documento=documento)

    documentos.nova_versao(papeis["envia"].id, documento.id, arquivo=_arquivo(), motivo="Atualizado")

    vinculo.refresh_from_db()
    assert vinculo.desvinculado_em is None
    detalhe = consulta.detalhe_do_documento(papeis["leitor"].id, documento.id)
    assert detalhe["versao_atual"] == 2
    assert [c["id"] for c in detalhe["comunicados"]] == [comunicado.id]
    assert [(v["numero"], v["situacao"]) for v in detalhe["versoes"]] == [
        (1, "SUBSTITUIDA"),
        (2, "VIGENTE"),
    ]


def test_ca25_so_os_comunicados_publicados_aparecem_no_detalhe_do_documento(
    papeis: dict[str, Usuario],
) -> None:
    documento = _enviar(papeis)
    comunicado = comunicados.publicar(
        papeis["autor"].id, tipo="COMUNICADO", titulo="t", texto="x", documentos_ids=[documento.id]
    )
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    detalhe = consulta.detalhe_do_documento(papeis["leitor"].id, documento.id)

    assert detalhe["comunicados"] == []


# --- arquivar e desarquivar (CA-26) ---------------------------------------------------------------------


def test_ca26_arquiva_e_desarquiva_sem_apagar(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    documentos.arquivar(papeis["envia"].id, documento.id)
    documento.refresh_from_db()
    assert documento.situacao == "ARQUIVADO"

    documentos.desarquivar(papeis["envia"].id, documento.id)
    documento.refresh_from_db()
    assert documento.situacao == "VIGENTE"
    assert acoes_de("documento", documento.id) == [
        "DOCUMENTO_ENVIADO",
        "DOCUMENTO_ARQUIVADO",
        "DOCUMENTO_DESARQUIVADO",
    ]


def test_ca26_o_arquivado_continua_vinculado_e_na_leitura(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)
    comunicado = comunicados.publicar(
        papeis["autor"].id, tipo="COMUNICADO", titulo="t", texto="x", documentos_ids=[documento.id]
    )

    documentos.arquivar(papeis["envia"].id, documento.id)

    vinculo = VinculoDeDocumento.objects.get(comunicado=comunicado, documento=documento)
    assert vinculo.desvinculado_em is None
    item = consulta.detalhe(papeis["leitor"].id, comunicado.id)["documentos"][0]
    assert item["situacao"] == "ARQUIVADO"
    assert consulta.detalhe_do_documento(papeis["leitor"].id, documento.id)["situacao"] == "ARQUIVADO"


def test_ca26_arquivar_de_novo_e_desarquivar_o_vigente_sao_recusados(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    with pytest.raises(BusinessError) as sem_arquivo:
        documentos.desarquivar(papeis["envia"].id, documento.id)
    documentos.arquivar(papeis["envia"].id, documento.id)
    with pytest.raises(BusinessError) as repetido:
        documentos.arquivar(papeis["envia"].id, documento.id)

    assert _codigo(sem_arquivo) == "DOCUMENTO_NAO_ESTA_ARQUIVADO"
    assert _codigo(repetido) == "DOCUMENTO_JA_ARQUIVADO"


@pytest.mark.parametrize("quem", ["leitor", "autor", "atas", "sem_cargo"])
def test_ca26_terceiro_nao_arquiva(papeis: dict[str, Usuario], quem: str) -> None:
    documento = _enviar(papeis)

    with pytest.raises(BusinessError) as erro:
        documentos.arquivar(papeis[quem].id, documento.id)

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ca26_quem_gerencia_arquiva_e_desarquiva(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)

    documentos.arquivar(papeis["gerente"].id, documento.id)
    documentos.desarquivar(papeis["gerente"].id, documento.id)

    documento.refresh_from_db()
    assert documento.situacao == "VIGENTE"


# --- a lista, os filtros e o detalhe (CA-23) ------------------------------------------------------------


def test_ca23_lista_filtra_por_categoria_tipo_titulo_e_arquivados(papeis: dict[str, Usuario]) -> None:
    estatuto = _enviar(papeis)
    balanco = _enviar(papeis, titulo="Balanço 2025", categoria_id=categoria("Financeiro").id)
    ata = _ata(papeis)
    velho = _enviar(papeis, titulo="Regimento antigo")
    documentos.arquivar(papeis["envia"].id, velho.id)
    leitor = papeis["leitor"].id

    def titulos(**filtros: Any) -> list[str]:
        return [d["titulo"] for d in consulta.documentos(leitor, **filtros)["itens"]]

    assert set(titulos()) == {estatuto.titulo, balanco.titulo, ata.titulo}
    assert titulos(categoria_id=categoria("Financeiro").id) == ["Balanço 2025"]
    assert titulos(tipo="ATA") == ["Ata de outubro"]
    assert titulos(titulo="balan") == ["Balanço 2025"]
    assert titulos(arquivados=True) == ["Regimento antigo"]


def test_ca23_pagina_do_mais_novo_ao_mais_antigo(papeis: dict[str, Usuario]) -> None:
    criados = [_enviar(papeis, titulo=f"Doc {n}") for n in range(3)]
    leitor = papeis["leitor"].id

    primeira = consulta.documentos(leitor, limite=2)
    segunda = consulta.documentos(leitor, antes=primeira["itens"][-1]["id"], limite=2)

    assert [d["id"] for d in primeira["itens"]] == [criados[2].id, criados[1].id]
    assert primeira["tem_mais"] is True
    assert [d["id"] for d in segunda["itens"]] == [criados[0].id]
    assert segunda["tem_mais"] is False


def test_ca23_a_lista_so_responde_a_quem_le_gestao(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        consulta.documentos(papeis["sem_cargo"].id)

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_o_detalhe_traz_dados_versoes_e_acoes_por_papel(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)
    documentos.nova_versao(papeis["envia"].id, documento.id, arquivo=_arquivo(), motivo="Segunda")

    dono = consulta.detalhe_do_documento(papeis["envia"].id, documento.id)
    leitor = consulta.detalhe_do_documento(papeis["leitor"].id, documento.id)

    assert dono["categoria"]["nome"] == "Institucional"
    assert dono["enviado_por"]["id"] == papeis["envia"].id
    assert [v["numero"] for v in dono["versoes"]] == [1, 2]
    assert dono["versoes"][1]["motivo"] == "Segunda"
    assert dono["acoes"] == ["nova_versao", "arquivar"]
    assert leitor["acoes"] == []


def test_o_detalhe_de_documento_inexistente_e_404(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        consulta.detalhe_do_documento(papeis["leitor"].id, uuid.uuid4())

    assert _codigo(erro) == "NOT_FOUND"


def test_nada_e_apagado_nos_documentos(papeis: dict[str, Usuario]) -> None:
    documento = _enviar(papeis)
    documentos.nova_versao(papeis["envia"].id, documento.id, arquivo=_arquivo(), motivo="m")
    documentos.arquivar(papeis["envia"].id, documento.id)

    assert Documento.objects.count() == 1
    assert VersaoDeDocumento.objects.count() == 2
    assert CategoriaDeDocumento.objects.filter(nome="Institucional").exists()
