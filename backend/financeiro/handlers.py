"""Tratadores de eventos de integração de contextos inferiores para o módulo financeiro."""

from acesso import public as acesso
from auditoria import public as auditoria
from financeiro.domain.transicoes import SituacaoCobranca
from financeiro.models import Cobranca, SituacaoSuspensao, Suspensao
from financeiro.services import avisos
from kernel import events


def ao_desativar_usuario(evento: acesso.UsuarioDesativado) -> None:
    """Encerra suspensões vigentes e avisa o financeiro sem apagar cobranças do diretor."""
    suspensoes = Suspensao.objects.filter(diretor_id=evento.usuario_id, situacao=SituacaoSuspensao.VIGENTE)
    for suspensao in suspensoes:
        suspensao.encerrar(por_id=None, agora=evento.desativado_em)
        auditoria.registrar(
            acao="SUSPENSAO_ENCERRADA_DESATIVACAO",
            ator_id=None,
            item_tipo="suspensao",
            item_id=suspensao.id,
            dados={"diretor_id": str(evento.usuario_id)},
        )

    cobrancas_abertas = Cobranca.objects.filter(
        devedor_id=evento.usuario_id,
        situacao__in=(
            SituacaoCobranca.ABERTA,
            SituacaoCobranca.EM_VALIDACAO,
            SituacaoCobranca.ATRASADA,
        ),
    ).count()
    if cobrancas_abertas > 0:
        avisos.diretor_desativado_com_cobrancas(
            evento.usuario_id,
            evento.desativado_em,
            cobrancas_abertas,
        )


def registrar() -> None:
    """Inscreve os tratadores de integração no barramento em processo (ADR-003)."""
    events.subscribe(acesso.UsuarioDesativado, ao_desativar_usuario)
