"""O perfil do usuário (RF-100, RF-101, RF-142): só leitura, sem tabela e sem cópia.

Cada seção é lida, na hora, do módulo dono pela API pública. A regra "dono ou admin" é conferida antes de
qualquer consulta, e quem não pode recebe 403 até para um ID que não existe. A consulta do admin ao perfil de
outro usuário é auditada na mesma transação, sem dado pessoal. As notificações são só de quem as tem.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from acesso import public as acesso
from auditoria import public as auditoria
from eventos import public as eventos_publicos
from financeiro import public as financeiro
from notificacoes import public as notificacoes
from permissoes import public as permissoes
from relatorios.domain.acesso_ao_perfil import pode_ver_perfil
from relatorios.erros import erro, limite_invalido

LIMITE_PADRAO = 10
LIMITE_MAXIMO = 50


@dataclass(frozen=True)
class DadosDoPerfil:
    id: uuid.UUID
    nome: str
    nome_de_usuario: str
    email: str
    telefone: str
    ativo: bool
    admin: bool
    cadastrado_em: datetime
    cargo: str | None
    setores: list[str]


@dataclass(frozen=True)
class PerfilCompleto:
    """As quatro seções; `notificacoes` é nulo quando o alvo não é quem consulta."""

    dados: DadosDoPerfil
    cobrancas: financeiro.PaginaDeCobrancasDoDevedor
    eventos: eventos_publicos.PaginaDeEventosDoUsuario
    notificacoes: notificacoes.ResumoDaCaixa | None


def _conferir(ator_id: uuid.UUID, alvo_id: uuid.UUID) -> bool:
    """Quem pode ver, antes de qualquer consulta. Devolve se o ator é admin; senão, 403."""
    ator = acesso.usuario_por_id(ator_id)
    if ator is None or not ator.ativo:
        raise erro("PERMISSION_DENIED")
    if not pode_ver_perfil(ator_id=ator_id, alvo_id=alvo_id, ator_e_admin=ator.admin):
        raise erro("PERMISSION_DENIED")
    return ator.admin


def _limite(limite: int) -> int:
    if not 1 <= limite <= LIMITE_MAXIMO:
        raise limite_invalido(LIMITE_MAXIMO)
    return limite


def _exigir_existente(alvo_id: uuid.UUID) -> None:
    """Só chega aqui quem pode ver: o dono existe sempre, e o admin recebe 404 para ID inexistente."""
    if acesso.usuario_por_id(alvo_id) is None:
        raise erro("NOT_FOUND")


def _auditar(ator_id: uuid.UUID, alvo_id: uuid.UUID, ator_e_admin: bool, secao: str) -> None:
    """O admin lendo o perfil de outro deixa registro; o usuário lendo o próprio, não (regra 5)."""
    if ator_e_admin and ator_id != alvo_id:
        auditoria.registrar(
            ator_id=ator_id,
            acao="PERFIL_CONSULTADO",
            item_tipo="usuario",
            item_id=alvo_id,
            dados={"secao": secao},
        )


@transaction.atomic
def dados(ator_id: uuid.UUID, alvo_id: uuid.UUID) -> DadosDoPerfil:
    admin = _conferir(ator_id, alvo_id)
    info = acesso.dados_do_perfil(alvo_id)
    if info is None:
        raise erro("NOT_FOUND")
    classificacao = permissoes.classificacao_de(alvo_id)
    _auditar(ator_id, alvo_id, admin, "dados")
    return DadosDoPerfil(
        id=info.id,
        nome=info.nome,
        nome_de_usuario=info.nome_de_usuario,
        email=info.email,
        telefone=info.telefone,
        ativo=info.ativo,
        admin=info.admin,
        cadastrado_em=info.cadastrado_em,
        cargo=classificacao.cargo.nome if classificacao else None,
        setores=[setor.nome for setor in classificacao.setores] if classificacao else [],
    )


@transaction.atomic
def cobrancas(
    ator_id: uuid.UUID,
    alvo_id: uuid.UUID,
    *,
    antes: uuid.UUID | None = None,
    limite: int = LIMITE_PADRAO,
) -> financeiro.PaginaDeCobrancasDoDevedor:
    admin = _conferir(ator_id, alvo_id)
    limite = _limite(limite)
    _exigir_existente(alvo_id)
    pagina = financeiro.cobrancas_do_devedor(alvo_id, antes=antes, limite=limite)
    _auditar(ator_id, alvo_id, admin, "cobrancas")
    return pagina


@transaction.atomic
def eventos(
    ator_id: uuid.UUID,
    alvo_id: uuid.UUID,
    *,
    antes: uuid.UUID | None = None,
    limite: int = LIMITE_PADRAO,
) -> eventos_publicos.PaginaDeEventosDoUsuario:
    admin = _conferir(ator_id, alvo_id)
    limite = _limite(limite)
    _exigir_existente(alvo_id)
    pagina = eventos_publicos.eventos_do_usuario(alvo_id, antes=antes, limite=limite)
    _auditar(ator_id, alvo_id, admin, "eventos")
    return pagina


def resumo_de_notificacoes(ator_id: uuid.UUID, alvo_id: uuid.UUID) -> notificacoes.ResumoDaCaixa | None:
    """Só quando o alvo é o próprio ator: a caixa de outra pessoa nunca é consultada (RN-009)."""
    _conferir(ator_id, alvo_id)
    if ator_id != alvo_id:
        return None
    return notificacoes.resumo_da_caixa(alvo_id)


@transaction.atomic
def perfil(ator_id: uuid.UUID, alvo_id: uuid.UUID) -> PerfilCompleto:
    """O perfil inteiro: dados, a primeira página de cobranças e de eventos e, só no próprio, o resumo."""
    return PerfilCompleto(
        dados=dados(ator_id, alvo_id),
        cobrancas=cobrancas(ator_id, alvo_id),
        eventos=eventos(ator_id, alvo_id),
        notificacoes=resumo_de_notificacoes(ator_id, alvo_id),
    )
