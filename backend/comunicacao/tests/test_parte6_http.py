"""As rotas HTTP do feed e dos documentos, com `APIClient` (CA-01 a CA-31, pelo lado do contrato).

Cobre cada rota com sucesso, a tabela de erros, a ordem das conferências, a paridade entre `acoes` e as rotas,
o download e o esquema OpenAPI. Os usuários vêm de `tests/apoio.py`; a regra em si está nos outros arquivos.
"""

import re
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from comunicacao.models import Comunicado
from comunicacao.services import comentarios, comunicados, documentos
from comunicacao.tests.conftest import categoria
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

BASE = "/api/v1/comunicacao"
PDF = b"%PDF-1.4\nconteudo do pdf\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

Cliente = Callable[[str], APIClient]


@pytest.fixture
def cliente(papeis: dict[str, Usuario]) -> Cliente:
    """Um cliente logado por papel, criado na primeira vez que se pede (a senha é cara de conferir)."""
    criados: dict[str, APIClient] = {}

    def de(papel: str) -> APIClient:
        if papel not in criados:
            criados[papel] = apoio.cliente_de(papeis[papel])
        return criados[papel]

    return de


def _arquivo(conteudo: bytes = PDF, nome: str = "estatuto.pdf", tipo: str = "application/pdf") -> Any:
    return SimpleUploadedFile(nome, conteudo, content_type=tipo)


def _codigo(resposta: Any) -> str:
    return str(resposta.json()["error"]["code"])


def _publicar(papeis: dict[str, Usuario], **mudar: Any) -> Comunicado:
    dados: dict[str, Any] = {"tipo": "COMUNICADO", "titulo": "Reunião", "texto": "Sábado, 10h."}
    dados.update(mudar)
    return comunicados.publicar(papeis["autor"].id, **dados)


def _documento(papeis: dict[str, Usuario]) -> Any:
    return documentos.enviar_documento(
        papeis["envia"].id, titulo="Estatuto", descricao="", categoria_id=categoria().id, arquivo=_arquivo()
    )


# --- acesso: negado por padrão -------------------------------------------------------------------------

_ID = uuid.UUID(int=1)
_ROTAS: list[tuple[str, str]] = [
    ("get", "referencias/"),
    ("get", "comunicados/"),
    ("post", "comunicados/"),
    ("get", "comunicados/despublicados/"),
    ("get", f"comunicados/{_ID}/"),
    ("post", f"comunicados/{_ID}/editar/"),
    ("post", f"comunicados/{_ID}/despublicar/"),
    ("post", f"comunicados/{_ID}/republicar/"),
    ("post", f"comunicados/{_ID}/fixar/"),
    ("post", f"comunicados/{_ID}/desafixar/"),
    ("post", f"comunicados/{_ID}/reacao/"),
    ("post", f"comunicados/{_ID}/reacao/retirar/"),
    ("get", f"comunicados/{_ID}/comentarios/"),
    ("post", f"comunicados/{_ID}/comentarios/"),
    ("post", f"comentarios/{_ID}/editar/"),
    ("post", f"comentarios/{_ID}/ocultar/"),
    ("post", f"comentarios/{_ID}/reexibir/"),
    ("get", "documentos/"),
    ("post", "documentos/"),
    ("post", "documentos/atas/"),
    ("get", f"documentos/{_ID}/"),
    ("get", f"documentos/{_ID}/arquivo/"),
    ("get", f"documentos/{_ID}/versoes/1/arquivo/"),
    ("post", f"documentos/{_ID}/versoes/"),
    ("post", f"documentos/{_ID}/arquivar/"),
    ("post", f"documentos/{_ID}/desarquivar/"),
    ("get", "categorias/"),
    ("post", "categorias/"),
    ("post", f"categorias/{_ID}/editar/"),
    ("post", f"categorias/{_ID}/desativar/"),
    ("post", f"categorias/{_ID}/reativar/"),
]


@pytest.mark.parametrize(("metodo", "caminho"), _ROTAS)
def test_sem_sessao_toda_rota_e_negada(metodo: str, caminho: str) -> None:
    resposta = getattr(APIClient(), metodo)(f"{BASE}/{caminho}")

    assert resposta.status_code == 401


@pytest.mark.parametrize(("metodo", "caminho"), _ROTAS)
def test_sem_cargo_toda_rota_e_403(cliente: Cliente, metodo: str, caminho: str) -> None:
    resposta = getattr(cliente("sem_cargo"), metodo)(f"{BASE}/{caminho}")

    assert resposta.status_code == 403
    assert _codigo(resposta) == "PERMISSION_DENIED"


_ESCRITAS_COM_PERMISSAO = [
    ("comunicados/", "leitor"),
    (f"comunicados/{_ID}/fixar/", "autor"),
    (f"comunicados/{_ID}/desafixar/", "leitor"),
    ("documentos/", "leitor"),
    ("documentos/atas/", "envia"),
    ("categorias/", "gerente"),
    (f"categorias/{_ID}/editar/", "envia"),
]


@pytest.mark.parametrize(("caminho", "papel"), _ESCRITAS_COM_PERMISSAO)
def test_a_escrita_declara_quem_pode_e_nega_os_demais(cliente: Cliente, caminho: str, papel: str) -> None:
    resposta = cliente(papel).post(f"{BASE}/{caminho}", {}, format="json")

    assert resposta.status_code == 403
    assert _codigo(resposta) == "PERMISSION_DENIED"


# --- referências ---------------------------------------------------------------------------------------


def test_referencias_trazem_categorias_ativas_tipos_e_reacoes(cliente: Cliente) -> None:
    resposta = cliente("leitor").get(f"{BASE}/referencias/")

    assert resposta.status_code == 200
    dados = resposta.json()
    assert [c["nome"] for c in dados["categorias"]] == ["Eventos", "Financeiro", "Institucional", "Outros"]
    assert [t["codigo"] for t in dados["tipos"]] == ["COMUNICADO", "PAUTA"]
    assert [r["codigo"] for r in dados["reacoes"]] == ["CIENTE", "DE_ACORDO", "DUVIDA", "COMEMORACAO"]


# --- comunicados (CA-02 a CA-10) -----------------------------------------------------------------------


def test_publica_e_le_o_detalhe_com_o_documento_vinculado(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    documento = _documento(papeis)

    resposta = cliente("autor").post(
        f"{BASE}/comunicados/",
        {"tipo": "PAUTA", "titulo": "Pauta", "texto": "1. Orçamento", "documentos_ids": [str(documento.id)]},
        format="json",
    )

    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["tipo"] == "PAUTA"
    assert dados["autor"]["id"] == str(papeis["autor"].id)
    assert [d["id"] for d in dados["documentos"]] == [str(documento.id)]
    assert "editar_comunicado" in dados["acoes"]
    detalhe = cliente("leitor").get(f"{BASE}/comunicados/{dados['id']}/")
    assert detalhe.status_code == 200
    assert detalhe.json()["acoes"] == ["reagir", "comentar"]


def test_o_feed_traz_fixados_so_na_primeira_pagina_e_pagina_o_resto(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    criados = [_publicar(papeis, titulo=f"Aviso {n}") for n in range(4)]
    comunicados.fixar(papeis["gerente"].id, criados[0].id)

    primeira = cliente("leitor").get(f"{BASE}/comunicados/", {"limite": 2}).json()
    segunda = cliente("leitor").get(
        f"{BASE}/comunicados/", {"limite": 2, "antes": primeira["itens"][-1]["id"]}
    )

    assert [c["titulo"] for c in primeira["fixados"]] == ["Aviso 0"]
    assert [c["titulo"] for c in primeira["itens"]] == ["Aviso 3", "Aviso 2"]
    assert primeira["tem_mais"] is True
    assert segunda.json()["fixados"] == []
    assert [c["titulo"] for c in segunda.json()["itens"]] == ["Aviso 1"]
    assert segunda.json()["tem_mais"] is False


def test_o_feed_recusa_limite_fora_da_faixa_e_cursor_invalido(cliente: Cliente) -> None:
    assert cliente("leitor").get(f"{BASE}/comunicados/", {"limite": 51}).status_code == 400
    assert cliente("leitor").get(f"{BASE}/comunicados/", {"antes": "x"}).status_code == 400
    assert cliente("leitor").get(f"{BASE}/comunicados/", {"antes": str(_ID)}).status_code == 404


def test_edita_despublica_republica_fixa_e_desafixa(cliente: Cliente, papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    base = f"{BASE}/comunicados/{comunicado.id}"

    editado = cliente("autor").post(
        f"{base}/editar/", {"titulo": "Novo", "texto": "Texto novo", "documentos_ids": []}, format="json"
    )
    fixado = cliente("gerente").post(f"{base}/fixar/")
    desafixado = cliente("gerente").post(f"{base}/desafixar/")
    despublicado = cliente("autor").post(f"{base}/despublicar/", {"motivo": "Erro"}, format="json")
    republicado = cliente("autor").post(f"{base}/republicar/")

    assert (editado.status_code, editado.json()["titulo"], editado.json()["editado"]) == (200, "Novo", True)
    assert (fixado.status_code, fixado.json()["fixado"]) == (200, True)
    assert (desafixado.status_code, desafixado.json()["fixado"]) == (200, False)
    assert despublicado.json()["situacao"] == "DESPUBLICADO"
    assert despublicado.json()["despublicado"]["motivo"] == "Erro"
    assert (republicado.status_code, republicado.json()["situacao"]) == (200, "PUBLICADO")


def test_lista_de_despublicados_respeita_quem_ve(cliente: Cliente, papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    do_autor = cliente("autor").get(f"{BASE}/comunicados/despublicados/").json()
    da_gerencia = cliente("gerente").get(f"{BASE}/comunicados/despublicados/").json()
    do_leitor = cliente("leitor").get(f"{BASE}/comunicados/despublicados/").json()

    assert [c["id"] for c in do_autor["itens"]] == [str(comunicado.id)]
    assert [c["id"] for c in da_gerencia["itens"]] == [str(comunicado.id)]
    assert do_leitor["itens"] == []


def test_despublicado_que_o_ator_nao_ve_e_404_em_toda_rota(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    comunicado = _publicar(papeis)
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")
    base = f"{BASE}/comunicados/{comunicado.id}"

    respostas = [
        cliente("leitor").get(f"{base}/"),
        cliente("leitor").get(f"{base}/comentarios/"),
        cliente("leitor").post(f"{base}/reacao/", {"tipo": "CIENTE"}, format="json"),
        cliente("leitor").post(f"{base}/reacao/retirar/"),
        cliente("leitor").post(f"{base}/comentarios/", {"texto": "oi"}, format="json"),
        cliente("leitor").post(f"{base}/despublicar/", {"motivo": "x"}, format="json"),
    ]

    assert [r.status_code for r in respostas] == [404] * 6
    assert {_codigo(r) for r in respostas} == {"NOT_FOUND"}


# --- a ordem das conferências --------------------------------------------------------------------------


def test_ordem_leitura_entrada_existencia_quem_pode_situacao(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    comunicado = _publicar(papeis)
    inexistente = f"{BASE}/comunicados/{uuid.uuid4()}"
    existente = f"{BASE}/comunicados/{comunicado.id}"

    sem_cargo_e_invalido = cliente("sem_cargo").post(f"{inexistente}/editar/", {}, format="json")
    invalido_e_inexistente = cliente("autor").post(f"{inexistente}/editar/", {}, format="json")
    valido_e_inexistente = cliente("autor").post(
        f"{inexistente}/editar/", {"titulo": "a", "texto": "b", "documentos_ids": []}, format="json"
    )
    terceiro = cliente("leitor").post(
        f"{existente}/editar/", {"titulo": "a", "texto": "b", "documentos_ids": []}, format="json"
    )
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")
    situacao = cliente("autor").post(
        f"{existente}/editar/", {"titulo": "a", "texto": "b", "documentos_ids": []}, format="json"
    )

    assert sem_cargo_e_invalido.status_code == 403
    assert invalido_e_inexistente.status_code == 400
    assert _codigo(invalido_e_inexistente) == "VALIDATION_ERROR"
    assert valido_e_inexistente.status_code == 404
    assert (terceiro.status_code, _codigo(terceiro)) == (403, "PERMISSION_DENIED")
    assert (situacao.status_code, _codigo(situacao)) == (422, "COMUNICADO_NAO_PUBLICADO")


def test_terceiro_num_comunicado_publicado_e_403_e_nao_404(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    comunicado = _publicar(papeis)

    resposta = cliente("leitor").post(
        f"{BASE}/comunicados/{comunicado.id}/despublicar/", {"motivo": "x"}, format="json"
    )

    assert (resposta.status_code, _codigo(resposta)) == (403, "PERMISSION_DENIED")


# --- a tabela de erros ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("corpo", "campos"),
    [
        ({"tipo": "OUTRO", "titulo": "a", "texto": "b"}, {"tipo"}),
        ({"tipo": "COMUNICADO", "titulo": " ", "texto": ""}, {"titulo", "texto"}),
        ({"tipo": "COMUNICADO", "titulo": "x" * 121, "texto": "b"}, {"titulo"}),
        ({"tipo": "COMUNICADO", "titulo": "a", "texto": "x" * 5001}, {"texto"}),
        (
            {"tipo": "COMUNICADO", "titulo": "a", "texto": "b", "documentos_ids": [str(_ID)]},
            {"documentos_ids"},
        ),
    ],
)
def test_publicar_com_dados_invalidos_e_400_com_o_campo(
    cliente: Cliente, corpo: dict[str, Any], campos: set[str]
) -> None:
    resposta = cliente("autor").post(f"{BASE}/comunicados/", corpo, format="json")

    assert resposta.status_code == 400
    assert _codigo(resposta) == "VALIDATION_ERROR"
    assert set(resposta.json()["error"]["details"]) == campos


def test_publicar_exige_corpo_json_ou_formulario_bem_formado(cliente: Cliente) -> None:
    resposta = cliente("autor").post(f"{BASE}/comunicados/", {"titulo": "a"}, format="json")

    assert resposta.status_code == 400
    assert _codigo(resposta) == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("acao", "codigo"),
    [("desafixar", "NAO_ESTA_FIXADO"), ("republicar", "COMUNICADO_JA_PUBLICADO")],
)
def test_situacao_invalida_e_422_com_o_codigo_da_tabela(
    cliente: Cliente, papeis: dict[str, Usuario], acao: str, codigo: str
) -> None:
    comunicado = _publicar(papeis)

    resposta = cliente("gerente").post(f"{BASE}/comunicados/{comunicado.id}/{acao}/")

    assert (resposta.status_code, _codigo(resposta)) == (422, codigo)


def test_o_erro_vem_no_envelope_estavel(cliente: Cliente) -> None:
    resposta = cliente("leitor").get(f"{BASE}/comunicados/{uuid.uuid4()}/")

    assert resposta.status_code == 404
    assert set(resposta.json()) == {"error"}
    assert set(resposta.json()["error"]) == {"code", "message", "details"}


# --- reações e comentários (CA-11 a CA-20) -------------------------------------------------------------


def test_reage_troca_repete_para_retirar_e_retira(cliente: Cliente, papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    rota = f"{BASE}/comunicados/{comunicado.id}/reacao/"

    primeira = cliente("leitor").post(rota, {"tipo": "CIENTE"}, format="json")
    trocada = cliente("leitor").post(rota, {"tipo": "DUVIDA"}, format="json")
    de_outro = cliente("outro").post(rota, {"tipo": "DUVIDA"}, format="json")
    retirada = cliente("leitor").post(f"{rota}retirar/")

    assert primeira.status_code == 200
    assert primeira.json()["minha"] == "CIENTE"
    assert trocada.json()["contagem"] == {"CIENTE": 0, "DE_ACORDO": 0, "DUVIDA": 1, "COMEMORACAO": 0}
    assert [p["id"] for p in de_outro.json()["quem"]["DUVIDA"]] == [
        str(papeis["leitor"].id),
        str(papeis["outro"].id),
    ]
    assert retirada.json()["minha"] is None
    assert retirada.json()["contagem"]["DUVIDA"] == 1


def test_reacao_de_tipo_desconhecido_e_400_e_retirar_sem_reacao_e_422(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    comunicado = _publicar(papeis)
    rota = f"{BASE}/comunicados/{comunicado.id}/reacao/"

    desconhecido = cliente("leitor").post(rota, {"tipo": "RAIVA"}, format="json")
    sem_reacao = cliente("leitor").post(f"{rota}retirar/")

    assert (desconhecido.status_code, _codigo(desconhecido)) == (400, "VALIDATION_ERROR")
    assert (sem_reacao.status_code, _codigo(sem_reacao)) == (422, "SEM_REACAO")


def test_comenta_lista_edita_oculta_e_reexibe(cliente: Cliente, papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    rota = f"{BASE}/comunicados/{comunicado.id}/comentarios/"

    criado = cliente("leitor").post(rota, {"texto": "Concordo"}, format="json")
    comentario_id = criado.json()["id"]
    editado = cliente("leitor").post(
        f"{BASE}/comentarios/{comentario_id}/editar/", {"texto": "Concordo, com ressalvas"}, format="json"
    )
    ocultado = cliente("gerente").post(
        f"{BASE}/comentarios/{comentario_id}/ocultar/", {"motivo": "Fora do assunto"}, format="json"
    )
    do_outro = cliente("outro").get(rota).json()
    do_autor = cliente("leitor").get(rota).json()
    reexibido = cliente("gerente").post(f"{BASE}/comentarios/{comentario_id}/reexibir/")

    assert criado.status_code == 201
    assert criado.json()["acoes"] == ["editar_comentario", "ocultar_comentario"]
    assert (editado.status_code, editado.json()["editado"]) == (200, True)
    assert ocultado.json()["oculto"]["pela_gerencia"] is True
    assert ocultado.json()["oculto"]["motivo"] == "Fora do assunto"
    assert do_outro["itens"] == []  # oculto: some para os demais
    assert [c["situacao"] for c in do_autor["itens"]] == ["OCULTO"]
    assert (reexibido.status_code, reexibido.json()["situacao"]) == (200, "VISIVEL")


def test_o_comentario_oculto_pela_gerencia_so_a_gerencia_reexibe(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    comunicado = _publicar(papeis)
    comentario = comentarios.comentar(papeis["leitor"].id, comunicado.id, "oi")
    comentarios.ocultar(papeis["gerente"].id, comentario.id, "Motivo")

    resposta = cliente("leitor").post(f"{BASE}/comentarios/{comentario.id}/reexibir/")

    assert (resposta.status_code, _codigo(resposta)) == (403, "PERMISSION_DENIED")


def test_comentarios_paginam_do_mais_antigo_ao_mais_novo(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    comunicado = _publicar(papeis)
    for n in range(3):
        comentarios.comentar(papeis["leitor"].id, comunicado.id, f"c{n}")
    rota = f"{BASE}/comunicados/{comunicado.id}/comentarios/"

    primeira = cliente("outro").get(rota, {"limite": 2}).json()
    segunda = cliente("outro").get(rota, {"limite": 2, "depois": primeira["itens"][-1]["id"]}).json()

    assert [c["texto"] for c in primeira["itens"]] == ["c0", "c1"]
    assert primeira["tem_mais"] is True
    assert [c["texto"] for c in segunda["itens"]] == ["c2"]
    assert segunda["tem_mais"] is False


def test_comentario_inexistente_e_404_e_comentario_vazio_e_400(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    comunicado = _publicar(papeis)

    inexistente = cliente("leitor").post(
        f"{BASE}/comentarios/{uuid.uuid4()}/editar/", {"texto": "x"}, format="json"
    )
    vazio = cliente("leitor").post(
        f"{BASE}/comunicados/{comunicado.id}/comentarios/", {"texto": " "}, format="json"
    )

    assert inexistente.status_code == 404
    assert (vazio.status_code, _codigo(vazio)) == (400, "VALIDATION_ERROR")


# --- texto livre (CA-31) -------------------------------------------------------------------------------

_HTML = '<script>alert("x")</script><img src=x onerror=alert(1)> & <b>negrito</b>'


def test_ca31_o_texto_com_html_volta_como_foi_guardado_e_em_json(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    resposta = cliente("autor").post(
        f"{BASE}/comunicados/", {"tipo": "COMUNICADO", "titulo": _HTML, "texto": _HTML}, format="json"
    )
    comunicado_id = resposta.json()["id"]
    comentario = cliente("leitor").post(
        f"{BASE}/comunicados/{comunicado_id}/comentarios/", {"texto": _HTML}, format="json"
    )

    detalhe = cliente("leitor").get(f"{BASE}/comunicados/{comunicado_id}/")
    lista = cliente("leitor").get(f"{BASE}/comunicados/{comunicado_id}/comentarios/")

    assert detalhe["Content-Type"].startswith("application/json")
    assert detalhe.json()["titulo"] == _HTML == detalhe.json()["texto"]
    assert comentario.json()["texto"] == _HTML
    assert lista.json()["itens"][0]["texto"] == _HTML
    assert detalhe["X-Content-Type-Options"] == "nosniff"


# --- campos de saída declarados ------------------------------------------------------------------------

_CAMPOS_DO_COMUNICADO = {
    "id", "tipo", "titulo", "texto", "autor", "situacao", "fixado", "fixado_em", "publicado_em", "editado",
    "editado_em", "despublicado", "documentos", "reacoes", "total_de_comentarios", "acoes",
}  # fmt: skip


def test_a_saida_so_traz_os_campos_declarados(cliente: Cliente, papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    comentarios.comentar(papeis["leitor"].id, comunicado.id, "oi")

    detalhe = cliente("leitor").get(f"{BASE}/comunicados/{comunicado.id}/").json()
    feed = cliente("leitor").get(f"{BASE}/comunicados/").json()
    lista = cliente("leitor").get(f"{BASE}/comunicados/{comunicado.id}/comentarios/").json()

    assert set(detalhe) == _CAMPOS_DO_COMUNICADO
    assert set(feed["itens"][0]) == _CAMPOS_DO_COMUNICADO
    assert set(detalhe["autor"]) == {"id", "nome"}
    assert set(detalhe["reacoes"]) == {"contagem", "minha", "quem"}
    assert set(lista["itens"][0]) == {
        "id", "autor", "texto", "situacao", "criado_em", "editado", "editado_em", "oculto", "acoes",
    }  # fmt: skip
    assert "autor_id" not in str(detalhe)


# --- documentos e atas (CA-21 a CA-27) -----------------------------------------------------------------


def test_envia_documento_ata_nova_versao_arquiva_e_desarquiva(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    enviado = cliente("envia").post(
        f"{BASE}/documentos/",
        {
            "titulo": "Estatuto",
            "descricao": "Em cartório",
            "categoria_id": str(categoria().id),
            "arquivo": _arquivo(),
        },
        format="multipart",
    )
    ata = cliente("atas").post(
        f"{BASE}/documentos/atas/",
        {"titulo": "Ata", "data_da_reuniao": "2026-10-30", "arquivo": _arquivo(nome="ata.pdf")},
        format="multipart",
    )
    documento_id = enviado.json()["id"]
    versao = cliente("envia").post(
        f"{BASE}/documentos/{documento_id}/versoes/",
        {"motivo": "Correção", "arquivo": _arquivo(PNG, "novo.png", "image/png")},
        format="multipart",
    )
    arquivado = cliente("envia").post(f"{BASE}/documentos/{documento_id}/arquivar/")
    desarquivado = cliente("envia").post(f"{BASE}/documentos/{documento_id}/desarquivar/")

    assert enviado.status_code == 201
    assert enviado.json()["categoria"]["nome"] == "Institucional"
    assert (ata.status_code, ata.json()["tipo"], ata.json()["data_da_reuniao"]) == (201, "ATA", "2026-10-30")
    assert (versao.status_code, versao.json()["versao_atual"]) == (201, 2)
    assert [v["situacao"] for v in versao.json()["versoes"]] == ["SUBSTITUIDA", "VIGENTE"]
    assert arquivado.json()["situacao"] == "ARQUIVADO"
    assert desarquivado.json()["situacao"] == "VIGENTE"


def test_a_lista_de_documentos_filtra_e_pagina(cliente: Cliente, papeis: dict[str, Usuario]) -> None:
    primeiro = _documento(papeis)
    segundo = _documento(papeis)
    documentos.arquivar(papeis["envia"].id, primeiro.id)

    vigentes = cliente("leitor").get(f"{BASE}/documentos/").json()
    arquivados = cliente("leitor").get(f"{BASE}/documentos/", {"arquivados": "1"}).json()
    paginada = cliente("leitor").get(f"{BASE}/documentos/", {"limite": "1", "tipo": "DOCUMENTO"}).json()
    ruim = cliente("leitor").get(f"{BASE}/documentos/", {"tipo": "XYZ"})

    assert [d["id"] for d in vigentes["itens"]] == [str(segundo.id)]
    assert [d["id"] for d in arquivados["itens"]] == [str(primeiro.id)]
    assert len(paginada["itens"]) == 1
    assert ruim.status_code == 400


def test_documento_com_arquivo_invalido_e_400_no_campo_arquivo_com_texto_de_documento(
    cliente: Cliente,
) -> None:
    corpo = {"titulo": "x", "categoria_id": str(categoria().id)}

    sem_arquivo = cliente("envia").post(f"{BASE}/documentos/", corpo, format="multipart")
    tipo_ruim = cliente("envia").post(
        f"{BASE}/documentos/",
        {**corpo, "arquivo": _arquivo(b"texto", "nota.txt", "text/plain")},
        format="multipart",
    )

    assert sem_arquivo.json()["error"]["details"] == {"arquivo": ["Envie um arquivo de documento válido."]}
    assert (tipo_ruim.status_code, set(tipo_ruim.json()["error"]["details"])) == (400, {"arquivo"})


def test_documento_pede_multipart_e_recusa_json(cliente: Cliente) -> None:
    resposta = cliente("envia").post(f"{BASE}/documentos/", {"titulo": "x"}, format="json")

    assert resposta.status_code == 415


def test_ata_futura_e_422_e_categoria_inativa_e_422(cliente: Cliente, papeis: dict[str, Usuario]) -> None:
    futura = cliente("atas").post(
        f"{BASE}/documentos/atas/",
        {"titulo": "Ata", "data_da_reuniao": "2999-01-01", "arquivo": _arquivo()},
        format="multipart",
    )
    cliente("admin").post(f"{BASE}/categorias/{categoria().id}/desativar/")
    inativa = cliente("envia").post(
        f"{BASE}/documentos/",
        {"titulo": "x", "categoria_id": str(categoria().id), "arquivo": _arquivo()},
        format="multipart",
    )

    assert (futura.status_code, _codigo(futura)) == (422, "DATA_FUTURA")
    assert (inativa.status_code, _codigo(inativa)) == (422, "CATEGORIA_INATIVA")


def test_download_da_vigente_e_de_versao_antiga_com_os_cabecalhos(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    documento = _documento(papeis)
    documentos.nova_versao(
        papeis["envia"].id, documento.id, arquivo=_arquivo(PNG, "n.png", "image/png"), motivo="m"
    )

    vigente = cliente("leitor").get(f"{BASE}/documentos/{documento.id}/arquivo/")
    antiga = cliente("leitor").get(f"{BASE}/documentos/{documento.id}/versoes/1/arquivo/")
    inexistente = cliente("leitor").get(f"{BASE}/documentos/{documento.id}/versoes/9/arquivo/")

    assert (vigente.status_code, bytes(vigente.content)) == (200, PNG)
    assert (antiga.status_code, bytes(antiga.content)) == (200, PDF)
    assert vigente["X-Content-Type-Options"] == "nosniff"
    assert vigente["Cache-Control"] == "private, no-store"
    assert vigente["Content-Disposition"].startswith("inline;")
    assert inexistente.status_code == 404


def test_o_arquivo_nao_tem_url_publica_nem_a_chave_aparece_na_saida(
    cliente: Cliente, papeis: dict[str, Usuario]
) -> None:
    documento = _documento(papeis)
    detalhe = cliente("leitor").get(f"{BASE}/documentos/{documento.id}/")

    assert "documentos/" not in detalhe.json()["arquivo"]["nome"]
    assert not re.search(r"documentos/[0-9a-f-]{36}\.", detalhe.content.decode())
    assert APIClient().get("/media/documentos/qualquer.pdf").status_code == 404
    assert cliente("leitor").get("/media/documentos/qualquer.pdf").status_code == 404


def test_download_exige_sessao_e_cargo(cliente: Cliente, papeis: dict[str, Usuario]) -> None:
    documento = _documento(papeis)
    rota = f"{BASE}/documentos/{documento.id}/arquivo/"

    assert APIClient().get(rota).status_code == 401
    assert cliente("sem_cargo").get(rota).status_code == 403
    assert cliente("admin").get(rota).status_code == 200


# --- categorias (CA-28) --------------------------------------------------------------------------------


def test_o_admin_cria_renomeia_desativa_e_reativa_e_o_leitor_so_ve_as_ativas(cliente: Cliente) -> None:
    criada = cliente("admin").post(f"{BASE}/categorias/", {"nome": "Jurídico"}, format="json")
    categoria_id = criada.json()["id"]
    renomeada = cliente("admin").post(
        f"{BASE}/categorias/{categoria_id}/editar/", {"nome": "Jurídico e contratos"}, format="json"
    )
    desativada = cliente("admin").post(f"{BASE}/categorias/{categoria_id}/desativar/")
    do_leitor = cliente("leitor").get(f"{BASE}/categorias/", {"todas": "1"}).json()
    do_admin = cliente("admin").get(f"{BASE}/categorias/", {"todas": "1"}).json()
    reativada = cliente("admin").post(f"{BASE}/categorias/{categoria_id}/reativar/")

    assert (criada.status_code, criada.json()["ativa"]) == (201, True)
    assert renomeada.json()["nome"] == "Jurídico e contratos"
    assert desativada.json()["ativa"] is False
    assert "Jurídico e contratos" not in [c["nome"] for c in do_leitor]
    assert "Jurídico e contratos" in [c["nome"] for c in do_admin]
    assert reativada.json()["ativa"] is True


def test_categoria_com_nome_repetido_e_409(cliente: Cliente) -> None:
    resposta = cliente("admin").post(f"{BASE}/categorias/", {"nome": "institucional"}, format="json")

    assert (resposta.status_code, _codigo(resposta)) == (409, "CATEGORIA_JA_EXISTE")


# --- paridade entre `acoes` e as rotas -----------------------------------------------------------------

Chamada = Callable[[APIClient, str], Any]


def _json(sufixo: str, corpo: dict[str, Any] | None = None) -> Chamada:
    def chamar(c: APIClient, base: str) -> Any:
        resposta: Any = c.post(f"{base}/{sufixo}", corpo or {}, format="json")
        return resposta

    return chamar


def _nova_versao(c: APIClient, base: str) -> Any:
    resposta: Any = c.post(f"{base}/versoes/", {"motivo": "m", "arquivo": _arquivo()}, format="multipart")
    return resposta


_COMANDOS_DO_COMUNICADO: dict[str, Chamada] = {
    "editar_comunicado": _json("editar/", {"titulo": "t", "texto": "x", "documentos_ids": []}),
    "despublicar": _json("despublicar/", {"motivo": "m"}),
    "republicar": _json("republicar/"),
    "fixar": _json("fixar/"),
    "desafixar": _json("desafixar/"),
    "reagir": _json("reacao/", {"tipo": "CIENTE"}),
    "retirar_reacao": _json("reacao/retirar/"),
    "comentar": _json("comentarios/", {"texto": "oi"}),
}


def _cenario(papeis: dict[str, Usuario], situacao: str) -> Comunicado:
    comunicado = _publicar(papeis)
    if situacao == "fixado":
        comunicados.fixar(papeis["gerente"].id, comunicado.id)
    if situacao == "despublicado":
        comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")
    return comunicado


@pytest.mark.parametrize("papel", ["autor", "gerente", "leitor", "admin"])
@pytest.mark.parametrize("situacao", ["publicado", "fixado", "despublicado"])
def test_as_acoes_do_comunicado_batem_com_o_que_as_rotas_aceitam(
    cliente: Cliente, papeis: dict[str, Usuario], papel: str, situacao: str
) -> None:
    resposta = cliente(papel).get(f"{BASE}/comunicados/{_cenario(papeis, situacao).id}/")
    if resposta.status_code == 404:
        assert papel == "leitor"
        assert situacao == "despublicado"
        return
    acoes = set(resposta.json()["acoes"])

    for comando, chamar in _COMANDOS_DO_COMUNICADO.items():
        fresco = _cenario(papeis, situacao)
        resultado = chamar(cliente(papel), f"{BASE}/comunicados/{fresco.id}")
        aceita = resultado.status_code not in (403, 422)
        assert aceita == (comando in acoes), (comando, resultado.status_code, sorted(acoes))


_COMANDOS_DO_DOCUMENTO: dict[str, Chamada] = {
    "arquivar": _json("arquivar/"),
    "desarquivar": _json("desarquivar/"),
    "nova_versao": _nova_versao,
}


@pytest.mark.parametrize("papel", ["envia", "gerente", "leitor", "atas", "admin"])
@pytest.mark.parametrize("situacao", ["vigente", "arquivado"])
def test_as_acoes_do_documento_batem_com_o_que_as_rotas_aceitam(
    cliente: Cliente, papeis: dict[str, Usuario], papel: str, situacao: str
) -> None:
    def novo() -> Any:
        criado = _documento(papeis)
        if situacao == "arquivado":
            documentos.arquivar(papeis["envia"].id, criado.id)
        return criado

    acoes = set(cliente(papel).get(f"{BASE}/documentos/{novo().id}/").json()["acoes"])

    for comando, chamar in _COMANDOS_DO_DOCUMENTO.items():
        resultado = chamar(cliente(papel), f"{BASE}/documentos/{novo().id}")
        aceita = resultado.status_code not in (403, 422)
        assert aceita == (comando in acoes), (comando, resultado.status_code, sorted(acoes))


_COMANDOS_DO_COMENTARIO: dict[str, Chamada] = {
    "editar_comentario": _json("editar/", {"texto": "novo"}),
    "ocultar_comentario": _json("ocultar/", {"motivo": "m"}),
    "reexibir_comentario": _json("reexibir/"),
}


@pytest.mark.parametrize("papel", ["leitor", "outro", "gerente", "admin"])
@pytest.mark.parametrize("situacao", ["visivel", "oculto_pelo_autor", "oculto_pela_gerencia"])
def test_as_acoes_do_comentario_batem_com_o_que_as_rotas_aceitam(
    cliente: Cliente, papeis: dict[str, Usuario], papel: str, situacao: str
) -> None:
    def novo() -> Any:
        comunicado = _publicar(papeis)
        comentario = comentarios.comentar(papeis["leitor"].id, comunicado.id, "oi")
        if situacao == "oculto_pelo_autor":
            comentarios.ocultar(papeis["leitor"].id, comentario.id)
        if situacao == "oculto_pela_gerencia":
            comentarios.ocultar(papeis["gerente"].id, comentario.id, "Motivo")
        return comunicado, comentario

    comunicado, comentario = novo()
    pagina = cliente(papel).get(f"{BASE}/comunicados/{comunicado.id}/comentarios/").json()
    visiveis = {c["id"]: c for c in pagina["itens"]}
    if str(comentario.id) not in visiveis:
        assert papel in ("outro", "admin") or situacao == "visivel"
        resposta = cliente(papel).post(f"{BASE}/comentarios/{comentario.id}/reexibir/")
        assert resposta.status_code in (403, 404)
        return
    acoes = set(visiveis[str(comentario.id)]["acoes"])

    for comando, chamar in _COMANDOS_DO_COMENTARIO.items():
        _, fresco = novo()
        resultado = chamar(cliente(papel), f"{BASE}/comentarios/{fresco.id}")
        aceita = resultado.status_code not in (403, 422)
        assert aceita == (comando in acoes), (comando, resultado.status_code, sorted(acoes))


# --- o esquema OpenAPI ---------------------------------------------------------------------------------


def test_o_esquema_openapi_traz_as_rotas_novas_so_para_o_admin(cliente: Cliente) -> None:
    sem_permissao = cliente("leitor").get("/api/v1/schema/", headers={"Accept": "application/json"})
    do_admin = cliente("admin").get("/api/v1/schema/", headers={"Accept": "application/json"})

    assert sem_permissao.status_code == 403
    caminhos = do_admin.json()["paths"]
    for esperado in (
        "/api/v1/comunicacao/comunicados/",
        "/api/v1/comunicacao/comunicados/{comunicado_id}/reacao/",
        "/api/v1/comunicacao/comentarios/{comentario_id}/ocultar/",
        "/api/v1/comunicacao/documentos/{documento_id}/versoes/{numero}/arquivo/",
        "/api/v1/comunicacao/categorias/{categoria_id}/desativar/",
    ):
        assert esperado in caminhos
