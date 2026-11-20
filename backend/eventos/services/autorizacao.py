"""Os fatos de quem age, das APIs públicas de `acesso` e `permissoes`, para `domain/autorizacao.avaliar`.

As rotas conferem primeiro; os serviços conferem de novo, porque também são chamados em processo.
"""

import uuid

from acesso import public as acesso
from eventos.domain.autorizacao import (
    PERM_APROVAR,
    PERM_CANCELAR,
    PERM_PROPOR,
    Avaliacao,
    FatosDoEvento,
)
from eventos.domain.situacao import SituacaoDoEvento
from eventos.erros import erro
from eventos.models import Evento
from permissoes import public as permissoes


def tem_cargo_ativo(usuario_id: uuid.UUID) -> bool:
    classificacao = permissoes.classificacao_de(usuario_id)
    return classificacao is not None and classificacao.cargo.ativo


def fatos(ator_id: uuid.UUID, evento: Evento | None = None) -> FatosDoEvento:
    """Uma leitura das permissões do ator; com o evento, também a situação e o orçamento dele."""
    usuario = acesso.usuario_por_id(ator_id)
    do_ator = permissoes.permissoes_de(ator_id)
    return FatosDoEvento(
        ator_id=ator_id,
        le_gestao=permissoes.le_gestao(ator_id),
        tem_cargo_ativo=tem_cargo_ativo(ator_id),
        e_admin=usuario is not None and usuario.ativo and usuario.admin,
        pode_propor=PERM_PROPOR in do_ator,
        pode_aprovar=PERM_APROVAR in do_ator,
        pode_cancelar=PERM_CANCELAR in do_ator,
        proponente_id=evento.proponente_id if evento else None,
        situacao=SituacaoDoEvento(evento.situacao) if evento else None,
        envolve_custo=evento.envolve_custo if evento else False,
        tem_orcamento=evento is not None and evento.solicitacao_orcamentaria_id is not None,
    )


def exigir(avaliacao: Avaliacao) -> None:
    if not avaliacao.pode:
        raise erro(avaliacao.erro or "PERMISSION_DENIED")


def exigir_leitura_de_gestao(ator_id: uuid.UUID) -> None:
    """Leitura de gestão (403) antes da existência (404): quem não lê não descobre quais IDs existem."""
    if not permissoes.le_gestao(ator_id):
        raise erro("PERMISSION_DENIED")
