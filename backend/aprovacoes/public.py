"""API pública do módulo `aprovacoes`.

É o único arquivo deste módulo que outros módulos podem importar
(docs/sdd/02-plan.md).

- `registrar_tipo(...)`: um módulo registra um tipo de solicitação ao iniciar, com a permissão de quem decide,
  se tem valor, o `preparar` que valida o conteúdo e o `ao_mudar` que recebe cada `MudancaDeSolicitacao`.
- `enviar(...)`: o módulo dono abre uma solicitação em processo e recebe o ID (adendo 1 da technical-spec).
- `iniciar_execucao(solicitacao_id, ator_id=None)` e `encerrar(solicitacao_id, ator_id=None)`: só o módulo
  dono os chama, e não há rota para eles. `ator_id` nulo quando é o sistema.
- `situacao_de(solicitacao_id)`: a situação atual, como `Situacao`.
- `nova_versao_pelo_dono(...)` e `cancelar_pelo_dono(...)`: só o módulo dono, que já conferiu quem age
  (adendo 2); um tipo registrado com `so_pelo_modulo_dono=True` só muda por elas.
- `registrar_tipo_de_decisao(codigo, nome)`: um módulo declara os tipos de decisão dele ao iniciar (RN-011).
- `motivo_aplicado(motivo_id, tipo_de_decisao)`: o texto do motivo a copiar na decisão; recusa motivo
  inexistente, inativo ou de outro tipo de decisão com `VALIDATION_ERROR` em `motivo_id`.
- `quantidade_na_fila(usuario_id)` e `em_analise_por_tipo()`: contagens para o dashboard, só leitura; quem
  pode ver é de quem chama.
"""

import uuid
from typing import Any

from aprovacoes.domain.transicoes import Situacao
from aprovacoes.services import execucao, solicitacoes
from aprovacoes.services.consulta import EmAnalisePorTipo, em_analise_por_tipo, quantidade_na_fila
from aprovacoes.services.execucao import SolicitacaoInfo, obter_solicitacao, situacao_de
from aprovacoes.services.motivos import motivo_aplicado
from aprovacoes.tipos import (
    Acontecimento,
    ConteudoPreparado,
    MudancaDeSolicitacao,
    registrar_tipo,
    registrar_tipo_de_decisao,
)


def enviar(
    *,
    tipo: str,
    conteudo: dict[str, Any],
    solicitante_id: uuid.UUID,
    aprovador_indicado_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Envia uma solicitação em nome do solicitante, com as mesmas regras da rota, e devolve o ID dela."""
    solicitacao = solicitacoes.enviar(
        ator_id=solicitante_id,
        tipo=tipo,
        conteudo=conteudo,
        aprovador_indicado_id=aprovador_indicado_id,
        pelo_dono=True,
    )
    return solicitacao.id


def iniciar_execucao(solicitacao_id: uuid.UUID, *, ator_id: uuid.UUID | None = None) -> None:
    """Aprovada → em execução. Recusa com `NAO_ESTA_APROVADA`; inexistente, `NOT_FOUND`."""
    execucao.iniciar_execucao(solicitacao_id, ator_id=ator_id)


def encerrar(solicitacao_id: uuid.UUID, *, ator_id: uuid.UUID | None = None) -> None:
    """Aprovada ou em execução → encerrada. Recusa com `NAO_PODE_ENCERRAR`; inexistente, `NOT_FOUND`."""
    execucao.encerrar(solicitacao_id, ator_id=ator_id)


def cancelar(solicitacao_id: uuid.UUID, *, ator_id: uuid.UUID, motivo: str) -> None:
    """Cancela com motivo, com as regras da rota: o solicitante, ou quem tem `solicitacoes.cancelar`."""
    solicitacoes.cancelar(ator_id=ator_id, solicitacao_id=solicitacao_id, motivo=motivo)


def nova_versao_pelo_dono(
    solicitacao_id: uuid.UUID,
    *,
    tipo: str,
    ator_id: uuid.UUID,
    conteudo: dict[str, Any],
    justificativa: str = "",
) -> None:
    """Só o módulo dono, que já conferiu quem age: versão nova pela transição da situação atual (adendo 2).

    Aprovada → editar; contestada ou retirada → reenviar; recusada → reabrir (justificativa obrigatória); em
    análise → retirar e reenviar. Nas outras, `NAO_PODE_EDITAR`. Tipo diferente do informado: `ValueError`.
    """
    solicitacoes.nova_versao_pelo_dono(
        solicitacao_id=solicitacao_id,
        tipo=tipo,
        ator_id=ator_id,
        conteudo=conteudo,
        justificativa=justificativa,
    )


def cancelar_pelo_dono(
    solicitacao_id: uuid.UUID, *, tipo: str, ator_id: uuid.UUID | None, motivo: str
) -> None:
    """Só o módulo dono, que já conferiu quem age: cancela com motivo; ator nulo é o sistema (adendo 2)."""
    solicitacoes.cancelar_pelo_dono(solicitacao_id=solicitacao_id, tipo=tipo, ator_id=ator_id, motivo=motivo)


__all__ = (
    "Acontecimento",
    "ConteudoPreparado",
    "EmAnalisePorTipo",
    "MudancaDeSolicitacao",
    "Situacao",
    "SolicitacaoInfo",
    "cancelar",
    "cancelar_pelo_dono",
    "em_analise_por_tipo",
    "encerrar",
    "enviar",
    "iniciar_execucao",
    "motivo_aplicado",
    "nova_versao_pelo_dono",
    "obter_solicitacao",
    "quantidade_na_fila",
    "registrar_tipo",
    "registrar_tipo_de_decisao",
    "situacao_de",
)
