"""Fixtures dos testes de `aprovacoes`. As comuns (usuários e clientes) ficam em `backend/conftest.py`.

O motor é exercitado com o tipo `teste.pedido` (com valor e a permissão `teste.aprovar`), registrado pela API
pública e removido no fim de cada teste, falhando ou não. O `ao_mudar` dele guarda o que recebeu.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from rest_framework.test import APIClient

from aprovacoes import public
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError
from tests import apoio
from tests.apoio import Usuario

TIPO = "teste.pedido"
APROVAR_TESTE = "teste.aprovar"
AUTO_APROVAR = "solicitacoes.auto_aprovar"
REABRIR = "solicitacoes.reabrir"
CANCELAR = "solicitacoes.cancelar"
SOLICITACOES = "/api/v1/aprovacoes/solicitacoes/"


def preparar_pedido(conteudo: dict[str, Any], solicitante_id: Any) -> public.ConteudoPreparado:
    """O módulo dono valida e normaliza: exige `descricao` e `valor` maior que zero."""
    erros: dict[str, list[str]] = {}
    descricao = conteudo.get("descricao")
    if not isinstance(descricao, str) or not descricao.strip():
        erros["descricao"] = ["Informe a descrição."]
    try:
        valor = Dinheiro(str(conteudo.get("valor")))
        if valor.quantia <= 0:
            erros["valor"] = ["O valor precisa ser maior que zero."]
    except TypeError, ValueError:
        erros["valor"] = ["Valor inválido."]
    if erros:
        raise BusinessError("VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details=erros)
    assert isinstance(descricao, str)
    return public.ConteudoPreparado(
        conteudo={"descricao": descricao.strip(), "valor": str(valor)}, valor=valor, resumo=descricao.strip()
    )


@dataclass
class TipoDeTeste:
    codigo: str
    recebidas: list[public.MudancaDeSolicitacao] = field(default_factory=list)


@pytest.fixture
def tipo_de_teste(db: None) -> Iterator[TipoDeTeste]:
    tipo = TipoDeTeste(TIPO)
    apoio.registrar_permissao_de_teste(APROVAR_TESTE)
    try:
        public.registrar_tipo(
            codigo=TIPO,
            nome="Pedido de teste",
            permissao_de_aprovar=APROVAR_TESTE,
            tem_valor=True,
            preparar=preparar_pedido,
            ao_mudar=tipo.recebidas.append,
        )
        yield tipo
    finally:
        apoio.remover_tipo_de_solicitacao_de_teste(TIPO)
        apoio.remover_permissao_de_teste(APROVAR_TESTE)


def pedido(descricao: str = "Bolas de treino", valor: str = "150.00") -> dict[str, Any]:
    return {"descricao": descricao, "valor": valor}


def com_cargo(nome_de_usuario: str, *permissoes: str) -> Usuario:
    usuario = apoio.criar_diretor(nome_de_usuario)
    apoio.dar_cargo(usuario)
    for permissao in permissoes:
        apoio.conceder(usuario, permissao)
    return usuario


@pytest.fixture
def diretor_com_cargo(db: None) -> Usuario:
    return com_cargo("caio")


@pytest.fixture
def client_com_cargo(diretor_com_cargo: Usuario) -> APIClient:
    return apoio.cliente_de(diretor_com_cargo)


@pytest.fixture
def aprovador(tipo_de_teste: TipoDeTeste) -> Usuario:
    return com_cargo("dora", APROVAR_TESTE)


# --- Cenários montados pelos serviços (nunca gravando a situação direto no banco) ---

DECISOR_DO_CENARIO = "decisor.cenario"


def decisor_do_cenario() -> Usuario:
    """Um aprovador de `teste.aprovar` que só existe para montar cenários."""
    existente = Usuario.objects.filter(nome_de_usuario=DECISOR_DO_CENARIO).first()
    return existente or com_cargo(DECISOR_DO_CENARIO, APROVAR_TESTE)


def _motivo_do_cenario(tipo_de_decisao: str) -> Any:
    from aprovacoes.models import MotivoDeDecisao

    motivo, _ = MotivoDeDecisao.objects.get_or_create(
        tipo_de_decisao=tipo_de_decisao, texto="Motivo do cenário"
    )
    return motivo.id


def enviada(solicitante: Usuario, tipo: str = TIPO, indicado: Usuario | None = None) -> Any:
    from aprovacoes.models import Solicitacao

    solicitacao_id = public.enviar(
        tipo=tipo,
        conteudo=pedido(),
        solicitante_id=solicitante.id,
        aprovador_indicado_id=indicado.id if indicado else None,
    )
    return Solicitacao.objects.get(pk=solicitacao_id)


def levar_a(solicitacao: Any, situacao: str, *, avisos: list[Any] | None = None) -> Any:
    """Leva a solicitação, que está em análise, até a situação pedida, pelos mesmos serviços do sistema.

    Os avisos ao módulo dono gerados aqui são tirados de `avisos` (a lista do tipo de teste), para o teste
    conferir só os avisos da ação que ele exercita.
    """
    from aprovacoes.services import decisoes, solicitacoes

    antes = len(avisos) if avisos is not None else 0
    decisor = decisor_do_cenario().id
    solicitante = solicitacao.solicitante_id

    def decidir(comando: Any, tipo_de_decisao: str, **extra: Any) -> None:
        comando(
            ator_id=decisor,
            solicitacao_id=solicitacao.id,
            motivo_id=_motivo_do_cenario(tipo_de_decisao),
            **extra,
        )

    if situacao == "CONTESTADA":
        decidir(decisoes.contestar, "solicitacao.contestar", mensagem="Ajuste o pedido.")
    elif situacao == "RECUSADA":
        decidir(decisoes.recusar, "solicitacao.recusar")
    elif situacao in ("APROVADA", "EM_EXECUCAO", "ENCERRADA"):
        decidir(decisoes.aprovar, "solicitacao.aprovar")
        if situacao == "EM_EXECUCAO":
            public.iniciar_execucao(solicitacao.id)
        elif situacao == "ENCERRADA":
            public.encerrar(solicitacao.id)
    elif situacao == "RETIRADA":
        solicitacoes.retirar(ator_id=solicitante, solicitacao_id=solicitacao.id)
    elif situacao == "CANCELADA":
        solicitacoes.cancelar(ator_id=solicitante, solicitacao_id=solicitacao.id, motivo="Cenário")
    elif situacao != "EM_ANALISE":
        raise ValueError(f"Cenário desconhecido: {situacao}")
    if avisos is not None:
        del avisos[antes:]
    solicitacao.refresh_from_db()
    assert solicitacao.situacao == situacao
    return solicitacao
