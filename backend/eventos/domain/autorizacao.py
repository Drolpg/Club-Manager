"""Quem pode o quê num evento (spec técnica do M8, "Quem pode, em `avaliar`").

Uma função só responde à rota, ao serviço e ao campo `acoes` do detalhe. A ordem é leitura de gestão → quem
pode → o que o estado do evento exige (orçamento) → situação, como no motor.
"""

import uuid
from dataclasses import dataclass

from eventos.domain.situacao import SituacaoDoEvento
from eventos.domain.transicoes import ComandoDoEvento, erro_de_situacao, transicao_permitida

PERM_PROPOR = "eventos.propor"
PERM_APROVAR = "eventos.aprovar"
PERM_CANCELAR = "eventos.cancelar"

PERMISSION_DENIED = "PERMISSION_DENIED"

C = ComandoDoEvento

# Os comandos sobre um evento que já existe, na ordem em que o detalhe os mostra.
COMANDOS_SOBRE_O_EVENTO: tuple[ComandoDoEvento, ...] = (
    C.EDITAR,
    C.REABRIR,
    C.VINCULAR_ORCAMENTO,
    C.CONFIRMAR_REALIZACAO,
    C.CANCELAR,
    C.RESPONDER_PRESENCA,
)


@dataclass(frozen=True)
class FatosDoEvento:
    """O que se sabe de quem age e, quando o evento existe, do evento. Para `PROPOR`, `situacao` é nula."""

    ator_id: uuid.UUID
    le_gestao: bool
    tem_cargo_ativo: bool
    e_admin: bool
    pode_propor: bool
    pode_aprovar: bool
    pode_cancelar: bool
    proponente_id: uuid.UUID | None
    situacao: SituacaoDoEvento | None
    envolve_custo: bool = False
    tem_orcamento: bool = False


@dataclass(frozen=True)
class Avaliacao:
    pode: bool
    erro: str | None = None


_PODE = Avaliacao(True)


def _nao(erro: str) -> Avaliacao:
    return Avaliacao(False, erro)


def _quem_pode(comando: ComandoDoEvento, fatos: FatosDoEvento) -> bool:
    e_o_proponente = fatos.proponente_id is not None and fatos.ator_id == fatos.proponente_id
    if comando == C.PROPOR:
        return fatos.pode_propor
    if comando in (C.EDITAR, C.REABRIR):
        return e_o_proponente or fatos.pode_aprovar
    if comando == C.VINCULAR_ORCAMENTO:
        return fatos.pode_aprovar
    if comando == C.CONFIRMAR_REALIZACAO:
        return e_o_proponente or fatos.pode_aprovar or fatos.e_admin
    if comando == C.CANCELAR:
        return e_o_proponente or fatos.pode_cancelar or fatos.e_admin
    return fatos.tem_cargo_ativo


def avaliar(comando: ComandoDoEvento, fatos: FatosDoEvento) -> Avaliacao:
    """Se o ator pode executar o comando agora e, se não, o código do erro."""
    if not fatos.le_gestao or not _quem_pode(comando, fatos):
        return _nao(PERMISSION_DENIED)
    if fatos.situacao is None:
        return _PODE if comando == C.PROPOR else _nao(PERMISSION_DENIED)
    if not transicao_permitida(fatos.situacao, comando):
        return _nao(erro_de_situacao(fatos.situacao, comando))
    if comando == C.VINCULAR_ORCAMENTO:
        if not fatos.envolve_custo:
            return _nao("EVENTO_SEM_CUSTO")
        if fatos.tem_orcamento:
            return _nao("ORCAMENTO_JA_VINCULADO")
    return _PODE


def acoes_disponiveis(fatos: FatosDoEvento) -> tuple[ComandoDoEvento, ...]:
    return tuple(comando for comando in COMANDOS_SOBRE_O_EVENTO if avaliar(comando, fatos).pode)
