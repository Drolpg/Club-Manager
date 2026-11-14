"""Motivos de decisão: lista sugerida, manutenção pelo admin e a cópia do texto na decisão (CA-29 a CA-31)."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.test import APIClient

from aprovacoes import public, tipos
from aprovacoes.models import Decisao, MotivoDeDecisao, Solicitacao, Versao
from auditoria import public as auditoria
from kernel.errors import BusinessError

pytestmark = pytest.mark.django_db

BASE = "/api/v1/aprovacoes/"
MOTIVOS = f"{BASE}motivos/"
APROVAR = "solicitacao.aprovar"
CONTESTAR = "solicitacao.contestar"
RECUSAR = "solicitacao.recusar"


def _erro(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def _criar(client: APIClient, texto: str, tipo: str = APROVAR) -> Any:
    return client.post(MOTIVOS, {"tipo_de_decisao": tipo, "texto": texto}, format="json")


def _textos(client: APIClient, tipo: str, todos: bool = False) -> set[str]:
    resposta = client.get(MOTIVOS, {"tipo_de_decisao": tipo, **({"todos": "1"} if todos else {})})
    assert resposta.status_code == 200, resposta.content
    return {m["texto"] for m in resposta.json()}


def _decisao_com(motivo: MotivoDeDecisao) -> Decisao:
    solicitacao = Solicitacao.objects.create(
        tipo="teste.pedido", solicitante_id=uuid.uuid7(), situacao="EM_ANALISE"
    )
    versao = Versao.objects.create(
        solicitacao=solicitacao,
        numero=1,
        conteudo={},
        valor=Decimal("1.00"),
        resumo="x",
        autor_id=solicitacao.solicitante_id,
    )
    return Decisao.objects.create(
        versao=versao, tipo="APROVAR", aprovador_id=uuid.uuid7(), motivo=motivo, motivo_texto=motivo.texto
    )


# --- CA-29: lista sugerida ---


def test_ca29_o_sistema_nasce_com_motivos_sugeridos(client_com_cargo: APIClient) -> None:
    assert _textos(client_com_cargo, APROVAR) == {
        "Dentro do orçamento",
        "Necessário para a atividade do clube",
        "Conforme combinado em reunião",
    }
    assert _textos(client_com_cargo, CONTESTAR) == {
        "Valor acima do necessário",
        "Faltam detalhes dos itens",
        "Falta justificativa",
        "Data ou prazo a rever",
    }
    assert _textos(client_com_cargo, RECUSAR) == {
        "Sem caixa disponível",
        "Fora das prioridades do clube",
        "Pedido duplicado",
    }


def test_a_lista_traz_id_tipo_texto_e_situacao(client_com_cargo: APIClient) -> None:
    (motivo,) = [m for m in client_com_cargo.get(MOTIVOS).json() if m["texto"] == "Pedido duplicado"]

    assert set(motivo) == {"id", "tipo_de_decisao", "texto", "ativo"}
    assert motivo["tipo_de_decisao"] == RECUSAR
    assert motivo["ativo"] is True


# --- CA-30: o admin mantém, e a decisão antiga guarda o texto ---


def test_ca30_o_admin_cria_edita_e_desativa_e_a_lista_de_opcoes_muda(client_admin: APIClient) -> None:
    criado = _criar(client_admin, "  Aprovado em assembleia  ")
    assert criado.status_code == 201, criado.content
    motivo_id = criado.json()["id"]
    assert "Aprovado em assembleia" in _textos(client_admin, APROVAR)

    editado = client_admin.post(f"{MOTIVOS}{motivo_id}/editar/", {"texto": "Aprovado pela diretoria"})
    assert editado.status_code == 200
    assert "Aprovado pela diretoria" in _textos(client_admin, APROVAR)

    desativado = client_admin.post(f"{MOTIVOS}{motivo_id}/desativar/")
    assert desativado.json()["ativo"] is False
    assert "Aprovado pela diretoria" not in _textos(client_admin, APROVAR)
    assert "Aprovado pela diretoria" in _textos(client_admin, APROVAR, todos=True)

    reativado = client_admin.post(f"{MOTIVOS}{motivo_id}/reativar/")
    assert reativado.json()["ativo"] is True
    assert "Aprovado pela diretoria" in _textos(client_admin, APROVAR)


def test_ca30_a_decisao_antiga_continua_com_o_texto_que_tinha(client_admin: APIClient) -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Dentro do orçamento")
    decisao = _decisao_com(motivo)

    client_admin.post(f"{MOTIVOS}{motivo.id}/editar/", {"texto": "Cabe no orçamento do mês"})
    client_admin.post(f"{MOTIVOS}{motivo.id}/desativar/")

    decisao.refresh_from_db()
    assert decisao.motivo_texto == "Dentro do orçamento"
    assert decisao.motivo_id == motivo.id


# --- CA-31: só o admin altera ---


@pytest.mark.parametrize("acao", ["editar", "desativar", "reativar"])
def test_ca31_quem_nao_e_admin_nao_altera_motivo(client_com_cargo: APIClient, acao: str) -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Pedido duplicado")

    resposta = client_com_cargo.post(f"{MOTIVOS}{motivo.id}/{acao}/", {"texto": "Outro texto"})

    assert _erro(resposta) == (403, "PERMISSION_DENIED")
    motivo.refresh_from_db()
    assert (motivo.texto, motivo.ativo) == ("Pedido duplicado", True)


def test_ca31_quem_nao_e_admin_nao_cria_motivo(client_com_cargo: APIClient) -> None:
    assert _erro(_criar(client_com_cargo, "Qualquer")) == (403, "PERMISSION_DENIED")
    assert not MotivoDeDecisao.objects.filter(texto="Qualquer").exists()


def test_ca31_o_servico_confere_o_admin_de_novo(diretor_com_cargo: Any) -> None:
    from aprovacoes.services import motivos

    with pytest.raises(BusinessError) as erro:
        motivos.criar(ator_id=diretor_com_cargo.id, tipo_de_decisao=APROVAR, texto="Pelo serviço")

    assert (erro.value.status, erro.value.code) == (403, "PERMISSION_DENIED")


def test_ler_os_motivos_exige_leitura_de_gestao(client_diretor: APIClient, client: APIClient) -> None:
    assert _erro(client_diretor.get(MOTIVOS)) == (403, "PERMISSION_DENIED")
    assert _erro(client.get(MOTIVOS)) == (401, "NOT_AUTHENTICATED")


def test_so_o_admin_ve_os_inativos(client_com_cargo: APIClient) -> None:
    resposta = client_com_cargo.get(MOTIVOS, {"todos": "1"})

    assert _erro(resposta) == (403, "PERMISSION_DENIED")


# --- regras do cadastro ---


@pytest.mark.parametrize("texto", ["Pedido duplicado", "PEDIDO DUPLICADO", " pedido duplicado "])
def test_motivo_repetido_no_mesmo_tipo_de_decisao_e_recusado(client_admin: APIClient, texto: str) -> None:
    assert _erro(_criar(client_admin, texto, RECUSAR)) == (409, "MOTIVO_JA_EXISTE")


def test_a8_motivo_com_o_texto_de_um_inativo_e_recusado(client_admin: APIClient) -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Pedido duplicado")
    client_admin.post(f"{MOTIVOS}{motivo.id}/desativar/")

    assert _erro(_criar(client_admin, "Pedido Duplicado", RECUSAR)) == (409, "MOTIVO_JA_EXISTE")


def test_o_mesmo_texto_em_outro_tipo_de_decisao_e_aceito(client_admin: APIClient) -> None:
    assert _criar(client_admin, "Pedido duplicado", CONTESTAR).status_code == 201


def test_editar_para_o_texto_de_outro_motivo_e_recusado(client_admin: APIClient) -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Sem caixa disponível")

    resposta = client_admin.post(f"{MOTIVOS}{motivo.id}/editar/", {"texto": "pedido duplicado"})

    assert _erro(resposta) == (409, "MOTIVO_JA_EXISTE")


def test_editar_mudando_so_maiusculas_e_aceito(client_admin: APIClient) -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Sem caixa disponível")

    resposta = client_admin.post(f"{MOTIVOS}{motivo.id}/editar/", {"texto": "Sem Caixa Disponível"})

    assert resposta.status_code == 200
    assert resposta.json()["texto"] == "Sem Caixa Disponível"


def test_tipo_de_decisao_desconhecido_e_recusado(client_admin: APIClient) -> None:
    resposta = _criar(client_admin, "Qualquer", "pagamento.validar")

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "tipo_de_decisao" in resposta.json()["error"]["details"]


@pytest.mark.parametrize("texto", ["", "x", "a" * 201])
def test_texto_vazio_curto_ou_longo_e_recusado(client_admin: APIClient, texto: str) -> None:
    assert _erro(_criar(client_admin, texto)) == (400, "VALIDATION_ERROR")


def test_motivo_inexistente(client_admin: APIClient) -> None:
    resposta = client_admin.post(f"{MOTIVOS}{uuid.uuid7()}/desativar/")

    assert _erro(resposta) == (404, "NOT_FOUND")


def test_quem_nao_e_admin_nao_descobre_se_o_motivo_existe(client_com_cargo: APIClient) -> None:
    resposta = client_com_cargo.post(f"{MOTIVOS}{uuid.uuid7()}/desativar/")

    assert _erro(resposta) == (403, "PERMISSION_DENIED")


def test_desativar_o_inativo_e_reativar_o_ativo_sao_recusados(client_admin: APIClient) -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Pedido duplicado")

    assert _erro(client_admin.post(f"{MOTIVOS}{motivo.id}/reativar/")) == (422, "JA_ESTA_ATIVO")
    client_admin.post(f"{MOTIVOS}{motivo.id}/desativar/")
    assert _erro(client_admin.post(f"{MOTIVOS}{motivo.id}/desativar/")) == (422, "JA_ESTA_INATIVO")


def test_nao_ha_rota_para_apagar_motivo(client_admin: APIClient) -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Pedido duplicado")

    assert client_admin.delete(f"{MOTIVOS}{motivo.id}/").status_code in (404, 405)
    assert MotivoDeDecisao.objects.filter(pk=motivo.pk).exists()


# --- CA-33 (motivos): toda ação é auditada ---


def test_ca33_cada_acao_sobre_o_motivo_gera_registro_de_auditoria(
    client_admin: APIClient, admin: Any
) -> None:
    motivo_id = _criar(client_admin, "Aprovado em assembleia").json()["id"]
    client_admin.post(f"{MOTIVOS}{motivo_id}/editar/", {"texto": "Aprovado pela diretoria"})
    client_admin.post(f"{MOTIVOS}{motivo_id}/desativar/")
    client_admin.post(f"{MOTIVOS}{motivo_id}/reativar/")

    registros = auditoria.historico_do_item("motivo_de_decisao", uuid.UUID(motivo_id))

    assert [r.acao for r in registros] == [
        "MOTIVO_CRIADO",
        "MOTIVO_EDITADO",
        "MOTIVO_DESATIVADO",
        "MOTIVO_REATIVADO",
    ]
    assert {r.ator_id for r in registros} == {admin.id}


# --- tipos de decisão ---


def test_o_admin_lista_os_tipos_de_decisao(client_admin: APIClient) -> None:
    resposta = client_admin.get(f"{BASE}tipos-de-decisao/")

    assert resposta.status_code == 200
    codigos = [t["codigo"] for t in resposta.json()]
    assert {APROVAR, CONTESTAR, RECUSAR} <= set(codigos)
    assert codigos == sorted(codigos)
    assert all(set(t) == {"codigo", "nome"} for t in resposta.json())


def test_so_o_admin_lista_os_tipos_de_decisao(client_com_cargo: APIClient) -> None:
    assert _erro(client_com_cargo.get(f"{BASE}tipos-de-decisao/")) == (403, "PERMISSION_DENIED")


def test_registrar_tipo_de_decisao_pela_api_publica() -> None:
    public.registrar_tipo_de_decisao("teste.validar", "Validar de teste")
    try:
        public.registrar_tipo_de_decisao("teste.validar", "Validar de teste")
        with pytest.raises(ValueError, match="outra definição"):
            public.registrar_tipo_de_decisao("teste.validar", "Outro nome")
        with pytest.raises(ValueError, match="inválido"):
            public.registrar_tipo_de_decisao("Validar", "Sem formato")
    finally:
        tipos.remover_tipo_de_decisao_para_testes("teste.validar")


# --- motivo_aplicado: o que os outros módulos usam ---


def test_motivo_aplicado_devolve_o_texto() -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Pedido duplicado")

    assert public.motivo_aplicado(motivo.id, RECUSAR) == "Pedido duplicado"


@pytest.mark.parametrize("caso", ["inexistente", "inativo", "outro_tipo"])
def test_motivo_aplicado_recusa_inexistente_inativo_ou_de_outro_tipo(caso: str) -> None:
    motivo = MotivoDeDecisao.objects.get(texto="Pedido duplicado")
    if caso == "inativo":
        motivo.desativar()
        motivo.save(update_fields=["ativo"])
    motivo_id = uuid.uuid7() if caso == "inexistente" else motivo.id
    tipo = APROVAR if caso == "outro_tipo" else RECUSAR

    with pytest.raises(BusinessError) as erro:
        public.motivo_aplicado(motivo_id, tipo)

    assert (erro.value.status, erro.value.code) == (400, "VALIDATION_ERROR")
    assert "motivo_id" in erro.value.details
