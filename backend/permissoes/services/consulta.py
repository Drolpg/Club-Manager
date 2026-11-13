"""Perguntas sobre o que um usuário pode. É o que a API pública do módulo expõe.

Não há cache: cada pergunta consulta o banco, e por isso uma mudança vale na requisição seguinte (RF-021).
"""

import uuid
from dataclasses import dataclass

from django.db.models import Q

from acesso import public as acesso
from kernel.errors import BusinessError
from permissoes import catalogo
from permissoes.domain.resolucao import ACESSO_TOTAL, Fatos, Grupo, Origem, resolver_permissoes
from permissoes.models import AlvoDaConcessao, Cargo, Classificacao, Concessao, Setor
from permissoes.services.autorizacao import exigir_admin


@dataclass(frozen=True)
class ItemInfo:
    """Um cargo ou setor, para os outros módulos. Não é o modelo persistido."""

    id: uuid.UUID
    nome: str
    ativo: bool


@dataclass(frozen=True)
class ClassificacaoInfo:
    cargo: ItemInfo
    setores: tuple[ItemInfo, ...]


@dataclass(frozen=True)
class PermissaoDoUsuario:
    codigo: str
    nome: str
    origens: tuple[Origem, ...]


@dataclass(frozen=True)
class DetalheDoUsuario:
    """O que o painel e a página inicial mostram: classificação e permissões com origens."""

    cargo: ItemInfo | None
    setores: tuple[ItemInfo, ...]
    permissoes: tuple[PermissaoDoUsuario, ...]


def le_gestao(usuario_id: uuid.UUID) -> bool:
    """Lê os dados de gestão quem é admin ativo, ou é ativo e tem cargo ativo (PER-R10)."""
    usuario = acesso.usuario_por_id(usuario_id)
    if usuario is None or not usuario.ativo:
        return False
    if usuario.admin:
        return True
    return Classificacao.objects.filter(usuario_id=usuario_id, cargo__ativo=True).exists()


def _permissoes_por_grupo(concessoes: list[Concessao], campo: str) -> dict[uuid.UUID, frozenset[str]]:
    por_grupo: dict[uuid.UUID, set[str]] = {}
    for concessao in concessoes:
        grupo_id = getattr(concessao, campo)
        if grupo_id is not None:
            por_grupo.setdefault(grupo_id, set()).add(concessao.permissao)
    return {grupo_id: frozenset(codigos) for grupo_id, codigos in por_grupo.items()}


def permissoes_de(usuario_id: uuid.UUID) -> dict[str, list[Origem]]:
    """Cada permissão do usuário com todas as origens dela (PER-R01 a PER-R05). Usuário inexistente: `{}`."""
    usuario = acesso.usuario_por_id(usuario_id)
    if usuario is None:
        return {}

    classificacao = (
        Classificacao.objects.select_related("cargo")
        .prefetch_related("setores")
        .filter(pk=usuario_id)
        .first()
    )
    cargo = classificacao.cargo if classificacao else None
    setores = list(classificacao.setores.all()) if classificacao else []

    de_quem_e = Q(alvo_tipo=AlvoDaConcessao.USUARIO, usuario_id=usuario_id)
    if cargo is not None:
        de_quem_e |= Q(alvo_tipo=AlvoDaConcessao.CARGO, cargo=cargo)
    if setores:
        de_quem_e |= Q(alvo_tipo=AlvoDaConcessao.SETOR, setor__in=setores)
    concessoes = list(Concessao.objects.filter(de_quem_e, revogada_em__isnull=True))
    do_cargo = _permissoes_por_grupo(concessoes, "cargo_id")
    dos_setores = _permissoes_por_grupo(concessoes, "setor_id")

    fatos = Fatos(
        ativo=usuario.ativo,
        admin=usuario.admin,
        catalogo=catalogo.mapa_para_resolucao(),
        cargo=Grupo(cargo.id, cargo.nome, cargo.ativo, do_cargo.get(cargo.id, frozenset()))
        if cargo
        else None,
        setores=[Grupo(s.id, s.nome, s.ativo, dos_setores.get(s.id, frozenset())) for s in setores],
        individuais=frozenset(c.permissao for c in concessoes if c.alvo_tipo == AlvoDaConcessao.USUARIO),
    )
    return resolver_permissoes(fatos)


def pode(usuario_id: uuid.UUID, codigo: str) -> bool:
    return codigo in permissoes_de(usuario_id)


def quem_pode(codigo: str) -> list[uuid.UUID]:
    """IDs dos usuários ativos que têm a permissão, admins incluídos.

    Reúne os candidatos pelas três origens e confirma cada um com `pode`, que aplica as regras de uma vez só.
    """
    if not catalogo.conhecida(codigo):
        return []
    candidatos = {admin.id for admin in acesso.admins_ativos()}

    ativas = Concessao.objects.filter(revogada_em__isnull=True)
    individuais = ativas.filter(
        alvo_tipo=AlvoDaConcessao.USUARIO, permissao__in=(codigo, ACESSO_TOTAL)
    ).values_list("usuario_id", flat=True)
    candidatos |= {uid for uid in individuais if uid is not None}
    cargos = ativas.filter(alvo_tipo=AlvoDaConcessao.CARGO, permissao=codigo).values("cargo_id")
    setores = ativas.filter(alvo_tipo=AlvoDaConcessao.SETOR, permissao=codigo).values("setor_id")
    candidatos |= set(Classificacao.objects.filter(cargo_id__in=cargos).values_list("usuario_id", flat=True))
    candidatos |= set(Classificacao.objects.filter(setores__in=setores).values_list("usuario_id", flat=True))

    return sorted(uid for uid in candidatos if pode(uid, codigo))


def _item(item: Cargo | Setor) -> ItemInfo:
    return ItemInfo(id=item.id, nome=item.nome, ativo=item.ativo)


def classificacao_de(usuario_id: uuid.UUID) -> ClassificacaoInfo | None:
    classificacao = (
        Classificacao.objects.select_related("cargo")
        .prefetch_related("setores")
        .filter(pk=usuario_id)
        .first()
    )
    if classificacao is None:
        return None
    return ClassificacaoInfo(
        cargo=_item(classificacao.cargo),
        setores=tuple(_item(s) for s in classificacao.setores.all()),
    )


def detalhe_de(usuario_id: uuid.UUID) -> DetalheDoUsuario:
    """Classificação e permissões com origens de um usuário. Usuário inexistente: `NOT_FOUND`."""
    if acesso.usuario_por_id(usuario_id) is None:
        raise BusinessError("NOT_FOUND", "Usuário não encontrado.", status=404)
    info = classificacao_de(usuario_id)
    nomes = {p.codigo: p.nome for p in catalogo.listar()}
    return DetalheDoUsuario(
        cargo=info.cargo if info else None,
        setores=info.setores if info else (),
        permissoes=tuple(
            PermissaoDoUsuario(codigo, nomes[codigo], tuple(origens))
            for codigo, origens in sorted(permissoes_de(usuario_id).items())
        ),
    )


def detalhe_para_admin(ator_id: uuid.UUID, usuario_id: uuid.UUID) -> DetalheDoUsuario:
    """O detalhe de outro usuário é só do admin (PER-R09); a rota exige e o serviço confere de novo."""
    exigir_admin(ator_id)
    return detalhe_de(usuario_id)
