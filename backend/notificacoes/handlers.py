"""Tratadores dos eventos de integração de `acesso` e `permissoes` (ADR-003).

Rodam na transação de quem publicou o evento: um erro aqui desfaz a operação que gerou o fato. Por isso só
montam o texto e chamam `notificar`, que faz o resto (filtro de ativos, preferências, e-mail depois do
commit).
Os quatro tipos são declarados aqui porque `acesso` e `permissoes` estão abaixo e não conhecem `notificacoes`.
"""

import uuid

from acesso import public as acesso
from kernel import events
from notificacoes import tipos
from notificacoes.services import envio
from permissoes import public as permissoes

CADASTRO_CONCLUIDO = "acesso.cadastro_concluido"
CLASSIFICACAO_ALTERADA = "permissoes.classificacao_alterada"
PAPEL_DE_ADMIN_ALTERADO = "acesso.papel_de_admin_alterado"
CONCESSAO_INDIVIDUAL_ALTERADA = "permissoes.concessao_individual_alterada"

# O texto da notificação cabe em 500 caracteres; o nome do usuário (até 120) é a única parte variável longa.
_NOME_MAXIMO = 200


def registrar() -> None:
    """Declara os tipos e registra os tratadores. Pode rodar mais de uma vez sem duplicar nada."""
    tipos.registrar_tipo(
        CADASTRO_CONCLUIDO,
        pede_acao=True,
        descricao="Um diretor concluiu o cadastro e aguarda a classificação pelo admin.",
    )
    tipos.registrar_tipo(
        CLASSIFICACAO_ALTERADA,
        pede_acao=False,
        descricao="O diretor foi classificado, reclassificado ou ficou sem cargo.",
    )
    tipos.registrar_tipo(
        PAPEL_DE_ADMIN_ALTERADO,
        pede_acao=False,
        descricao="O usuário ganhou ou perdeu o papel de admin.",
    )
    tipos.registrar_tipo(
        CONCESSAO_INDIVIDUAL_ALTERADA,
        pede_acao=False,
        descricao="O usuário ganhou ou perdeu uma permissão concedida a ele.",
    )
    events.subscribe(acesso.CadastroConcluido, ao_concluir_o_cadastro)
    events.subscribe(permissoes.ClassificacaoAlterada, ao_alterar_a_classificacao)
    events.subscribe(acesso.PapelDeAdminAlterado, ao_alterar_o_papel_de_admin)
    events.subscribe(permissoes.ConcessaoIndividualAlterada, ao_alterar_a_concessao_individual)


def _avisar_o_usuario(usuario_id: uuid.UUID, *, tipo: str, titulo: str, texto: str, fato: str) -> None:
    # Cada mudança é um fato novo, então a chave leva um UUID 7 (que carrega o instante) e nunca repete.
    envio.notificar(
        tipo=tipo,
        destinatarios=[usuario_id],
        titulo=titulo,
        texto=texto,
        item_tipo="usuario",
        item_id=usuario_id,
        caminho="/",
        chave=f"{fato}:{usuario_id}:{uuid.uuid7()}",
    )


def ao_concluir_o_cadastro(evento: acesso.CadastroConcluido) -> None:
    usuario = acesso.usuario_por_id(evento.usuario_id)
    if usuario is None:
        return
    nome = usuario.nome[:_NOME_MAXIMO]
    envio.notificar(
        tipo=CADASTRO_CONCLUIDO,
        destinatarios=[admin.id for admin in acesso.admins_ativos()],
        titulo="Novo diretor para classificar",
        texto=f"{nome} concluiu o cadastro e aguarda a classificação: cargo e setores.",
        item_tipo="usuario",
        item_id=usuario.id,
        caminho=f"/admin/usuarios/{usuario.id}",
        chave=f"cadastro-concluido:{usuario.id}",
    )


def ao_alterar_a_classificacao(evento: permissoes.ClassificacaoAlterada) -> None:
    classificacao = permissoes.classificacao_de(evento.usuario_id)
    if classificacao is None:
        texto = "Você ficou sem cargo."
    elif classificacao.setores:
        setores = ", ".join(setor.nome for setor in classificacao.setores)
        texto = f"Seu cargo agora é {classificacao.cargo.nome}, nos setores: {setores}."
    else:
        texto = f"Seu cargo agora é {classificacao.cargo.nome}, sem setores."
    _avisar_o_usuario(
        evento.usuario_id,
        tipo=CLASSIFICACAO_ALTERADA,
        titulo="Sua classificação mudou",
        texto=texto,
        fato="classificacao-alterada",
    )


def ao_alterar_o_papel_de_admin(evento: acesso.PapelDeAdminAlterado) -> None:
    texto = (
        "Você agora é administrador do clube."
        if evento.admin
        else "Você deixou de ser administrador do clube."
    )
    _avisar_o_usuario(
        evento.usuario_id,
        tipo=PAPEL_DE_ADMIN_ALTERADO,
        titulo="Seu papel de administrador mudou",
        texto=texto,
        fato="papel-de-admin-alterado",
    )


def ao_alterar_a_concessao_individual(evento: permissoes.ConcessaoIndividualAlterada) -> None:
    nome = permissoes.nome_da_permissao(evento.permissao) or evento.permissao
    verbo = "ganhou" if evento.concedida else "perdeu"
    _avisar_o_usuario(
        evento.usuario_id,
        tipo=CONCESSAO_INDIVIDUAL_ALTERADA,
        titulo="Suas permissões mudaram",
        texto=f"Você {verbo} a permissão “{nome}”.",
        fato="concessao-individual-alterada",
    )
