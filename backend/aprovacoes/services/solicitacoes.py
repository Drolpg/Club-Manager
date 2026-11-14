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
from aprovacoes.domain.decisores import FatosDoEnvio, avaliar_envio
from aprovacoes.models import Solicitacao
from aprovacoes.services.autorizacao import exigir
from aprovacoes.tipos import ConteudoPreparado, TipoDeSolicitacao
from auditoria import public as auditoria
from kernel.errors import BusinessError
from permissoes import public as permissoes

ITEM_DA_AUDITORIA = "solicitacao"
LIMITE_DO_CONTEUDO = 64 * 1024
LIMITE_DO_RESUMO = 200


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
    return solicitacao
