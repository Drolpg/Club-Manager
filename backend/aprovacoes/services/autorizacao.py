"""Conferências de quem age, escritas sobre as APIs públicas de `acesso` e `permissoes` (adendo 1).

As rotas conferem primeiro; os serviços conferem de novo, porque também são chamados em processo.
"""

import uuid

from acesso import public as acesso
from aprovacoes import tipos
from aprovacoes.domain.decisores import Avaliacao, Fatos
from aprovacoes.domain.transicoes import Situacao
from aprovacoes.erros import erro
from aprovacoes.models import Solicitacao
from kernel.errors import BusinessError
from permissoes import public as permissoes


def negado(mensagem: str = "Você não tem permissão para fazer isso.") -> BusinessError:
    return BusinessError("PERMISSION_DENIED", mensagem, status=403)


def e_admin(usuario_id: uuid.UUID) -> bool:
    usuario = acesso.usuario_por_id(usuario_id)
    return usuario is not None and usuario.ativo and usuario.admin


def exigir_admin(ator_id: uuid.UUID) -> None:
    if not e_admin(ator_id):
        raise negado("Só o admin pode fazer isso.")


def exigir_leitura_de_gestao(ator_id: uuid.UUID) -> None:
    """Admin ativo, ou ativo com cargo ativo (PER-R10; regra 18 da spec funcional)."""
    if not permissoes.le_gestao(ator_id):
        raise negado()


def exigir(avaliacao: Avaliacao) -> None:
    """Levanta o erro que a função de decisão devolveu, se ela disse que não pode."""
    if not avaliacao.pode:
        raise erro(avaliacao.erro or "PERMISSION_DENIED")


def fatos_de(solicitacao: Solicitacao, ator_id: uuid.UUID) -> Fatos:
    """O que as funções de decisão precisam saber do ator e da solicitação. Uma leitura das permissões."""
    definicao = tipos.obter_tipo(solicitacao.tipo)
    do_ator = permissoes.permissoes_de(ator_id)
    return Fatos(
        ator_id=ator_id,
        solicitante_id=solicitacao.solicitante_id,
        aprovador_indicado_id=solicitacao.aprovador_indicado_id,
        situacao=Situacao(solicitacao.situacao),
        le_gestao=permissoes.le_gestao(ator_id),
        pode_aprovar_o_tipo=definicao is not None and definicao.permissao_de_aprovar in do_ator,
        tem_auto_aprovacao=tipos.AUTO_APROVAR in do_ator,
        pode_reabrir_de_outros=tipos.REABRIR_DE_OUTROS in do_ator,
        pode_cancelar_de_outros=tipos.CANCELAR_DE_OUTROS in do_ator,
    )
