"""Categorias de documento (só o admin) e o download dos arquivos (CA-27, CA-28)."""

import uuid
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from comunicacao.models import CategoriaDeDocumento, Documento, Imutavel
from comunicacao.services import categorias, consulta, documentos
from comunicacao.tests.conftest import acoes_de, categoria, registros_de
from comunicacao.tests.conftest import documento as documento_pronto
from kernel.errors import BusinessError
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\nprimeira versao\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _codigo(excecao: pytest.ExceptionInfo[BusinessError]) -> str:
    return excecao.value.code


def _arquivo(conteudo: bytes = PDF, nome: str = "a.pdf", tipo: str = "application/pdf") -> Any:
    return SimpleUploadedFile(nome, conteudo, content_type=tipo)


def _documento(papeis: dict[str, Usuario]) -> Documento:
    return documentos.enviar_documento(
        papeis["envia"].id,
        titulo="Estatuto",
        descricao="",
        categoria_id=categoria().id,
        arquivo=_arquivo(),
    )


# --- categorias (CA-28) -------------------------------------------------------------------------------------


def test_ca28_o_admin_cria_renomeia_desativa_e_reativa(papeis: dict[str, Usuario]) -> None:
    admin = papeis["admin"].id

    criada = categorias.criar(admin, "  Jurídico ")
    assert criada.nome == "Jurídico"
    assert criada.ativa is True

    categorias.editar(admin, criada.id, "Jurídico e contratos")
    categorias.desativar(admin, criada.id)
    criada.refresh_from_db()
    assert (criada.nome, criada.ativa) == ("Jurídico e contratos", False)

    categorias.reativar(admin, criada.id)
    criada.refresh_from_db()
    assert criada.ativa is True
    assert acoes_de("categoria_de_documento", criada.id) == [
        "CATEGORIA_DE_DOCUMENTO_CRIADA",
        "CATEGORIA_DE_DOCUMENTO_EDITADA",
        "CATEGORIA_DE_DOCUMENTO_DESATIVADA",
        "CATEGORIA_DE_DOCUMENTO_REATIVADA",
    ]


@pytest.mark.parametrize("quem", ["gerente", "envia", "autor", "leitor", "sem_cargo"])
def test_ca28_so_o_admin_mantem_as_categorias(papeis: dict[str, Usuario], quem: str) -> None:
    ator = papeis[quem].id
    existente = categoria()

    chamadas: list[Callable[[], object]] = [
        partial(categorias.criar, ator, "Nova"),
        partial(categorias.editar, ator, existente.id, "Outro nome"),
        partial(categorias.desativar, ator, existente.id),
        partial(categorias.reativar, ator, existente.id),
    ]
    for chamada in chamadas:
        with pytest.raises(BusinessError) as erro:
            chamada()
        assert _codigo(erro) == "PERMISSION_DENIED"
    existente.refresh_from_db()
    assert (existente.nome, existente.ativa) == ("Institucional", True)


def test_ca28_nome_repetido_sem_diferenciar_maiusculas_e_recusado(papeis: dict[str, Usuario]) -> None:
    admin = papeis["admin"].id
    outra = categorias.criar(admin, "Jurídico")

    with pytest.raises(BusinessError) as criar:
        categorias.criar(admin, "INSTITUCIONAL")
    with pytest.raises(BusinessError) as editar:
        categorias.editar(admin, outra.id, "financeiro")

    assert _codigo(criar) == "CATEGORIA_JA_EXISTE"
    assert _codigo(editar) == "CATEGORIA_JA_EXISTE"
    categorias.editar(admin, outra.id, "JURÍDICO")  # o mesmo nome, só trocando a caixa, é permitido


def test_ca28_nome_em_branco_ou_longo_e_recusado(papeis: dict[str, Usuario]) -> None:
    for nome in ("  ", "x" * 61):
        with pytest.raises(BusinessError) as erro:
            categorias.criar(papeis["admin"].id, nome)
        assert _codigo(erro) == "VALIDATION_ERROR"
        assert "nome" in erro.value.details


def test_ca28_categoria_inexistente_e_404(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        categorias.desativar(papeis["admin"].id, uuid.uuid4())

    assert _codigo(erro) == "NOT_FOUND"


def test_ca28_categoria_usada_e_desativada_nunca_apagada(papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)
    usada = categoria()

    categorias.desativar(papeis["admin"].id, usada.id)

    assert CategoriaDeDocumento.objects.filter(pk=usada.pk, ativa=False).exists()
    documento.refresh_from_db()
    assert documento.categoria_id == usada.id
    with pytest.raises(Imutavel, match="não é apagado"):
        usada.delete()


def test_ca28_o_documento_novo_em_categoria_inativa_e_recusado_e_o_antigo_segue(
    papeis: dict[str, Usuario],
) -> None:
    antigo = _documento(papeis)
    categorias.desativar(papeis["admin"].id, categoria().id)

    with pytest.raises(BusinessError) as erro:
        _documento(papeis)
    documentos.nova_versao(
        papeis["envia"].id, antigo.id, arquivo=_arquivo(PNG, "b.png", "image/png"), motivo="m"
    )

    assert _codigo(erro) == "CATEGORIA_INATIVA"
    assert Documento.objects.count() == 1


def test_ca28_o_nome_no_documento_e_o_do_momento_do_envio(papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)

    categorias.editar(papeis["admin"].id, categoria().id, "Institucional e legal")

    documento.refresh_from_db()
    assert documento.categoria_nome == "Institucional"


def test_ca28_a_auditoria_leva_o_nome(papeis: dict[str, Usuario]) -> None:
    criada = categorias.criar(papeis["admin"].id, "Jurídico")

    (registro,) = registros_de("categoria_de_documento", criada.id, "CATEGORIA_DE_DOCUMENTO_CRIADA")
    assert registro.dados == {"nome": "Jurídico"}


def test_ca28_a_lista_traz_as_ativas_e_o_admin_pede_todas(papeis: dict[str, Usuario]) -> None:
    categorias.desativar(papeis["admin"].id, categoria("Outros").id)

    do_leitor = categorias.listar(papeis["leitor"].id, todas=True)
    do_admin = categorias.listar(papeis["admin"].id, todas=True)
    ativas_do_admin = categorias.listar(papeis["admin"].id)

    assert [c.nome for c in do_leitor] == ["Eventos", "Financeiro", "Institucional"]
    assert "Outros" in [c.nome for c in do_admin]
    assert "Outros" not in [c.nome for c in ativas_do_admin]


def test_ca28_a_lista_exige_leitura_de_gestao(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        categorias.listar(papeis["sem_cargo"].id)

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ca28_o_nome_repetido_tambem_e_barrado_no_banco(db: None) -> None:
    with pytest.raises(IntegrityError):
        CategoriaDeDocumento.objects.create(nome="institucional")


# --- download (CA-27) ---------------------------------------------------------------------------------------


def _conteudo(resposta: Any) -> bytes:
    return bytes(resposta.content)


def test_ca27_baixa_a_versao_vigente_e_as_antigas(papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)
    documentos.nova_versao(
        papeis["envia"].id, documento.id, arquivo=_arquivo(PNG, "b.png", "image/png"), motivo="Nova"
    )
    leitor = papeis["leitor"].id

    vigente = consulta.download(leitor, documento.id)
    primeira = consulta.download(leitor, documento.id, numero=1)
    segunda = consulta.download(leitor, documento.id, numero=2)

    assert _conteudo(vigente) == PNG == _conteudo(segunda)
    assert _conteudo(primeira) == PDF
    assert vigente["Content-Type"] == "image/png"
    assert primeira["Content-Type"] == "application/pdf"


def test_ca27_a_resposta_tem_nosniff_no_store_e_inline(papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)

    resposta = consulta.download(papeis["leitor"].id, documento.id)

    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert resposta["Cache-Control"] == "private, no-store"
    assert resposta["Content-Disposition"].startswith("inline;")


def test_ca27_o_arquivado_continua_baixavel(papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)
    documentos.arquivar(papeis["envia"].id, documento.id)

    assert _conteudo(consulta.download(papeis["leitor"].id, documento.id)) == PDF


@pytest.mark.parametrize("quem", ["sem_cargo"])
def test_ca27_sem_cargo_e_negado(papeis: dict[str, Usuario], quem: str) -> None:
    documento = _documento(papeis)

    with pytest.raises(BusinessError) as erro:
        consulta.download(papeis[quem].id, documento.id)

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ca27_o_admin_baixa(papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)

    assert _conteudo(consulta.download(papeis["admin"].id, documento.id)) == PDF


def test_ca27_documento_ou_versao_inexistente_e_404(papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)

    with pytest.raises(BusinessError) as sem_documento:
        consulta.download(papeis["leitor"].id, uuid.uuid4())
    with pytest.raises(BusinessError) as sem_versao:
        consulta.download(papeis["leitor"].id, documento.id, numero=9)

    assert _codigo(sem_documento) == "NOT_FOUND"
    assert _codigo(sem_versao) == "NOT_FOUND"


def test_ca27_chave_de_outro_contexto_e_404(papeis: dict[str, Usuario]) -> None:
    default_storage.save("comprovantes/segredo.pdf", ContentFile(PDF))
    adulterado = documento_pronto(chave="comprovantes/segredo.pdf")

    with pytest.raises(BusinessError) as erro:
        consulta.download(papeis["leitor"].id, adulterado.id)

    assert _codigo(erro) == "NOT_FOUND"


def test_ca27_arquivo_ausente_no_armazenamento_e_404_de_documento(papeis: dict[str, Usuario]) -> None:
    sem_arquivo = documento_pronto(chave="documentos/some.pdf")

    with pytest.raises(BusinessError) as erro:
        consulta.download(papeis["leitor"].id, sem_arquivo.id)

    assert _codigo(erro) == "NOT_FOUND"
    assert erro.value.message == "Documento não encontrado."


def test_ca27_baixar_nao_gera_auditoria(papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)

    consulta.download(papeis["leitor"].id, documento.id)

    assert acoes_de("documento", documento.id) == ["DOCUMENTO_ENVIADO"]
