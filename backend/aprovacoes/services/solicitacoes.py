"""Os comandos do solicitante: enviar, e (checkpoint 3b) retirar, reenviar, reabrir, editar e cancelar.

Cada serviço abre a transação, confere quem age com as funções puras de `aprovacoes/domain/`, chama o método
do aggregate, audita e avisa o módulo dono. A autorização fica separada da mudança de estado (adendo 1 da
technical-spec).
"""

import json
import uuid
from typing import Any

from django.db import transaction

from aprovacoes import tipos
from aprovacoes.domain.decisores import FatosDoEnvio, avaliar, avaliar_envio
from aprovacoes.domain.transicoes import Comando, Situacao
from aprovacoes.models import Solicitacao
from aprovacoes.services import avisos
from aprovacoes.services.autorizacao import exigir, exigir_leitura_de_gestao, fatos_de
from aprovacoes.tipos import Acontecimento, ConteudoPreparado, MudancaDeSolicitacao, TipoDeSolicitacao
from auditoria import public as auditoria
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError
from permissoes import public as permissoes

ITEM_DA_AUDITORIA = "solicitacao"
LIMITE_DO_CONTEUDO = 64 * 1024
LIMITE_DO_RESUMO = 200
# Mensagem, justificativa e complemento do motivo (adendo 1, A11).
LIMITE_DO_TEXTO = 1000


def _invalido(campo: str, mensagem: str) -> BusinessError:
    return BusinessError(
        "VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details={campo: [mensagem]}
    )


def cortar(texto: str, limite: int) -> str:
    """O texto inteiro, ou cortado com reticências para caber no limite."""
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _tipo(codigo: str) -> TipoDeSolicitacao:
    definicao = tipos.obter_tipo(codigo)
    if definicao is None:
        raise _invalido("tipo", "Tipo de solicitação desconhecido.")
    return definicao


def _conferir_formato(conteudo: Any) -> dict[str, Any]:
    if not isinstance(conteudo, dict):
        raise _invalido("conteudo", "O conteúdo precisa ser um objeto.")
    if len(json.dumps(conteudo, ensure_ascii=False).encode()) > LIMITE_DO_CONTEUDO:
        raise _invalido("conteudo", "O conteúdo passa de 64 KB.")
    return conteudo


def _preparar(
    definicao: TipoDeSolicitacao, conteudo: dict[str, Any], solicitante_id: uuid.UUID
) -> ConteudoPreparado:
    """Chama o módulo dono, dentro da transação do serviço, e confere o que ele devolveu."""
    preparado = definicao.preparar(conteudo, solicitante_id)
    if definicao.tem_valor and preparado.valor is None:
        raise ValueError(f"O tipo {definicao.codigo!r} tem valor, e o preparar não devolveu o valor.")
    if not definicao.tem_valor and preparado.valor is not None:
        raise ValueError(f"O tipo {definicao.codigo!r} não tem valor, e o preparar devolveu um valor.")
    return ConteudoPreparado(
        conteudo=preparado.conteudo,
        valor=preparado.valor,
        resumo=cortar(preparado.resumo.strip(), LIMITE_DO_RESUMO),
    )


def _auditar(
    ator_id: uuid.UUID | None, solicitacao: Solicitacao, acao: str, *, justificativa: str = "", **dados: Any
) -> None:
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao,
        item_tipo=ITEM_DA_AUDITORIA,
        item_id=solicitacao.id,
        justificativa=justificativa,
        dados=dados,
    )


@transaction.atomic
def enviar(
    *,
    ator_id: uuid.UUID,
    tipo: str,
    conteudo: Any,
    aprovador_indicado_id: uuid.UUID | None = None,
) -> Solicitacao:
    """Cria a solicitação em análise, com a versão 1 (RF-034; INV-SOL-10, INV-SOL-15; adendo 1, A1 e A3)."""
    definicao = _tipo(tipo)
    conteudo = _conferir_formato(conteudo)
    do_ator = permissoes.permissoes_de(ator_id)
    indicado = aprovador_indicado_id
    exigir(
        avaliar_envio(
            FatosDoEnvio(
                solicitante_id=ator_id,
                aprovador_indicado_id=indicado,
                le_gestao=permissoes.le_gestao(ator_id),
                pode_enviar_o_tipo=definicao.permissao_de_enviar is None
                or definicao.permissao_de_enviar in do_ator,
                pode_aprovar_o_tipo=definicao.permissao_de_aprovar in do_ator,
                tem_auto_aprovacao=tipos.AUTO_APROVAR in do_ator,
                indicado_le_gestao=indicado is not None and permissoes.le_gestao(indicado),
            )
        )
    )
    preparado = _preparar(definicao, conteudo, ator_id)
    solicitacao = Solicitacao.abrir(
        tipo=definicao.codigo, solicitante_id=ator_id, aprovador_indicado_id=indicado, preparado=preparado
    )
    _auditar(ator_id, solicitacao, "SOLICITACAO_ENVIADA", tipo=definicao.codigo, versao=1)
    if indicado is not None:
        _auditar(ator_id, solicitacao, "APROVADOR_INDICADO", aprovador_indicado_id=str(indicado))
    avisos.ao_enviar(solicitacao, ator_id=ator_id)
    return solicitacao


# --- comandos sobre uma solicitação que já existe ---


def texto_obrigatorio(campo: str, texto: str | None) -> str:
    limpo = (texto or "").strip()
    if not limpo:
        raise _invalido(campo, "Este campo é obrigatório.")
    return texto_opcional(campo, limpo)


def texto_opcional(campo: str, texto: str | None) -> str:
    limpo = (texto or "").strip()
    if len(limpo) > LIMITE_DO_TEXTO:
        raise _invalido(campo, f"Use no máximo {LIMITE_DO_TEXTO} caracteres.")
    return limpo


def bloquear(ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Solicitacao:
    """Leitura de gestão (403) antes da existência (404), e a linha bloqueada até o fim da transação."""
    exigir_leitura_de_gestao(ator_id)
    solicitacao = Solicitacao.objects.select_for_update().filter(pk=solicitacao_id).first()
    if solicitacao is None:
        raise BusinessError("NOT_FOUND", "Solicitação não encontrada.", status=404)
    return solicitacao


def tipo_de(solicitacao: Solicitacao) -> TipoDeSolicitacao:
    definicao = tipos.obter_tipo(solicitacao.tipo)
    if definicao is None:
        # Só acontece se o módulo que registrou o tipo deixou de registrá-lo: é erro de configuração.
        raise RuntimeError(f"Tipo de solicitação {solicitacao.tipo!r} não está registrado.")
    return definicao


def avisar_o_dono(
    solicitacao: Solicitacao,
    acontecimento: Acontecimento,
    ator_id: uuid.UUID | None,
    teto_sugerido: Dinheiro | None = None,
) -> None:
    """O aviso ao módulo dono, na mesma transação: um erro nele desfaz a ação (ADR-003)."""
    versao = solicitacao.versao_atual
    tipo_de(solicitacao).ao_mudar(
        MudancaDeSolicitacao(
            solicitacao_id=solicitacao.id,
            tipo=solicitacao.tipo,
            acontecimento=acontecimento,
            versao=versao.numero,
            valor=Dinheiro(versao.valor) if versao.valor is not None else None,
            ator_id=ator_id,
            teto_sugerido=teto_sugerido,
        )
    )


@transaction.atomic
def retirar(*, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Solicitacao:
    """RF-120: o solicitante tira da análise para corrigir; ela sai da fila e só volta por reenvio."""
    solicitacao = bloquear(ator_id, solicitacao_id)
    exigir(avaliar(Comando.RETIRAR, fatos_de(solicitacao, ator_id)))
    solicitacao.retirar()
    _auditar(ator_id, solicitacao, "SOLICITACAO_RETIRADA", versao=solicitacao.numero_da_versao_atual)
    avisar_o_dono(solicitacao, Acontecimento.RETIRADA, ator_id)
    avisos.saiu_da_fila(solicitacao, ator_id=ator_id, como="retirada")
    return solicitacao


@transaction.atomic
def reenviar(*, ator_id: uuid.UUID, solicitacao_id: uuid.UUID, conteudo: Any) -> Solicitacao:
    """RF-039: contestada ou retirada, corrigida, volta à análise como versão nova."""
    conteudo = _conferir_formato(conteudo)
    solicitacao = bloquear(ator_id, solicitacao_id)
    exigir(avaliar(Comando.REENVIAR, fatos_de(solicitacao, ator_id)))
    preparado = _preparar(tipo_de(solicitacao), conteudo, solicitacao.solicitante_id)
    solicitacao.reenviar(preparado, autor_id=ator_id)
    _auditar(ator_id, solicitacao, "SOLICITACAO_REENVIADA", versao=solicitacao.numero_da_versao_atual)
    avisos.para_decidir(solicitacao, ator_id=ator_id, fato="reenviada")
    return solicitacao


@transaction.atomic
def reabrir(
    *, ator_id: uuid.UUID, solicitacao_id: uuid.UUID, justificativa: str, conteudo: Any = None
) -> Solicitacao:
    """RF-040. Sem conteúdo novo, a versão nova copia a anterior; nos dois casos o conteúdo passa de novo pela
    validação do tipo, em nome do solicitante original, e o autor da versão é quem reabriu (adendo 1, A4).
    """
    justificativa = texto_obrigatorio("justificativa", justificativa)
    if conteudo is not None:
        conteudo = _conferir_formato(conteudo)
    solicitacao = bloquear(ator_id, solicitacao_id)
    exigir(avaliar(Comando.REABRIR, fatos_de(solicitacao, ator_id)))
    if conteudo is None:
        conteudo = solicitacao.versao_atual.conteudo
    preparado = _preparar(tipo_de(solicitacao), conteudo, solicitacao.solicitante_id)
    solicitacao.reabrir(preparado, autor_id=ator_id, justificativa=justificativa)
    _auditar(
        ator_id,
        solicitacao,
        "SOLICITACAO_REABERTA",
        justificativa=justificativa,
        versao=solicitacao.numero_da_versao_atual,
    )
    avisar_o_dono(solicitacao, Acontecimento.REABERTA, ator_id)
    avisos.para_decidir(solicitacao, ator_id=ator_id, fato="reaberta")
    return solicitacao


@transaction.atomic
def editar(
    *, ator_id: uuid.UUID, solicitacao_id: uuid.UUID, conteudo: Any, justificativa: str | None = None
) -> Solicitacao:
    """RF-041: a aprovada, antes da execução, volta à análise como versão nova; o dono é avisado."""
    justificativa = texto_opcional("justificativa", justificativa)
    conteudo = _conferir_formato(conteudo)
    solicitacao = bloquear(ator_id, solicitacao_id)
    exigir(avaliar(Comando.EDITAR, fatos_de(solicitacao, ator_id)))
    preparado = _preparar(tipo_de(solicitacao), conteudo, solicitacao.solicitante_id)
    solicitacao.editar(preparado, autor_id=ator_id, justificativa=justificativa)
    _auditar(
        ator_id,
        solicitacao,
        "SOLICITACAO_EDITADA",
        justificativa=justificativa,
        versao=solicitacao.numero_da_versao_atual,
    )
    avisar_o_dono(solicitacao, Acontecimento.EDITADA, ator_id)
    avisos.para_decidir(solicitacao, ator_id=ator_id, fato="editada")
    return solicitacao


@transaction.atomic
def cancelar(*, ator_id: uuid.UUID, solicitacao_id: uuid.UUID, motivo: str) -> Solicitacao:
    """RF-042: com motivo, enquanto a execução não começou. Cancelada, não aceita mais nada."""
    motivo = texto_obrigatorio("motivo", motivo)
    solicitacao = bloquear(ator_id, solicitacao_id)
    exigir(avaliar(Comando.CANCELAR, fatos_de(solicitacao, ator_id)))
    estava_na_fila = solicitacao.situacao == Situacao.EM_ANALISE
    solicitacao.cancelar()
    _auditar(
        ator_id,
        solicitacao,
        "SOLICITACAO_CANCELADA",
        justificativa=motivo,
        versao=solicitacao.numero_da_versao_atual,
    )
    avisar_o_dono(solicitacao, Acontecimento.CANCELADA, ator_id)
    if estava_na_fila:
        avisos.saiu_da_fila(solicitacao, ator_id=ator_id, como="cancelada")
    return solicitacao
