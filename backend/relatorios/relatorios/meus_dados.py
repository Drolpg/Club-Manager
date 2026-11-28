""" "Meus dados" (RF-144, P25): três CSV num ZIP, só com os dados de quem pediu.

Não existe parâmetro de usuário: o conteúdo é sempre do `usuario_id` do contexto. As cobranças e os eventos
são percorridos página a página, pelas mesmas consultas do perfil.
"""

import uuid
from decimal import Decimal
from typing import Any

from django.utils import timezone

from acesso import public as acesso
from eventos import public as eventos
from financeiro import public as financeiro
from permissoes import public as permissoes
from relatorios.domain.documento import Coluna, Documento, Tabela, TipoDeColuna, Valor
from relatorios.relatorios import comum
from relatorios.tipos import Contexto

T = TipoDeColuna
_PAGINA = 50
_PAPEIS = {
    "PROPONENTE": "Proponente",
    "PRESENCA": "Presença",
    "PROPONENTE_E_PRESENCA": "Proponente e presença",
}
_RESPOSTAS = {"VOU": "Vou", "NAO_VOU": "Não vou"}


def _dados(usuario_id: uuid.UUID, texto: str) -> Documento:
    perfil = acesso.dados_do_perfil(usuario_id)
    classificacao = permissoes.classificacao_de(usuario_id)
    linhas: list[tuple[Valor, ...]] = []
    if perfil is not None:
        linhas = [
            ("Nome", perfil.nome),
            ("Nome de usuário", perfil.nome_de_usuario),
            ("E-mail", perfil.email),
            ("Telefone", perfil.telefone),
            ("Cargo", classificacao.cargo.nome if classificacao else ""),
            ("Setores", ", ".join(s.nome for s in classificacao.setores) if classificacao else ""),
        ]
    colunas = (Coluna("Campo", T.TEXTO), Coluna("Valor", T.TEXTO))
    return Documento("Dados", texto, (), (Tabela("Dados", colunas, tuple(linhas)),))


def _cobrancas(usuario_id: uuid.UUID, texto: str) -> Documento:
    linhas: list[tuple[Valor, ...]] = []
    antes: uuid.UUID | None = None
    while True:
        pagina = financeiro.cobrancas_do_devedor(usuario_id, antes=antes, limite=_PAGINA)
        for c in pagina.itens:
            pagamentos = "; ".join(
                f"{p.forma} em {comum.data(p.data_pagamento)} ({p.situacao})" for p in c.pagamentos
            )
            situacao = comum.legivel(c.situacao, comum.SITUACOES_DE_COBRANCA)
            linhas.append(
                (c.descricao, c.categoria_nome, Decimal(c.valor), c.vencimento, situacao, pagamentos)
            )
        if not pagina.tem_mais or not pagina.itens:
            break
        antes = pagina.itens[-1].id
    colunas = (
        Coluna("Descrição", T.TEXTO),
        Coluna("Categoria", T.TEXTO),
        Coluna("Valor", T.DINHEIRO),
        Coluna("Vencimento", T.DATA),
        Coluna("Situação", T.TEXTO),
        Coluna("Pagamentos", T.TEXTO),
    )
    return Documento("Cobranças", texto, (), (Tabela("Cobranças", colunas, tuple(linhas)),))


def _eventos(usuario_id: uuid.UUID, texto: str) -> Documento:
    linhas: list[tuple[Valor, ...]] = []
    antes: uuid.UUID | None = None
    while True:
        pagina = eventos.eventos_do_usuario(usuario_id, antes=antes, limite=_PAGINA)
        for e in pagina.itens:
            linhas.append(
                (
                    e.titulo,
                    timezone.localdate(e.inicio),
                    e.local,
                    e.categoria_nome,
                    comum.legivel(e.situacao, comum.SITUACOES_DE_EVENTO),
                    _PAPEIS.get(e.papel, e.papel),
                    _RESPOSTAS.get(e.resposta or "", ""),
                )
            )
        if not pagina.tem_mais or not pagina.itens:
            break
        antes = pagina.itens[-1].id
    colunas = (
        Coluna("Título", T.TEXTO),
        Coluna("Data", T.DATA),
        Coluna("Local", T.TEXTO),
        Coluna("Categoria", T.TEXTO),
        Coluna("Situação", T.TEXTO),
        Coluna("Papel", T.TEXTO),
        Coluna("Resposta", T.TEXTO),
    )
    return Documento("Eventos", texto, (), (Tabela("Eventos", colunas, tuple(linhas)),))


def meus_dados(_parametros: dict[str, Any], contexto: Contexto) -> list[Documento]:
    texto = f"Dados de quem pediu, em {comum.data(contexto.hoje)}"
    return [
        _dados(contexto.usuario_id, texto),
        _cobrancas(contexto.usuario_id, texto),
        _eventos(contexto.usuario_id, texto),
    ]
