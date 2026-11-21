"""Comunicados: publicar, editar, fixar, despublicar, republicar, o feed e o aviso (CA-02 a CA-10).

Banco real; as notificações são lidas pela caixa de entrada. A auditoria de cada ação é conferida nos testes.
"""

import uuid
from typing import Any

import pytest

from auditoria import public as auditoria
from comunicacao.models import Comentario, Comunicado, Reacao, VersaoDeComunicado, VinculoDeDocumento
from comunicacao.services import comunicados, consulta
from comunicacao.tests.conftest import acoes_de, caixa, documento, recarregado, registros_de
from kernel.errors import BusinessError
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

NOTIF = "comunicacao.comunicado_publicado"


def _publicar(papeis: dict[str, Usuario], **mudar: Any) -> Comunicado:
    dados: dict[str, Any] = {
        "tipo": "COMUNICADO",
        "titulo": "Reunião de sábado",
        "texto": "Sábado, às 10h, na sede.",
        "documentos_ids": [],
    }
    dados.update(mudar)
    return comunicados.publicar(papeis["autor"].id, **dados)


def _codigo(excecao: pytest.ExceptionInfo[BusinessError]) -> str:
    return excecao.value.code


# --- publicar (CA-03, CA-04) --------------------------------------------------------------------------------


def test_ca03_publicar_comunicado_e_pauta(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    pauta = _publicar(papeis, tipo="PAUTA", titulo="Pauta de novembro", texto="1. Orçamento")

    assert comunicado.situacao == "PUBLICADO"
    assert comunicado.autor_id == papeis["autor"].id
    assert comunicado.publicado_em is not None
    assert comunicado.versao == 1
    assert pauta.tipo == "PAUTA"
    assert VersaoDeComunicado.objects.get(comunicado=comunicado).numero == 1
    assert acoes_de("comunicado", comunicado.id) == ["COMUNICADO_PUBLICADO"]


def test_ca03_o_texto_e_guardado_como_veio(papeis: dict[str, Usuario]) -> None:
    texto = '<script>alert("x")</script>\n  linha com <b>html</b> & espaços  '

    comunicado = _publicar(papeis, texto=texto, titulo="<i>título</i>")

    comunicado.refresh_from_db()
    assert comunicado.texto == texto
    assert comunicado.titulo == "<i>título</i>"


@pytest.mark.parametrize("quem", ["leitor", "gerente", "sem_cargo"])
def test_ca03_sem_a_permissao_de_publicar_e_negado(papeis: dict[str, Usuario], quem: str) -> None:
    with pytest.raises(BusinessError) as erro:
        comunicados.publicar(papeis[quem].id, tipo="COMUNICADO", titulo="x", texto="y", documentos_ids=[])

    assert _codigo(erro) == "PERMISSION_DENIED"
    assert not Comunicado.objects.exists()


def test_ca03_o_admin_publica_pelo_acesso_total(papeis: dict[str, Usuario]) -> None:
    comunicado = comunicados.publicar(
        papeis["admin"].id, tipo="COMUNICADO", titulo="Aviso", texto="Do admin", documentos_ids=[]
    )

    assert comunicado.autor_id == papeis["admin"].id


def test_ca04_comunicado_invalido_e_recusado_por_campo(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        comunicados.publicar(papeis["autor"].id, tipo="NOTICIA", titulo=" ", texto="", documentos_ids=[])

    assert _codigo(erro) == "VALIDATION_ERROR"
    assert set(erro.value.details) == {"tipo", "titulo", "texto"}
    assert not Comunicado.objects.exists()


# --- a notificação (CA-05) ----------------------------------------------------------------------------------


def test_ca05_os_diretores_com_cargo_menos_o_autor_sao_notificados_uma_vez(
    papeis: dict[str, Usuario],
) -> None:
    comunicado = _publicar(papeis)

    for quem in ("leitor", "outro", "gerente", "envia", "atas"):
        itens = caixa(papeis[quem], NOTIF)
        assert len(itens) == 1, quem
        assert itens[0]["caminho"] == f"/feed/{comunicado.id}"
    for quem in ("autor", "sem_cargo", "admin"):
        assert caixa(papeis[quem], NOTIF) == [], quem


def test_ca05_a_notificacao_leva_o_titulo_e_nao_o_texto(papeis: dict[str, Usuario]) -> None:
    _publicar(papeis, titulo="Eleição da diretoria", texto="Segredo do texto inteiro")

    item = caixa(papeis["leitor"], NOTIF)[0]

    assert "Eleição da diretoria" in item["titulo"] + item["texto"]
    assert "Segredo do texto inteiro" not in item["titulo"] + item["texto"]
    assert item["pede_acao"] is False


def test_ca05_republicar_nao_notifica_de_novo(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro de data")

    comunicados.republicar(papeis["autor"].id, comunicado.id)

    assert len(caixa(papeis["leitor"], NOTIF)) == 1


@pytest.mark.sem_atalho_de_commit
def test_ca05_o_email_so_e_enfileirado_depois_do_commit(
    papeis: dict[str, Usuario], django_capture_on_commit_callbacks: Any
) -> None:
    with django_capture_on_commit_callbacks(execute=False) as pendentes:
        _publicar(papeis)

    assert pendentes, "a publicação agenda os e-mails para depois do commit"


# --- editar (CA-06) -----------------------------------------------------------------------------------------


def test_ca06_editar_cria_a_versao_marca_editado_e_nao_notifica(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis, texto="Texto original")
    antes = len(caixa(papeis["leitor"]))

    editado = comunicados.editar(
        papeis["autor"].id, comunicado.id, titulo="Reunião de domingo", texto="Texto novo", documentos_ids=[]
    )

    assert editado.situacao == "PUBLICADO"
    assert editado.versao == 2
    assert editado.editado_em is not None
    assert editado.titulo == "Reunião de domingo"
    versoes = list(VersaoDeComunicado.objects.filter(comunicado=comunicado).order_by("numero"))
    assert [(v.numero, v.texto) for v in versoes] == [(1, "Texto original"), (2, "Texto novo")]
    assert len(caixa(papeis["leitor"])) == antes


def test_ca06_a_auditoria_leva_os_numeros_das_versoes_e_nunca_o_texto(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis, texto="Texto original")

    comunicados.editar(
        papeis["autor"].id, comunicado.id, titulo="Reunião", texto="Texto novo", documentos_ids=[]
    )

    registro = registros_de("comunicado", comunicado.id, "COMUNICADO_EDITADO")[0]
    assert registro.ator_id == papeis["autor"].id
    assert registro.dados["versao_anterior"] == 1
    assert registro.dados["versao_nova"] == 2
    assert "Texto" not in str(registro.dados)


def test_ca06_terceiro_sem_gerenciar_e_negado_inclusive_quem_so_publica(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    outra_autora = papeis["envia"]
    apoio.conceder(outra_autora, "comunicacao.publicar")

    for quem in (papeis["leitor"], outra_autora):
        with pytest.raises(BusinessError) as erro:
            comunicados.editar(quem.id, comunicado.id, titulo="x", texto="y", documentos_ids=[])
        assert _codigo(erro) == "PERMISSION_DENIED"
    assert recarregado(comunicado).versao == 1


def test_ca06_autor_sem_a_permissao_de_publicar_e_negado(papeis: dict[str, Usuario]) -> None:
    """Quem escreveu o comunicado mas já não tem a permissão (o `leitor` aqui) não o edita."""
    comunicado = Comunicado.objects.create(
        tipo="COMUNICADO", titulo="Antigo", texto="Texto", autor_id=papeis["leitor"].id
    )

    with pytest.raises(BusinessError) as ao_editar:
        comunicados.editar(papeis["leitor"].id, comunicado.id, titulo="x", texto="y", documentos_ids=[])
    with pytest.raises(BusinessError) as ao_despublicar:
        comunicados.despublicar(papeis["leitor"].id, comunicado.id, motivo="Erro")

    assert _codigo(ao_editar) == "PERMISSION_DENIED"
    assert _codigo(ao_despublicar) == "PERMISSION_DENIED"


def test_ca06_editar_com_dados_invalidos_e_em_comunicado_despublicado(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    with pytest.raises(BusinessError) as invalido:
        comunicados.editar(papeis["autor"].id, comunicado.id, titulo="", texto="y", documentos_ids=[])
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Duplicado")
    with pytest.raises(BusinessError) as despublicado:
        comunicados.editar(papeis["autor"].id, comunicado.id, titulo="x", texto="y", documentos_ids=[])

    assert _codigo(invalido) == "VALIDATION_ERROR"
    assert _codigo(despublicado) == "COMUNICADO_NAO_PUBLICADO"


def test_editar_comunicado_inexistente(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        comunicados.editar(papeis["autor"].id, uuid.uuid4(), titulo="x", texto="y", documentos_ids=[])

    assert _codigo(erro) == "NOT_FOUND"


# --- gerenciar, fixar e despublicar (CA-07, CA-08, CA-09) ---------------------------------------------------


def test_ca07_quem_gerencia_edita_e_despublica_comunicado_de_outro(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)

    comunicados.editar(papeis["gerente"].id, comunicado.id, titulo="Ajustado", texto="Ok", documentos_ids=[])
    comunicados.despublicar(papeis["gerente"].id, comunicado.id, motivo="Fora de época")

    assert recarregado(comunicado).situacao == "DESPUBLICADO"
    assert acoes_de("comunicado", comunicado.id) == [
        "COMUNICADO_PUBLICADO",
        "COMUNICADO_EDITADO",
        "COMUNICADO_DESPUBLICADO",
    ]


def test_ca07_fixar_e_desafixar_so_com_gerenciar_nem_o_autor(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)

    for quem in ("autor", "leitor"):
        with pytest.raises(BusinessError) as erro:
            comunicados.fixar(papeis[quem].id, comunicado.id)
        assert _codigo(erro) == "PERMISSION_DENIED"

    comunicados.fixar(papeis["gerente"].id, comunicado.id)
    assert recarregado(comunicado).fixado_em is not None
    comunicados.desafixar(papeis["gerente"].id, comunicado.id)
    assert recarregado(comunicado).fixado_em is None
    assert acoes_de("comunicado", comunicado.id)[1:] == ["COMUNICADO_FIXADO", "COMUNICADO_DESAFIXADO"]


def test_fixar_duas_vezes_e_desafixar_o_que_nao_esta_fixado(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    with pytest.raises(BusinessError) as nao_fixado:
        comunicados.desafixar(papeis["gerente"].id, comunicado.id)
    comunicados.fixar(papeis["gerente"].id, comunicado.id)
    with pytest.raises(BusinessError) as ja_fixado:
        comunicados.fixar(papeis["gerente"].id, comunicado.id)

    assert _codigo(nao_fixado) == "NAO_ESTA_FIXADO"
    assert _codigo(ja_fixado) == "JA_ESTA_FIXADO"


def test_ca08_despublicar_tira_do_feed_e_a_fixacao(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    comunicados.fixar(papeis["gerente"].id, comunicado.id)

    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Data errada")

    recarregado_ = recarregado(comunicado)
    assert recarregado_.situacao == "DESPUBLICADO"
    assert recarregado_.fixado_em is None
    assert recarregado_.motivo_da_despublicacao == "Data errada"
    feed = consulta.feed(papeis["leitor"].id)
    assert feed["fixados"] == []
    assert feed["itens"] == []
    acoes = acoes_de("comunicado", comunicado.id)
    assert "COMUNICADO_DESAFIXADO" in acoes
    assert "COMUNICADO_DESPUBLICADO" in acoes
    registro = registros_de("comunicado", comunicado.id, "COMUNICADO_DESPUBLICADO")[0]
    assert registro.justificativa == "Data errada"


def test_ca08_despublicar_sem_motivo_e_recusado(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)

    with pytest.raises(BusinessError) as erro:
        comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="  ")

    assert _codigo(erro) == "VALIDATION_ERROR"
    assert "motivo" in erro.value.details
    assert recarregado(comunicado).situacao == "PUBLICADO"


def test_ca08_a_lista_de_despublicados_e_por_papel(papeis: dict[str, Usuario]) -> None:
    dele = _publicar(papeis)
    comunicados.despublicar(papeis["autor"].id, dele.id, motivo="Erro")
    outra_autora = papeis["envia"]
    apoio.conceder(outra_autora, "comunicacao.publicar")
    de_outra = comunicados.publicar(
        outra_autora.id, tipo="PAUTA", titulo="Outra", texto="Texto", documentos_ids=[]
    )
    comunicados.despublicar(outra_autora.id, de_outra.id, motivo="Outro erro")

    def ids(quem: str) -> set[str]:
        return {str(i["id"]) for i in consulta.despublicados(papeis[quem].id)["itens"]}

    assert ids("autor") == {str(dele.id)}
    assert ids("gerente") == {str(dele.id), str(de_outra.id)}
    assert ids("admin") == {str(dele.id), str(de_outra.id)}
    assert ids("leitor") == set()
    item = consulta.despublicados(papeis["gerente"].id)["itens"][0]
    assert item["despublicado"]["motivo"] in {"Erro", "Outro erro"}


def test_ca08_o_detalhe_do_despublicado_so_para_quem_pode_ver(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    assert consulta.detalhe(papeis["autor"].id, comunicado.id)["situacao"] == "DESPUBLICADO"
    assert consulta.detalhe(papeis["gerente"].id, comunicado.id)["situacao"] == "DESPUBLICADO"
    with pytest.raises(BusinessError) as erro:
        consulta.detalhe(papeis["leitor"].id, comunicado.id)
    assert _codigo(erro) == "NOT_FOUND"


def test_ca09_republicar_volta_ao_feed_sem_fixacao_e_sem_aviso(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    comunicados.fixar(papeis["gerente"].id, comunicado.id)
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    comunicados.republicar(papeis["autor"].id, comunicado.id)

    voltou = recarregado(comunicado)
    assert voltou.situacao == "PUBLICADO"
    assert voltou.fixado_em is None
    assert voltou.motivo_da_despublicacao == ""
    assert [i["id"] for i in consulta.feed(papeis["leitor"].id)["itens"]] == [comunicado.id]
    assert acoes_de("comunicado", comunicado.id)[-1] == "COMUNICADO_REPUBLICADO"
    assert len(caixa(papeis["leitor"], NOTIF)) == 1


def test_despublicar_duas_vezes_e_republicar_o_que_esta_publicado(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    with pytest.raises(BusinessError) as publicado:
        comunicados.republicar(papeis["autor"].id, comunicado.id)
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")
    with pytest.raises(BusinessError) as despublicado:
        comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    assert _codigo(publicado) == "COMUNICADO_JA_PUBLICADO"
    assert _codigo(despublicado) == "COMUNICADO_JA_DESPUBLICADO"


# --- documentos vinculados (CA-10) --------------------------------------------------------------------------


def test_ca10_vincular_documentos_vigentes_e_mostra_no_feed(papeis: dict[str, Usuario]) -> None:
    estatuto = documento("Estatuto")
    ata = documento("Ata de outubro", ata=True)

    comunicado = _publicar(papeis, documentos_ids=[estatuto.id, ata.id])

    item = consulta.detalhe(papeis["leitor"].id, comunicado.id)
    assert {d["titulo"]: (d["tipo"], d["situacao"]) for d in item["documentos"]} == {
        "Estatuto": ("DOCUMENTO", "VIGENTE"),
        "Ata de outubro": ("ATA", "VIGENTE"),
    }
    assert VinculoDeDocumento.objects.filter(comunicado=comunicado, desvinculado_em__isnull=True).count() == 2


def test_ca10_documento_arquivado_ou_inexistente_nao_se_vincula(papeis: dict[str, Usuario]) -> None:
    arquivado = documento("Antigo", arquivado=True)

    for ids in ([arquivado.id], [uuid.uuid4()]):
        with pytest.raises(BusinessError) as erro:
            _publicar(papeis, documentos_ids=ids)
        assert _codigo(erro) == "VALIDATION_ERROR"
        assert "documentos_ids" in erro.value.details
    assert not Comunicado.objects.exists()


def test_ca10_editar_recalcula_os_vinculos_sem_apagar(papeis: dict[str, Usuario]) -> None:
    primeiro, segundo = documento("Primeiro"), documento("Segundo")
    comunicado = _publicar(papeis, documentos_ids=[primeiro.id])

    comunicados.editar(papeis["autor"].id, comunicado.id, titulo="x", texto="y", documentos_ids=[segundo.id])

    ativos = VinculoDeDocumento.objects.filter(comunicado=comunicado, desvinculado_em__isnull=True)
    assert [v.documento_id for v in ativos] == [segundo.id]
    assert VinculoDeDocumento.objects.filter(comunicado=comunicado, documento=primeiro).exists()
    assert VinculoDeDocumento.objects.get(comunicado=comunicado, documento=primeiro).desvinculado_em
    registro = registros_de("comunicado", comunicado.id, "COMUNICADO_EDITADO")[0]
    assert registro.dados["documentos_vinculados"] == [str(segundo.id)]
    assert registro.dados["documentos_desvinculados"] == [str(primeiro.id)]


def test_ca10_documento_arquivado_depois_continua_vinculado(papeis: dict[str, Usuario]) -> None:
    estatuto = documento("Estatuto")
    comunicado = _publicar(papeis, documentos_ids=[estatuto.id])
    estatuto.situacao = "ARQUIVADO"
    estatuto.save()

    item = consulta.detalhe(papeis["leitor"].id, comunicado.id)

    assert [(d["titulo"], d["situacao"]) for d in item["documentos"]] == [("Estatuto", "ARQUIVADO")]


# --- o feed (CA-02) -----------------------------------------------------------------------------------------


def test_ca02_o_feed_traz_os_fixados_primeiro_e_so_na_primeira_pagina(papeis: dict[str, Usuario]) -> None:
    velho = _publicar(papeis, titulo="Velho")
    meio = _publicar(papeis, titulo="Meio")
    novo = _publicar(papeis, titulo="Novo")
    fixado_antes = _publicar(papeis, titulo="Fixado antes")
    fixado_depois = _publicar(papeis, titulo="Fixado depois")
    comunicados.fixar(papeis["gerente"].id, fixado_antes.id)
    comunicados.fixar(papeis["gerente"].id, fixado_depois.id)

    primeira = consulta.feed(papeis["leitor"].id, limite=2)

    assert [i["id"] for i in primeira["fixados"]] == [fixado_depois.id, fixado_antes.id]
    assert [i["id"] for i in primeira["itens"]] == [novo.id, meio.id]
    assert primeira["tem_mais"] is True
    segunda = consulta.feed(papeis["leitor"].id, antes=meio.id, limite=2)
    assert segunda["fixados"] == []
    assert [i["id"] for i in segunda["itens"]] == [velho.id]
    assert segunda["tem_mais"] is False


def test_ca02_o_feed_nao_traz_despublicados_e_o_cursor_invalido_e_recusado(
    papeis: dict[str, Usuario],
) -> None:
    _publicar(papeis, titulo="Fica")
    sai = _publicar(papeis, titulo="Sai")
    comunicados.despublicar(papeis["autor"].id, sai.id, motivo="Erro")

    titulos = [i["titulo"] for i in consulta.feed(papeis["leitor"].id)["itens"]]
    with pytest.raises(BusinessError) as erro:
        consulta.feed(papeis["leitor"].id, antes=uuid.uuid4())

    assert titulos == ["Fica"]
    assert _codigo(erro) == "NOT_FOUND"


def test_ca02_o_feed_e_negado_a_quem_nao_tem_cargo(papeis: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        consulta.feed(papeis["sem_cargo"].id)

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ca02_cada_item_traz_autor_contagens_e_acoes(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    Reacao.objects.create(comunicado=comunicado, diretor_id=papeis["leitor"].id, tipo="CIENTE")
    Reacao.objects.create(comunicado=comunicado, diretor_id=papeis["outro"].id, tipo="CIENTE")
    Reacao.objects.create(comunicado=comunicado, diretor_id=papeis["gerente"].id, tipo="DUVIDA")
    retirada = Reacao.objects.create(comunicado=comunicado, diretor_id=papeis["envia"].id, tipo="DUVIDA")
    retirada.retirada_em = comunicado.criado_em
    retirada.save()
    Comentario.objects.create(comunicado=comunicado, autor_id=papeis["leitor"].id, texto="Ciente.")
    Comentario.objects.create(
        comunicado=comunicado,
        autor_id=papeis["outro"].id,
        texto="Oculto",
        situacao="OCULTO",
        oculto_por_id=papeis["outro"].id,
    )

    item = consulta.feed(papeis["leitor"].id)["itens"][0]

    assert item["autor"] == {"id": papeis["autor"].id, "nome": papeis["autor"].nome}
    assert item["reacoes"]["contagem"] == {"CIENTE": 2, "DE_ACORDO": 0, "DUVIDA": 1, "COMEMORACAO": 0}
    assert item["reacoes"]["minha"] == "CIENTE"
    assert item["total_de_comentarios"] == 1
    assert item["acoes"] == ["reagir", "retirar_reacao", "comentar"]
    assert item["editado"] is False
    assert item["fixado"] is False


def test_as_acoes_do_detalhe_por_papel(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)

    def acoes(quem: str) -> list[str]:
        return list(consulta.detalhe(papeis[quem].id, comunicado.id)["acoes"])

    assert acoes("autor") == ["editar_comunicado", "despublicar", "reagir", "comentar"]
    assert acoes("gerente") == ["editar_comunicado", "despublicar", "fixar", "reagir", "comentar"]
    assert acoes("leitor") == ["reagir", "comentar"]


def test_cada_acao_gera_um_registro_de_auditoria_com_ator(papeis: dict[str, Usuario]) -> None:
    comunicado = _publicar(papeis)
    comunicados.fixar(papeis["gerente"].id, comunicado.id)

    registros = auditoria.historico_do_item("comunicado", comunicado.id)

    assert [(r.acao, r.ator_id) for r in registros] == [
        ("COMUNICADO_PUBLICADO", papeis["autor"].id),
        ("COMUNICADO_FIXADO", papeis["gerente"].id),
    ]
