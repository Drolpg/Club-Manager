"""Quem pode fazer o quê numa solicitação (INV-SOL-02, INV-SOL-10, INV-SOL-11, INV-SOL-15; RN-012).

Funções puras: o serviço lê os fatos (permissões, leitura de gestão, situação) e elas respondem. Os serviços
levantam o erro devolvido, e o campo `acoes` do detalhe é calculado com as mesmas funções (adendo 1 da
technical-spec). A ordem das conferências é leitura de gestão → quem pode → situação; a existência da
solicitação é conferida pelo serviço entre a primeira e a segunda.
"""

import uuid
from dataclasses import dataclass

from aprovacoes.domain.transicoes import ERRO_DE_SITUACAO, Comando, Situacao, transicao_permitida

PERMISSION_DENIED = "PERMISSION_DENIED"
SO_O_SOLICITANTE = "SO_O_SOLICITANTE"
SOLICITANTE_NAO_DECIDE = "SOLICITANTE_NAO_DECIDE"
APROVADOR_NAO_INDICADO = "APROVADOR_NAO_INDICADO"
APROVADOR_INVALIDO = "APROVADOR_INVALIDO"

# O que o usuário pede pela API. Enviar tem fatos próprios; iniciar a execução e encerrar são do módulo dono.
COMANDOS_DO_USUARIO: tuple[Comando, ...] = (
    Comando.RETIRAR,
    Comando.REENVIAR,
    Comando.REABRIR,
    Comando.EDITAR,
    Comando.CANCELAR,
    Comando.APROVAR,
    Comando.CONTESTAR,
    Comando.RECUSAR,
)
_SO_DO_SOLICITANTE = frozenset({Comando.RETIRAR, Comando.REENVIAR, Comando.EDITAR})
_DECISOES = frozenset({Comando.APROVAR, Comando.CONTESTAR, Comando.RECUSAR})


@dataclass(frozen=True)
class Avaliacao:
    pode: bool
    erro: str | None = None
    aprovacao_propria: bool = False


_PODE = Avaliacao(True)


def _nao(erro: str) -> Avaliacao:
    return Avaliacao(False, erro)


@dataclass(frozen=True)
class Fatos:
    """O que se sabe de quem pede um comando sobre uma solicitação que já existe."""

    ator_id: uuid.UUID
    solicitante_id: uuid.UUID
    aprovador_indicado_id: uuid.UUID | None
    situacao: Situacao
    le_gestao: bool
    pode_aprovar_o_tipo: bool
    tem_auto_aprovacao: bool
    pode_reabrir_de_outros: bool
    pode_cancelar_de_outros: bool


@dataclass(frozen=True)
class FatosDoEnvio:
    solicitante_id: uuid.UUID
    aprovador_indicado_id: uuid.UUID | None
    le_gestao: bool
    # Verdadeiro também quando o tipo não declara permissão de enviar.
    pode_enviar_o_tipo: bool
    pode_aprovar_o_tipo: bool
    tem_auto_aprovacao: bool
    # Falso quando não há indicado.
    indicado_le_gestao: bool


def precisa_indicar_aprovador(tem_permissao_de_aprovar: bool, tem_auto_aprovacao: bool) -> bool:
    """INV-SOL-10: quem aprovaria o próprio pedido e não tem auto-aprovação indica outro aprovador."""
    return tem_permissao_de_aprovar and not tem_auto_aprovacao


def pode_decidir(
    *,
    ator_id: uuid.UUID,
    solicitante_id: uuid.UUID,
    aprovador_indicado_id: uuid.UUID | None,
    tem_permissao_de_aprovar: bool,
    tem_auto_aprovacao: bool,
) -> Avaliacao:
    """INV-SOL-02 e INV-SOL-11.

    O solicitante só decide o próprio pedido com a auto-aprovação, e ainda precisa da permissão de aprovar o
    tipo: a auto-aprovação é exceção à regra do próprio pedido, e não a permissão de decidir. Os outros
    decidem com a permissão de aprovar o tipo, ou sendo o aprovador indicado daquele pedido.
    """
    if ator_id == solicitante_id:
        if not tem_auto_aprovacao:
            return _nao(SOLICITANTE_NAO_DECIDE)
        if not tem_permissao_de_aprovar:
            return _nao(PERMISSION_DENIED)
        return Avaliacao(True, aprovacao_propria=True)
    if tem_permissao_de_aprovar or ator_id == aprovador_indicado_id:
        return _PODE
    return _nao(PERMISSION_DENIED)


def _quem_pode(comando: Comando, fatos: Fatos) -> Avaliacao:
    e_o_solicitante = fatos.ator_id == fatos.solicitante_id
    if comando in _SO_DO_SOLICITANTE:
        return _PODE if e_o_solicitante else _nao(SO_O_SOLICITANTE)
    if comando is Comando.REABRIR:
        return _PODE if e_o_solicitante or fatos.pode_reabrir_de_outros else _nao(PERMISSION_DENIED)
    if comando is Comando.CANCELAR:
        return _PODE if e_o_solicitante or fatos.pode_cancelar_de_outros else _nao(PERMISSION_DENIED)
    return pode_decidir(
        ator_id=fatos.ator_id,
        solicitante_id=fatos.solicitante_id,
        aprovador_indicado_id=fatos.aprovador_indicado_id,
        tem_permissao_de_aprovar=fatos.pode_aprovar_o_tipo,
        tem_auto_aprovacao=fatos.tem_auto_aprovacao,
    )


def avaliar(comando: Comando, fatos: Fatos) -> Avaliacao:
    """Se o ator pode executar o comando agora e, se não, o código do erro. Uma conferência só por vez."""
    if comando not in COMANDOS_DO_USUARIO:
        raise ValueError(f"{comando} não é comando do usuário.")
    if not fatos.le_gestao:
        return _nao(PERMISSION_DENIED)
    quem = _quem_pode(comando, fatos)
    if not quem.pode:
        return quem
    if not transicao_permitida(fatos.situacao, comando):
        return _nao(ERRO_DE_SITUACAO[comando])
    return quem


def acoes_disponiveis(fatos: Fatos) -> tuple[Comando, ...]:
    """Os comandos que o ator pode executar agora, na ordem de `COMANDOS_DO_USUARIO`."""
    return tuple(comando for comando in COMANDOS_DO_USUARIO if avaliar(comando, fatos).pode)


def avaliar_envio(fatos: FatosDoEnvio) -> Avaliacao:
    """Envio: leitura de gestão e permissão de enviar (adendo 1, A3); depois a indicação (INV-SOL-10 e 15).

    Só indica um aprovador quem precisa; a indicação de quem não precisa é recusada (adendo 1, A1).
    """
    if not (fatos.le_gestao and fatos.pode_enviar_o_tipo):
        return _nao(PERMISSION_DENIED)
    indicado = fatos.aprovador_indicado_id
    if not precisa_indicar_aprovador(fatos.pode_aprovar_o_tipo, fatos.tem_auto_aprovacao):
        return _PODE if indicado is None else _nao(APROVADOR_INVALIDO)
    if indicado is None:
        return _nao(APROVADOR_NAO_INDICADO)
    if indicado == fatos.solicitante_id or not fatos.indicado_le_gestao:
        return _nao(APROVADOR_INVALIDO)
    return _PODE
