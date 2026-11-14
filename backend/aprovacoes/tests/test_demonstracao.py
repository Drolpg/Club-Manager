"""Tipo de demonstração (adendo 1 da technical-spec): só existe com `DEBUG` ligado e a variável definida."""

from collections.abc import Iterator

import pytest
from django.test import override_settings

from aprovacoes import demonstracao, public, tipos
from permissoes import public as permissoes
from tests import apoio
from tests.apoio import Usuario

VARIAVEL = "APROVACOES_TIPO_DE_DEMONSTRACAO"


@pytest.fixture
def sem_registro() -> Iterator[None]:
    """Garante que o teste começa e termina sem o tipo e a permissão de demonstração."""
    apoio.remover_tipo_de_solicitacao_de_teste(demonstracao.TIPO)
    apoio.remover_permissao_de_teste(demonstracao.PERMISSAO)
    yield
    apoio.remover_tipo_de_solicitacao_de_teste(demonstracao.TIPO)
    apoio.remover_permissao_de_teste(demonstracao.PERMISSAO)


def _registrado() -> bool:
    return tipos.obter_tipo(demonstracao.TIPO) is not None


def test_nos_testes_o_sistema_inicia_sem_o_tipo_de_demonstracao() -> None:
    # A configuração dos testes tem DEBUG desligado: o `ready` não registrou nada.
    assert not _registrado()


@override_settings(DEBUG=False)
@pytest.mark.parametrize("valor", ["1", "true", "yes"])
def test_com_debug_desligado_a_variavel_e_ignorada(
    sem_registro: None, monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    monkeypatch.setenv(VARIAVEL, valor)

    assert demonstracao.registrar_se_ligado() is False
    assert not _registrado()
    assert permissoes.nome_da_permissao(demonstracao.PERMISSAO) is None


@override_settings(DEBUG=True)
@pytest.mark.parametrize("valor", [None, "", "0", "false", "não"])
def test_com_debug_ligado_e_sem_a_variavel_nao_registra(
    sem_registro: None, monkeypatch: pytest.MonkeyPatch, valor: str | None
) -> None:
    if valor is None:
        monkeypatch.delenv(VARIAVEL, raising=False)
    else:
        monkeypatch.setenv(VARIAVEL, valor)

    assert demonstracao.registrar_se_ligado() is False
    assert not _registrado()


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_com_debug_ligado_e_a_variavel_o_tipo_existe_e_funciona(
    sem_registro: None, monkeypatch: pytest.MonkeyPatch, diretor_com_cargo: Usuario
) -> None:
    monkeypatch.setenv(VARIAVEL, "1")

    assert demonstracao.registrar_se_ligado() is True

    definicao = tipos.obter_tipo(demonstracao.TIPO)
    assert definicao is not None
    assert (definicao.permissao_de_aprovar, definicao.tem_valor) == (demonstracao.PERMISSAO, True)
    solicitacao_id = public.enviar(
        tipo=demonstracao.TIPO,
        conteudo={"descricao": "Coletes para o treino", "valor": "320.00"},
        solicitante_id=diretor_com_cargo.id,
    )
    assert public.situacao_de(solicitacao_id) == public.Situacao.EM_ANALISE


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_o_tipo_de_demonstracao_valida_o_conteudo(
    sem_registro: None, monkeypatch: pytest.MonkeyPatch, diretor_com_cargo: Usuario
) -> None:
    from kernel.errors import BusinessError

    monkeypatch.setenv(VARIAVEL, "1")
    demonstracao.registrar_se_ligado()

    with pytest.raises(BusinessError) as erro:
        public.enviar(tipo=demonstracao.TIPO, conteudo={"valor": "0"}, solicitante_id=diretor_com_cargo.id)

    assert erro.value.code == "VALIDATION_ERROR"
    assert set(erro.value.details) == {"descricao", "valor"}
