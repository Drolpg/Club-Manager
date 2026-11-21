"""Reações e comentários (CA-11 a CA-20). Banco real; os avisos são lidos pela caixa de entrada."""

import uuid
from typing import Any

import pytest

from comunicacao.models import Comentario, Comunicado, Reacao, VersaoDeComentario
from comunicacao.services import comentarios, comunicados, consulta, reacoes
from comunicacao.tests.conftest import acoes_de, caixa, registros_de
from kernel.errors import BusinessError
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

NOTIF = "comunicacao.comentario_novo"
ZERO = {"CIENTE": 0, "DE_ACORDO": 0, "DUVIDA": 0, "COMEMORACAO": 0}


@pytest.fixture
def comunicado(papeis: dict[str, Usuario]) -> Comunicado:
    return comunicados.publicar(
        papeis["autor"].id, tipo="COMUNICADO", titulo="Reunião", texto="Sábado, às 10h.", documentos_ids=[]
    )


def _codigo(excecao: pytest.ExceptionInfo[BusinessError]) -> str:
    return excecao.value.code


def _comentar(
    papeis: dict[str, Usuario], comunicado: Comunicado, quem: str = "leitor", texto: str = "Ciente."
) -> Comentario:
    return comentarios.comentar(papeis[quem].id, comunicado.id, texto)


def _textos(papeis: dict[str, Usuario], comunicado: Comunicado, quem: str) -> list[str]:
    pagina = consulta.comentarios(papeis[quem].id, comunicado.id)
    return [c["texto"] for c in pagina["itens"]]


def _ativas(comunicado: Comunicado) -> dict[Any, str]:
    ativas = Reacao.objects.filter(comunicado=comunicado, retirada_em__isnull=True)
    return {r.diretor_id: r.tipo for r in ativas}


# --- reações (CA-11, CA-12, CA-13) --------------------------------------------------------------------------


@pytest.mark.parametrize("tipo", ["CIENTE", "DE_ACORDO", "DUVIDA", "COMEMORACAO"])
def test_ca11_reagir_com_cada_um_dos_quatro_tipos(
    papeis: dict[str, Usuario], comunicado: Comunicado, tipo: str
) -> None:
    resultado = reacoes.reagir(papeis["leitor"].id, comunicado.id, tipo)

    assert resultado["minha"] == tipo
    assert resultado["contagem"] == {**ZERO, tipo: 1}
    assert [p["id"] for p in resultado["quem"][tipo]] == [papeis["leitor"].id]
    assert acoes_de("comunicado", comunicado.id)[-1] == "REACAO_REGISTRADA"


def test_ca11_o_comunicado_mostra_a_contagem_por_tipo_e_quem_reagiu(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    reacoes.reagir(papeis["leitor"].id, comunicado.id, "CIENTE")
    reacoes.reagir(papeis["outro"].id, comunicado.id, "CIENTE")
    reacoes.reagir(papeis["gerente"].id, comunicado.id, "DUVIDA")

    detalhe = consulta.detalhe(papeis["leitor"].id, comunicado.id)

    assert detalhe["reacoes"]["contagem"] == {**ZERO, "CIENTE": 2, "DUVIDA": 1}
    assert {p["nome"] for p in detalhe["reacoes"]["quem"]["CIENTE"]} == {
        papeis["leitor"].nome,
        papeis["outro"].nome,
    }
    assert [p["nome"] for p in detalhe["reacoes"]["quem"]["DUVIDA"]] == [papeis["gerente"].nome]
    assert detalhe["reacoes"]["minha"] == "CIENTE"


def test_ca11_tipo_fora_do_conjunto_e_recusado(papeis: dict[str, Usuario], comunicado: Comunicado) -> None:
    with pytest.raises(BusinessError) as erro:
        reacoes.reagir(papeis["leitor"].id, comunicado.id, "CURTIDA")

    assert _codigo(erro) == "VALIDATION_ERROR"
    assert "tipo" in erro.value.details
    assert not Reacao.objects.exists()


def test_ca11_quem_nao_tem_cargo_e_negado(papeis: dict[str, Usuario], comunicado: Comunicado) -> None:
    with pytest.raises(BusinessError) as erro:
        reacoes.reagir(papeis["sem_cargo"].id, comunicado.id, "CIENTE")

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ca11_o_autor_e_o_admin_tambem_reagem(papeis: dict[str, Usuario], comunicado: Comunicado) -> None:
    reacoes.reagir(papeis["autor"].id, comunicado.id, "COMEMORACAO")
    reacoes.reagir(papeis["admin"].id, comunicado.id, "CIENTE")

    assert set(_ativas(comunicado).values()) == {"COMEMORACAO", "CIENTE"}


def test_ca12_trocar_deixa_uma_reacao_so_e_audita_de_e_para(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    reacoes.reagir(papeis["leitor"].id, comunicado.id, "CIENTE")

    resultado = reacoes.reagir(papeis["leitor"].id, comunicado.id, "DUVIDA")

    assert resultado["contagem"] == {**ZERO, "DUVIDA": 1}
    assert Reacao.objects.filter(comunicado=comunicado, diretor_id=papeis["leitor"].id).count() == 1
    troca = registros_de("comunicado", comunicado.id, "REACAO_TROCADA")[0]
    assert troca.dados == {"de": "CIENTE", "para": "DUVIDA"}
    assert troca.ator_id == papeis["leitor"].id


def test_ca12_escolher_a_mesma_de_novo_retira(papeis: dict[str, Usuario], comunicado: Comunicado) -> None:
    reacoes.reagir(papeis["leitor"].id, comunicado.id, "CIENTE")

    resultado = reacoes.reagir(papeis["leitor"].id, comunicado.id, "CIENTE")

    assert resultado["contagem"] == ZERO
    assert resultado["minha"] is None
    assert acoes_de("comunicado", comunicado.id)[-1] == "REACAO_RETIRADA"


def test_ca12_retirar_sai_da_contagem_mas_a_linha_fica(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    reacoes.reagir(papeis["leitor"].id, comunicado.id, "DE_ACORDO")

    resultado = reacoes.retirar(papeis["leitor"].id, comunicado.id)

    assert resultado["contagem"] == ZERO
    reacao = Reacao.objects.get(comunicado=comunicado, diretor_id=papeis["leitor"].id)
    assert reacao.retirada_em is not None
    assert registros_de("comunicado", comunicado.id, "REACAO_RETIRADA")[0].dados == {"tipo": "DE_ACORDO"}


def test_ca12_reagir_de_novo_depois_de_retirar_reaproveita_a_linha(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    reacoes.reagir(papeis["leitor"].id, comunicado.id, "CIENTE")
    reacoes.retirar(papeis["leitor"].id, comunicado.id)

    resultado = reacoes.reagir(papeis["leitor"].id, comunicado.id, "DUVIDA")

    assert resultado["contagem"] == {**ZERO, "DUVIDA": 1}
    reacao = Reacao.objects.get(comunicado=comunicado, diretor_id=papeis["leitor"].id)
    assert reacao.retirada_em is None
    assert registros_de("comunicado", comunicado.id, "REACAO_REGISTRADA")[-1].dados == {"tipo": "DUVIDA"}


def test_ca12_retirar_sem_reacao_e_recusado(papeis: dict[str, Usuario], comunicado: Comunicado) -> None:
    with pytest.raises(BusinessError) as erro:
        reacoes.retirar(papeis["leitor"].id, comunicado.id)

    assert _codigo(erro) == "SEM_REACAO"


def test_ca12_nenhuma_reacao_gera_notificacao(papeis: dict[str, Usuario], comunicado: Comunicado) -> None:
    antes = len(caixa(papeis["autor"]))

    reacoes.reagir(papeis["leitor"].id, comunicado.id, "CIENTE")
    reacoes.reagir(papeis["leitor"].id, comunicado.id, "DUVIDA")
    reacoes.retirar(papeis["leitor"].id, comunicado.id)

    assert len(caixa(papeis["autor"])) == antes


def test_ca13_despublicado_recusa_e_republicado_devolve_a_contagem(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    reacoes.reagir(papeis["leitor"].id, comunicado.id, "CIENTE")
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    with pytest.raises(BusinessError) as ao_reagir:
        reacoes.reagir(papeis["autor"].id, comunicado.id, "DUVIDA")
    with pytest.raises(BusinessError) as ao_retirar:
        reacoes.retirar(papeis["autor"].id, comunicado.id)
    comunicados.republicar(papeis["autor"].id, comunicado.id)

    assert _codigo(ao_reagir) == "COMUNICADO_NAO_PUBLICADO"
    assert _codigo(ao_retirar) == "COMUNICADO_NAO_PUBLICADO"
    assert consulta.detalhe(papeis["leitor"].id, comunicado.id)["reacoes"]["contagem"] == {
        **ZERO,
        "CIENTE": 1,
    }


def test_reagir_em_comunicado_inexistente_ou_que_nao_se_ve(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    with pytest.raises(BusinessError) as inexistente:
        reacoes.reagir(papeis["leitor"].id, uuid.uuid4(), "CIENTE")
    with pytest.raises(BusinessError) as invisivel:
        reacoes.reagir(papeis["leitor"].id, comunicado.id, "CIENTE")

    assert _codigo(inexistente) == "NOT_FOUND"
    assert _codigo(invisivel) == "NOT_FOUND"


# --- comentar (CA-14, CA-15) --------------------------------------------------------------------------------


def test_ca14_comentar_aparece_com_autor_e_data_do_mais_antigo_ao_mais_novo(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    _comentar(papeis, comunicado, "leitor", "Primeiro")
    _comentar(papeis, comunicado, "outro", "Segundo")
    _comentar(papeis, comunicado, "gerente", "Terceiro")

    pagina = consulta.comentarios(papeis["leitor"].id, comunicado.id)

    assert [c["texto"] for c in pagina["itens"]] == ["Primeiro", "Segundo", "Terceiro"]
    primeiro = pagina["itens"][0]
    assert primeiro["autor"] == {"id": papeis["leitor"].id, "nome": papeis["leitor"].nome}
    assert primeiro["criado_em"] is not None
    assert primeiro["editado"] is False
    assert VersaoDeComentario.objects.filter(comentario_id=primeiro["id"], numero=1).exists()
    assert acoes_de("comentario", primeiro["id"]) == ["COMENTARIO_CRIADO"]


def test_ca14_a_listagem_e_paginada_do_mais_antigo(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    ids = [_comentar(papeis, comunicado, texto=f"c{n}").id for n in range(3)]

    primeira = consulta.comentarios(papeis["leitor"].id, comunicado.id, limite=2)
    segunda = consulta.comentarios(papeis["leitor"].id, comunicado.id, depois=ids[1], limite=2)

    assert [c["id"] for c in primeira["itens"]] == ids[:2]
    assert primeira["tem_mais"] is True
    assert [c["id"] for c in segunda["itens"]] == [ids[2]]
    assert segunda["tem_mais"] is False


def test_ca14_texto_vazio_despublicado_e_sem_cargo_sao_recusados(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    with pytest.raises(BusinessError) as vazio:
        comentarios.comentar(papeis["leitor"].id, comunicado.id, "   ")
    with pytest.raises(BusinessError) as sem_cargo:
        comentarios.comentar(papeis["sem_cargo"].id, comunicado.id, "Oi")
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")
    with pytest.raises(BusinessError) as despublicado:
        comentarios.comentar(papeis["autor"].id, comunicado.id, "Oi")

    assert _codigo(vazio) == "VALIDATION_ERROR"
    assert "texto" in vazio.value.details
    assert _codigo(sem_cargo) == "PERMISSION_DENIED"
    assert _codigo(despublicado) == "COMUNICADO_NAO_PUBLICADO"
    assert not Comentario.objects.exists()


def test_ca14_o_texto_do_comentario_e_guardado_como_veio(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    texto = '<script>alert("x")</script> & <b>negrito</b>'

    comentario = comentarios.comentar(papeis["leitor"].id, comunicado.id, texto)

    assert Comentario.objects.get(pk=comentario.pk).texto == texto


def test_ca15_o_autor_do_comunicado_e_avisado_de_cada_comentario(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    _comentar(papeis, comunicado, "leitor", "Primeiro")
    _comentar(papeis, comunicado, "leitor", "Segundo do mesmo")
    _comentar(papeis, comunicado, "outro", "De outro")

    avisos = caixa(papeis["autor"], NOTIF)

    assert len(avisos) == 3
    assert all(a["caminho"] == f"/feed/{comunicado.id}" for a in avisos)
    assert all(a["pede_acao"] is False for a in avisos)


def test_ca15_quem_ja_comentou_e_os_outros_nao_sao_avisados(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    _comentar(papeis, comunicado, "leitor", "Primeiro")
    _comentar(papeis, comunicado, "outro", "Segundo")

    for quem in ("leitor", "outro", "gerente", "envia"):
        assert caixa(papeis[quem], NOTIF) == [], quem


def test_ca15_o_autor_comentando_no_proprio_comunicado_nao_avisa_a_si(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    _comentar(papeis, comunicado, "autor", "Esclarecendo")

    assert caixa(papeis["autor"], NOTIF) == []


def test_ca15_o_aviso_leva_o_titulo_e_o_nome_e_nunca_o_texto_do_comentario(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    _comentar(papeis, comunicado, "leitor", "Conteúdo sigiloso do comentário")

    aviso = caixa(papeis["autor"], NOTIF)[0]
    texto = aviso["titulo"] + " " + aviso["texto"]

    assert "Reunião" in texto
    assert papeis["leitor"].nome in texto
    assert "sigiloso" not in texto


@pytest.mark.sem_atalho_de_commit
def test_ca15_o_email_do_comentario_so_e_enfileirado_depois_do_commit(
    papeis: dict[str, Usuario], comunicado: Comunicado, django_capture_on_commit_callbacks: Any
) -> None:
    with django_capture_on_commit_callbacks(execute=False) as pendentes:
        _comentar(papeis, comunicado, "leitor")

    assert pendentes


# --- editar o próprio comentário (CA-16) --------------------------------------------------------------------


def test_ca16_o_autor_edita_com_versao_nova_e_sem_aviso(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado, texto="Texto original")
    avisos_antes = len(caixa(papeis["autor"], NOTIF))

    editado = comentarios.editar(papeis["leitor"].id, comentario.id, "Texto corrigido")

    assert editado.texto == "Texto corrigido"
    assert editado.editado_em is not None
    versoes = VersaoDeComentario.objects.filter(comentario=comentario).order_by("numero")
    assert [(v.numero, v.texto) for v in versoes] == [(1, "Texto original"), (2, "Texto corrigido")]
    registro = registros_de("comentario", comentario.id, "COMENTARIO_EDITADO")[0]
    assert registro.dados["versao_anterior"] == 1
    assert registro.dados["versao_nova"] == 2
    assert "Texto" not in str(registro.dados)
    assert len(caixa(papeis["autor"], NOTIF)) == avisos_antes
    item = consulta.comentarios(papeis["outro"].id, comunicado.id)["itens"][0]
    assert item["editado"] is True


def test_ca16_outra_pessoa_inclusive_quem_gerencia_e_negada(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado)

    for quem in ("gerente", "autor", "outro", "admin"):
        with pytest.raises(BusinessError) as erro:
            comentarios.editar(papeis[quem].id, comentario.id, "Adulterado")
        assert _codigo(erro) == "PERMISSION_DENIED", quem
    assert Comentario.objects.get(pk=comentario.pk).texto == "Ciente."


def test_ca16_edicao_invalida_ou_com_o_comunicado_despublicado(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado)
    with pytest.raises(BusinessError) as vazio:
        comentarios.editar(papeis["leitor"].id, comentario.id, "")
    with pytest.raises(BusinessError) as inexistente:
        comentarios.editar(papeis["leitor"].id, uuid.uuid4(), "x")
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")
    with pytest.raises(BusinessError) as despublicado:
        comentarios.editar(papeis["leitor"].id, comentario.id, "x")

    assert _codigo(vazio) == "VALIDATION_ERROR"
    assert _codigo(inexistente) == "NOT_FOUND"
    # O comunicado despublicado nem aparece para quem só comentou nele.
    assert _codigo(despublicado) == "NOT_FOUND"


# --- ocultar e reexibir (CA-17, CA-18, CA-19) ---------------------------------------------------------------


def test_ca17_o_autor_oculta_o_proprio_e_o_oculto_some_dos_demais(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    _comentar(papeis, comunicado, "outro", "Fica")
    comentario = _comentar(papeis, comunicado, "leitor", "Some")

    comentarios.ocultar(papeis["leitor"].id, comentario.id)

    assert _textos(papeis, comunicado, "outro") == ["Fica"]
    assert _textos(papeis, comunicado, "autor") == ["Fica"]
    assert _textos(papeis, comunicado, "leitor") == ["Fica", "Some"]
    assert _textos(papeis, comunicado, "gerente") == ["Fica", "Some"]
    assert _textos(papeis, comunicado, "admin") == ["Fica", "Some"]
    contagem = consulta.feed(papeis["outro"].id)["itens"][0]["total_de_comentarios"]
    assert contagem == 1
    marcado = next(
        c for c in consulta.comentarios(papeis["leitor"].id, comunicado.id)["itens"] if c["texto"] == "Some"
    )
    assert marcado["situacao"] == "OCULTO"
    assert marcado["oculto"]["pela_gerencia"] is False
    registro = registros_de("comentario", comentario.id, "COMENTARIO_OCULTADO")[0]
    assert registro.dados["pela_gerencia"] is False


def test_ca17_o_autor_reexibe_o_que_ele_mesmo_ocultou(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado, texto="Some e volta")
    comentarios.ocultar(papeis["leitor"].id, comentario.id)

    reexibido = comentarios.reexibir(papeis["leitor"].id, comentario.id)

    assert reexibido.situacao == "VISIVEL"
    assert reexibido.oculto_pela_gerencia is False
    assert _textos(papeis, comunicado, "outro") == ["Some e volta"]
    assert acoes_de("comentario", comentario.id)[-1] == "COMENTARIO_REEXIBIDO"


def test_ca17_ocultar_o_que_ja_esta_oculto_e_reexibir_o_que_nao_esta(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado)
    with pytest.raises(BusinessError) as nao_oculto:
        comentarios.reexibir(papeis["leitor"].id, comentario.id)
    comentarios.ocultar(papeis["leitor"].id, comentario.id)
    with pytest.raises(BusinessError) as ja_oculto:
        comentarios.ocultar(papeis["leitor"].id, comentario.id)

    assert _codigo(nao_oculto) == "COMENTARIO_NAO_ESTA_OCULTO"
    assert _codigo(ja_oculto) == "COMENTARIO_JA_OCULTO"


def test_ca18_quem_gerencia_oculta_com_motivo_visivel_a_quem_ve_oculto(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado, texto="Ofensivo")

    ocultado = comentarios.ocultar(papeis["gerente"].id, comentario.id, "Linguagem ofensiva")

    assert ocultado.situacao == "OCULTO"
    assert ocultado.oculto_pela_gerencia is True
    assert ocultado.oculto_por_id == papeis["gerente"].id
    assert _textos(papeis, comunicado, "outro") == []
    visto_pelo_autor = consulta.comentarios(papeis["leitor"].id, comunicado.id)["itens"][0]
    assert visto_pelo_autor["oculto"]["motivo"] == "Linguagem ofensiva"
    assert visto_pelo_autor["oculto"]["pela_gerencia"] is True
    registro = registros_de("comentario", comentario.id, "COMENTARIO_OCULTADO")[0]
    assert registro.justificativa == "Linguagem ofensiva"
    assert registro.ator_id == papeis["gerente"].id


def test_ca18_sem_motivo_e_recusado_e_sem_a_permissao_e_negado_inclusive_o_autor_do_comunicado(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado, "leitor")
    with pytest.raises(BusinessError) as sem_motivo:
        comentarios.ocultar(papeis["gerente"].id, comentario.id, "  ")
    with pytest.raises(BusinessError) as autor_do_comunicado:
        comentarios.ocultar(papeis["autor"].id, comentario.id, "Não gostei")
    with pytest.raises(BusinessError) as outro:
        comentarios.ocultar(papeis["outro"].id, comentario.id, "Não gostei")

    assert _codigo(sem_motivo) == "VALIDATION_ERROR"
    assert "motivo" in sem_motivo.value.details
    assert _codigo(autor_do_comunicado) == "PERMISSION_DENIED"
    assert _codigo(outro) == "PERMISSION_DENIED"
    assert Comentario.objects.get(pk=comentario.pk).situacao == "VISIVEL"


def test_ca18_quem_gerencia_oculta_tambem_com_o_comunicado_despublicado(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado)
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    comentarios.ocultar(papeis["gerente"].id, comentario.id, "Moderação")

    assert Comentario.objects.get(pk=comentario.pk).situacao == "OCULTO"


def test_ca19_o_autor_nao_reexibe_o_que_a_gerencia_ocultou_so_a_gerencia(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado)
    comentarios.ocultar(papeis["gerente"].id, comentario.id, "Moderação")

    with pytest.raises(BusinessError) as autor:
        comentarios.reexibir(papeis["leitor"].id, comentario.id)
    with pytest.raises(BusinessError) as outro:
        comentarios.reexibir(papeis["outro"].id, comentario.id)
    comentarios.reexibir(papeis["admin"].id, comentario.id)

    assert _codigo(autor) == "PERMISSION_DENIED"
    assert _codigo(outro) == "NOT_FOUND"  # quem não pode ver o oculto não sabe que ele existe
    assert Comentario.objects.get(pk=comentario.pk).situacao == "VISIVEL"
    # O motivo da ocultação fica na auditoria, ao lado do ato de reexibir.
    assert registros_de("comentario", comentario.id, "COMENTARIO_OCULTADO")[0].justificativa == "Moderação"


def test_ca19_nenhum_comentario_e_apagado_e_as_acoes_do_comentario_seguem_o_papel(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    comentario = _comentar(papeis, comunicado)

    def acoes(quem: str) -> list[str]:
        itens = consulta.comentarios(papeis[quem].id, comunicado.id)["itens"]
        return list(itens[0]["acoes"])

    assert acoes("leitor") == ["editar_comentario", "ocultar_comentario"]
    assert acoes("gerente") == ["ocultar_comentario"]
    assert acoes("outro") == []
    comentarios.ocultar(papeis["gerente"].id, comentario.id, "Moderação")
    assert acoes("gerente") == ["reexibir_comentario"]
    # O autor ainda edita o que a gerência ocultou, mas não o reexibe: segue oculto.
    assert acoes("leitor") == ["editar_comentario"]
    assert Comentario.objects.filter(pk=comentario.pk).exists()


# --- o comunicado despublicado (CA-20) ----------------------------------------------------------------------


def test_ca20_despublicado_preserva_os_comentarios_e_republicado_devolve(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    _comentar(papeis, comunicado, texto="Fica guardado")
    comunicados.despublicar(papeis["autor"].id, comunicado.id, motivo="Erro")

    with pytest.raises(BusinessError) as para_quem_nao_ve:
        consulta.comentarios(papeis["leitor"].id, comunicado.id)
    guardado_para_quem_ve = _textos(papeis, comunicado, "gerente")
    comunicados.republicar(papeis["autor"].id, comunicado.id)

    assert _codigo(para_quem_nao_ve) == "NOT_FOUND"
    assert guardado_para_quem_ve == ["Fica guardado"]
    assert _textos(papeis, comunicado, "outro") == ["Fica guardado"]
    assert Comentario.objects.filter(comunicado=comunicado).count() == 1


def test_a_lista_de_comentarios_exige_leitura_de_gestao_e_comunicado_existente(
    papeis: dict[str, Usuario], comunicado: Comunicado
) -> None:
    with pytest.raises(BusinessError) as sem_cargo:
        consulta.comentarios(papeis["sem_cargo"].id, comunicado.id)
    with pytest.raises(BusinessError) as inexistente:
        consulta.comentarios(papeis["leitor"].id, uuid.uuid4())

    assert _codigo(sem_cargo) == "PERMISSION_DENIED"
    assert _codigo(inexistente) == "NOT_FOUND"
