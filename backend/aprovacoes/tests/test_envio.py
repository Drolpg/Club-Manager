"""Registrar um tipo de solicitação e enviar (CA-01, CA-02, CA-20, CA-21; INV-SOL-10, INV-SOL-15; adendo 1).

As notificações do envio entram no checkpoint 6.
"""

import json
import uuid
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.test import APIClient

from aprovacoes import public
from aprovacoes.models import Solicitacao, Versao
from aprovacoes.tests.conftest import (
    APROVAR_TESTE,
    AUTO_APROVAR,
    SOLICITACOES,
    TIPO,
    TipoDeTeste,
    com_cargo,
    pedido,
    preparar_pedido,
)
from auditoria import public as auditoria
from tests import apoio
from tests.apoio import Situacao, Usuario

pytestmark = pytest.mark.django_db


def _erro(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def _enviar(client: APIClient, **corpo: Any) -> Any:
    return client.post(SOLICITACOES, {"tipo": TIPO, "conteudo": pedido(), **corpo}, format="json")


# --- CA-01 e CA-02 ---


def test_ca01_envio_valido_fica_em_analise_com_a_versao_1(
    tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient, diretor_com_cargo: Usuario
) -> None:
    resposta = _enviar(client_com_cargo, conteudo={"descricao": "  Bolas  ", "valor": "150"})

    assert resposta.status_code == 201, resposta.content
    corpo = resposta.json()
    assert corpo["situacao"] == "EM_ANALISE"
    assert corpo["numero_da_versao_atual"] == 1
    solicitacao = Solicitacao.objects.get(pk=corpo["id"])
    assert (solicitacao.tipo, solicitacao.solicitante_id) == (TIPO, diretor_com_cargo.id)
    (versao,) = solicitacao.versoes.all()
    assert versao.numero == 1
    assert versao.conteudo == {"descricao": "Bolas", "valor": "150.00"}
    assert versao.valor == Decimal("150.00")
    assert versao.resumo == "Bolas"
    assert versao.autor_id == diretor_com_cargo.id
    assert tipo_de_teste.recebidas == []


def test_ca01_o_modulo_dono_envia_pela_api_publica(
    tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario
) -> None:
    solicitacao_id = public.enviar(tipo=TIPO, conteudo=pedido(), solicitante_id=diretor_com_cargo.id)

    assert isinstance(solicitacao_id, uuid.UUID)
    assert Solicitacao.objects.get(pk=solicitacao_id).situacao == "EM_ANALISE"


def test_ca02_tipo_desconhecido_nao_cria_nada(
    tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient
) -> None:
    resposta = _enviar(client_com_cargo, tipo="financeiro.inventado")

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "tipo" in resposta.json()["error"]["details"]
    assert not Solicitacao.objects.exists()


def test_ca02_conteudo_recusado_pelo_modulo_dono_nao_cria_nada(
    tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient
) -> None:
    resposta = _enviar(client_com_cargo, conteudo={"descricao": "", "valor": "0"})

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert set(resposta.json()["error"]["details"]) == {"descricao", "valor"}
    assert not Solicitacao.objects.exists()
    assert not Versao.objects.exists()


@pytest.mark.parametrize("conteudo", [["lista"], "texto", None])
def test_conteudo_que_nao_e_objeto_e_recusado(
    tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient, conteudo: Any
) -> None:
    assert _erro(_enviar(client_com_cargo, conteudo=conteudo)) == (400, "VALIDATION_ERROR")


def test_conteudo_acima_de_64_kb_e_recusado(tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient) -> None:
    conteudo = {**pedido(), "anexo": "x" * (64 * 1024)}

    resposta = _enviar(client_com_cargo, conteudo=conteudo)

    assert _erro(resposta) == (400, "VALIDATION_ERROR")
    assert "conteudo" in resposta.json()["error"]["details"]


def test_o_resumo_longo_e_cortado_em_200(tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient) -> None:
    resposta = _enviar(client_com_cargo, conteudo=pedido(descricao="a" * 300))

    versao = Versao.objects.get(solicitacao_id=resposta.json()["id"])
    assert len(versao.resumo) == 200
    assert versao.resumo.endswith("…")


# --- quem envia (adendo 1, A3) ---


def test_enviar_exige_leitura_de_gestao(
    tipo_de_teste: TipoDeTeste, client_diretor: APIClient, client: APIClient
) -> None:
    assert _erro(_enviar(client_diretor)) == (403, "PERMISSION_DENIED")
    assert _erro(_enviar(client)) == (401, "NOT_AUTHENTICATED")
    assert not Solicitacao.objects.exists()


def test_a3_tipo_com_permissao_de_enviar_exige_a_permissao_e_o_cargo(tipo_de_teste: TipoDeTeste) -> None:
    apoio.registrar_permissao_de_teste("teste.enviar")
    public.registrar_tipo(
        codigo="teste.restrito",
        nome="Restrito",
        permissao_de_aprovar=APROVAR_TESTE,
        permissao_de_enviar="teste.enviar",
        tem_valor=True,
        preparar=preparar_pedido,
        ao_mudar=lambda mudanca: None,
    )
    try:
        so_cargo = apoio.cliente_de(com_cargo("sem.permissao"))
        so_permissao = apoio.criar_diretor("sem.cargo")
        apoio.conceder(so_permissao, "teste.enviar")
        os_dois = apoio.cliente_de(com_cargo("com.os.dois", "teste.enviar"))

        assert _erro(_enviar(so_cargo, tipo="teste.restrito")) == (403, "PERMISSION_DENIED")
        assert _erro(_enviar(apoio.cliente_de(so_permissao), tipo="teste.restrito")) == (
            403,
            "PERMISSION_DENIED",
        )
        assert _enviar(os_dois, tipo="teste.restrito").status_code == 201
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("teste.restrito")
        apoio.remover_permissao_de_teste("teste.enviar")


# --- quem aprovaria o próprio pedido (CA-20, CA-21; INV-SOL-10, INV-SOL-15; adendo 1, A1) ---


def test_ca20_quem_pode_aprovar_o_tipo_e_envia_sem_indicar_e_recusado(aprovador: Usuario) -> None:
    resposta = _enviar(apoio.cliente_de(aprovador))

    assert _erro(resposta) == (422, "APROVADOR_NAO_INDICADO")
    assert not Solicitacao.objects.exists()


def test_ca20_indicar_a_si_mesmo_e_recusado(aprovador: Usuario) -> None:
    resposta = _enviar(apoio.cliente_de(aprovador), aprovador_indicado_id=str(aprovador.id))

    assert _erro(resposta) == (422, "APROVADOR_INVALIDO")


def test_ca20_indicar_um_inativo_e_recusado(aprovador: Usuario) -> None:
    inativo = apoio.criar_diretor("ina", situacao=Situacao.INATIVO)
    apoio.dar_cargo(inativo)

    resposta = _enviar(apoio.cliente_de(aprovador), aprovador_indicado_id=str(inativo.id))

    assert _erro(resposta) == (422, "APROVADOR_INVALIDO")


def test_ca20_indicar_um_diretor_sem_cargo_e_recusado(aprovador: Usuario, diretor: Usuario) -> None:
    resposta = _enviar(apoio.cliente_de(aprovador), aprovador_indicado_id=str(diretor.id))

    assert _erro(resposta) == (422, "APROVADOR_INVALIDO")


def test_ca20_indicar_quem_nao_existe_e_recusado(aprovador: Usuario) -> None:
    resposta = _enviar(apoio.cliente_de(aprovador), aprovador_indicado_id=str(uuid.uuid7()))

    assert _erro(resposta) == (422, "APROVADOR_INVALIDO")
    assert not Solicitacao.objects.exists()


def test_ca21_a_indicacao_valida_fica_na_solicitacao_e_no_historico(
    aprovador: Usuario, diretor_com_cargo: Usuario
) -> None:
    resposta = _enviar(apoio.cliente_de(aprovador), aprovador_indicado_id=str(diretor_com_cargo.id))

    assert resposta.status_code == 201, resposta.content
    solicitacao = Solicitacao.objects.get(pk=resposta.json()["id"])
    assert solicitacao.aprovador_indicado_id == diretor_com_cargo.id
    registros = auditoria.historico_do_item("solicitacao", solicitacao.id)
    assert [r.acao for r in registros] == ["SOLICITACAO_ENVIADA", "APROVADOR_INDICADO"]
    assert registros[1].dados["aprovador_indicado_id"] == str(diretor_com_cargo.id)
    assert {r.ator_id for r in registros} == {aprovador.id}


def test_a1_indicar_sem_precisar_e_recusado(
    tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient, admin: Usuario
) -> None:
    resposta = _enviar(client_com_cargo, aprovador_indicado_id=str(admin.id))

    assert _erro(resposta) == (422, "APROVADOR_INVALIDO")
    assert not Solicitacao.objects.exists()


def test_com_auto_aprovacao_envia_sem_indicar(tipo_de_teste: TipoDeTeste) -> None:
    auto = com_cargo("auto", APROVAR_TESTE, AUTO_APROVAR)

    assert _enviar(apoio.cliente_de(auto)).status_code == 201


def test_ca24_acesso_total_sem_auto_aprovacao_precisa_indicar(tipo_de_teste: TipoDeTeste) -> None:
    total = com_cargo("total", "acesso.total")

    assert _erro(_enviar(apoio.cliente_de(total))) == (422, "APROVADOR_NAO_INDICADO")


def test_o_admin_envia_sem_indicar(tipo_de_teste: TipoDeTeste, client_admin: APIClient) -> None:
    assert _enviar(client_admin).status_code == 201


# --- auditoria ---


def test_ca33_o_envio_gera_registro_de_auditoria(
    tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient, diretor_com_cargo: Usuario
) -> None:
    solicitacao_id = uuid.UUID(_enviar(client_com_cargo).json()["id"])

    (registro,) = auditoria.historico_do_item("solicitacao", solicitacao_id)
    assert (registro.acao, registro.ator_id) == ("SOLICITACAO_ENVIADA", diretor_com_cargo.id)
    assert registro.dados == {"tipo": TIPO, "versao": 1}


# --- registrar_tipo ---


def _registrar(**extra: Any) -> None:
    definicao: dict[str, Any] = {
        "codigo": "teste.outro",
        "nome": "Outro",
        "permissao_de_aprovar": APROVAR_TESTE,
        "tem_valor": False,
        "preparar": preparar_pedido,
        "ao_mudar": print,
        **extra,
    }
    public.registrar_tipo(**definicao)


def test_registrar_tipo_com_permissao_fora_do_catalogo_falha(tipo_de_teste: TipoDeTeste) -> None:
    with pytest.raises(ValueError, match="catálogo"):
        _registrar(permissao_de_aprovar="inventada.aprovar")
    with pytest.raises(ValueError, match="catálogo"):
        _registrar(permissao_de_enviar="inventada.enviar")


def test_registrar_tipo_com_codigo_fora_do_formato_falha(tipo_de_teste: TipoDeTeste) -> None:
    with pytest.raises(ValueError, match="inválido"):
        _registrar(codigo="Outro")


def test_registrar_o_mesmo_tipo_de_novo_e_inofensivo_e_com_outra_definicao_falha(
    tipo_de_teste: TipoDeTeste,
) -> None:
    _registrar()
    try:
        _registrar()
        with pytest.raises(ValueError, match="outra definição"):
            _registrar(nome="Outro nome")
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("teste.outro")


def test_tipo_com_valor_que_nao_devolve_valor_e_erro_de_programacao(
    tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario
) -> None:
    def sem_valor(conteudo: dict[str, Any], solicitante_id: Any) -> public.ConteudoPreparado:
        return public.ConteudoPreparado(conteudo=conteudo, valor=None, resumo="x")

    _registrar(codigo="teste.sem_valor", tem_valor=True, preparar=sem_valor)
    try:
        with pytest.raises(ValueError, match="valor"):
            public.enviar(tipo="teste.sem_valor", conteudo={}, solicitante_id=diretor_com_cargo.id)
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste("teste.sem_valor")
    assert not Solicitacao.objects.exists()


def test_o_conteudo_e_guardado_como_json(tipo_de_teste: TipoDeTeste, client_com_cargo: APIClient) -> None:
    resposta = _enviar(client_com_cargo)

    versao = Versao.objects.get(solicitacao_id=resposta.json()["id"])
    assert json.loads(json.dumps(versao.conteudo)) == versao.conteudo
