"""`notificacoes.public.resumo_da_caixa`: só a contagem de não lidas do usuário pedido (CA-05)."""

import dataclasses
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from notificacoes import public
from notificacoes.models import Notificacao, SituacaoDoEmail
from tests.apoio import Usuario, criar_diretor

pytestmark = pytest.mark.django_db


def _notificacao(usuario: Usuario, *, lida: bool = False) -> Notificacao:
    return Notificacao.objects.create(
        destinatario_id=usuario.id,
        pede_acao=False,
        email_situacao=SituacaoDoEmail.DISPENSADO,
        tipo="teste.informativo",
        titulo="Aviso",
        texto="Texto",
        item_tipo="usuario",
        item_id=uuid.uuid4(),
        caminho="/",
        chave=f"chave:{uuid.uuid4()}",
        lida_em=timezone.now() - timedelta(minutes=1) if lida else None,
    )


def test_conta_so_as_nao_lidas_do_usuario_pedido() -> None:
    ana, bia = criar_diretor("ana"), criar_diretor("bia")
    _notificacao(ana)
    _notificacao(ana)
    _notificacao(ana, lida=True)
    _notificacao(bia)

    assert public.resumo_da_caixa(ana.id).nao_lidas == 2
    assert public.resumo_da_caixa(bia.id).nao_lidas == 1


def test_usuario_sem_notificacao_tem_zero() -> None:
    assert public.resumo_da_caixa(uuid.uuid4()).nao_lidas == 0


def test_so_expoe_a_contagem() -> None:
    ana = criar_diretor("ana")
    _notificacao(ana)

    resumo = public.resumo_da_caixa(ana.id)

    assert {c.name for c in dataclasses.fields(resumo)} == {"nao_lidas"}
