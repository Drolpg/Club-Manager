"""Autorização na camada de serviço sobre as APIs públicas de `acesso` e `permissoes`."""

import uuid

from acesso import public as acesso
from financeiro.domain.autorizacao import FatosCobranca, FatosEntrada, avaliar_cobranca, avaliar_entrada
from financeiro.domain.transicoes import ComandoCobranca, ComandoEntrada, SituacaoCobranca, SituacaoEntrada
from financeiro.erros import erro
from financeiro.models import Cobranca, Entrada
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
    return FatosEntrada(
        ator_id=ator_id,
        ator_admin=usuario.admin,
        tem_permissao_validar=usuario.admin or permissoes.pode(ator_id, "entradas.validar"),
        registrada_por_id=entrada.registrada_por_id,
        situacao=SituacaoEntrada(entrada.situacao),
    )


def exigir_comando_entrada(entrada: Entrada, ator_id: uuid.UUID, comando: ComandoEntrada) -> None:
    decisao = avaliar_entrada(comando, fatos_entrada(entrada, ator_id))
    if not decisao.pode:
        raise erro(decisao.codigo_erro or "PERMISSION_DENIED")
