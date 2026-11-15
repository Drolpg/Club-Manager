"""Autorização na camada de serviço sobre as APIs públicas de `acesso` e `permissoes`."""

import uuid

from acesso import public as acesso
from financeiro.domain.autorizacao import (
    PERM_FINANCEIRO_ESTORNAR,
    FatosCobranca,
    FatosEntrada,
    FatosSaida,
    avaliar_cobranca,
    avaliar_entrada,
    avaliar_saida,
)
from financeiro.domain.saidas import ErroDeRegraSaida, avaliar_liquidacao
from financeiro.domain.transicoes import (
    ComandoCobranca,
    ComandoEntrada,
    ComandoSaida,
    SituacaoCobranca,
    SituacaoEntrada,
    SituacaoSaida,
)
from financeiro.erros import erro
from financeiro.models import Cobranca, Entrada, Saida
from permissoes import public as permissoes


def _usuario_ativo(usuario_id: uuid.UUID) -> acesso.UsuarioInfo:
    usuario = acesso.usuario_por_id(usuario_id)
    if usuario is None or not usuario.ativo:
        raise erro("PERMISSION_DENIED")
    return usuario


def exigir_admin(ator_id: uuid.UUID) -> acesso.UsuarioInfo:
    usuario = _usuario_ativo(ator_id)
    if not usuario.admin:
        raise erro("PERMISSION_DENIED")
    return usuario


def exigir_leitura_gestao(ator_id: uuid.UUID) -> acesso.UsuarioInfo:
    usuario = _usuario_ativo(ator_id)
    if not permissoes.le_gestao(ator_id):
        raise erro("PERMISSION_DENIED")
    return usuario


def exigir_diretor_ativo(ator_id: uuid.UUID) -> acesso.UsuarioInfo:
    return _usuario_ativo(ator_id)


def exigir_permissao(ator_id: uuid.UUID, codigo: str) -> acesso.UsuarioInfo:
    usuario = exigir_leitura_gestao(ator_id)
    if not usuario.admin and not permissoes.pode(ator_id, codigo):
        raise erro("PERMISSION_DENIED")
    return usuario


def permissao_ou_admin(usuario: acesso.UsuarioInfo, codigo: str) -> bool:
    return usuario.admin or permissoes.pode(usuario.id, codigo)


def fatos_cobranca(cobranca: Cobranca, ator_id: uuid.UUID) -> FatosCobranca:
    usuario = _usuario_ativo(ator_id)
    le_gestao = permissoes.le_gestao(ator_id)
    perms = frozenset(permissoes.permissoes_de(ator_id)) if le_gestao or usuario.admin else frozenset()
    return FatosCobranca(
        ator_id=ator_id,
        ator_admin=usuario.admin,
        ator_le_gestao=le_gestao,
        permissoes_ator=perms,
        devedor_id=cobranca.devedor_id,
        situacao=SituacaoCobranca(cobranca.situacao),
        tem_questionamento_aberto=cobranca.tem_questionamento_aberto,
        tem_convocacao_aberta=cobranca.convocacao_aberta is not None,
    )


def exigir_comando_cobranca(cobranca: Cobranca, ator_id: uuid.UUID, comando: ComandoCobranca) -> None:
    decisao = avaliar_cobranca(comando, fatos_cobranca(cobranca, ator_id))
    if not decisao.pode:
        raise erro(decisao.codigo_erro or "PERMISSION_DENIED")


def fatos_entrada(entrada: Entrada, ator_id: uuid.UUID) -> FatosEntrada:
    usuario = _usuario_ativo(ator_id)
    le_gestao = permissoes.le_gestao(ator_id)
    return FatosEntrada(
        ator_id=ator_id,
        ator_admin=usuario.admin,
        tem_permissao_validar=usuario.admin or permissoes.pode(ator_id, "entradas.validar"),
        registrada_por_id=entrada.registrada_por_id,
        situacao=SituacaoEntrada(entrada.situacao),
        tem_permissao_estornar=usuario.admin or permissoes.pode(ator_id, PERM_FINANCEIRO_ESTORNAR),
        ator_le_gestao=le_gestao,
        saida_liquidada=entrada.saida is not None and entrada.saida.situacao == SituacaoSaida.LIQUIDADA.value,
    )


def exigir_comando_entrada(entrada: Entrada, ator_id: uuid.UUID, comando: ComandoEntrada) -> None:
    decisao = avaliar_entrada(comando, fatos_entrada(entrada, ator_id))
    if not decisao.pode:
        raise erro(decisao.codigo_erro or "PERMISSION_DENIED")


def _diferenca_pendente_para_liquidar(saida: Saida) -> bool:
    prestacao = saida.prestacao_vigente()
    if prestacao is None:
        return True
    try:
        avaliar_liquidacao(
            situacao=SituacaoSaida(saida.situacao),
            valor_prestacao=prestacao.valor,
            total_enviado=saida.total_enviado(),
            total_devolvido_validado=saida.total_devolvido_validado(),
            tem_devolucao_em_validacao=saida.devolucoes.filter(
                situacao=SituacaoEntrada.EM_VALIDACAO.value
            ).exists(),
            tem_complemento_em_andamento=saida.complemento_em_andamento() is not None,
            tem_complemento_aprovado_sem_envio=saida.complemento_aprovado_pendente_envio() is not None,
            justificativa="conferencia",
        )
    except ErroDeRegraSaida:
        return True
    return False


def fatos_saida(saida: Saida, ator_id: uuid.UUID) -> FatosSaida:
    usuario = _usuario_ativo(ator_id)
    le_gestao = permissoes.le_gestao(ator_id)
    perms = frozenset(permissoes.permissoes_de(ator_id)) if le_gestao or usuario.admin else frozenset()
    prestacao = saida.prestacao_vigente()
    total_enviado = saida.total_enviado()
    tem_comp_pendente = saida.complemento_aprovado_pendente_envio() is not None
    tem_comp_andamento = saida.complemento_em_andamento() is not None
    tem_dev_pend = saida.devolucoes.filter(situacao=SituacaoEntrada.EM_VALIDACAO.value).exists()
    situacao = SituacaoSaida(saida.situacao)
    return FatosSaida(
        ator_id=ator_id,
        ator_admin=usuario.admin,
        ator_le_gestao=le_gestao,
        permissoes_ator=perms,
        solicitante_id=saida.solicitante_id,
        situacao=situacao,
        tem_complemento_aprovado_para_enviar=tem_comp_pendente,
        tem_complemento_em_andamento=tem_comp_andamento,
        tem_excesso_para_complemento=prestacao is not None and prestacao.valor > total_enviado,
        tem_devolucao_em_validacao=tem_dev_pend,
        tem_saldo_para_devolver=total_enviado > saida.total_devolvido_ativo(),
        diferenca_pendente_acerto=(
            _diferenca_pendente_para_liquidar(saida) if situacao == SituacaoSaida.EM_CONFERENCIA else False
        ),
    )


def exigir_comando_saida(saida: Saida, ator_id: uuid.UUID, comando: ComandoSaida) -> None:
    decisao = avaliar_saida(comando, fatos_saida(saida, ator_id))
    if not decisao.pode:
        raise erro(decisao.codigo_erro or "PERMISSION_DENIED")
