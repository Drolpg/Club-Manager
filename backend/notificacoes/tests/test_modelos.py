"""NOT-R04 e NOT-R05: a notificação é um registro. Só ganha a data de leitura e o resultado do envio."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from notificacoes.models import Notificacao, NotificacaoImutavel, SituacaoDoEmail

pytestmark = pytest.mark.django_db


def _criar(**extra: Any) -> Notificacao:
    dados: dict[str, Any] = {
        "destinatario_id": uuid.uuid7(),
        "tipo": "teste.fato",
        "pede_acao": False,
        "titulo": "Título",
        "texto": "Texto",
        "item_tipo": "usuario",
        "item_id": uuid.uuid7(),
        "caminho": "/",
        "chave": "fato:1",
        "email_situacao": SituacaoDoEmail.PENDENTE,
    }
    dados.update(extra)
    return Notificacao.objects.create(**dados)


@pytest.mark.parametrize(
    ("campo", "novo"),
    [
        ("titulo", "Outro título"),
        ("texto", "Outro texto"),
        ("tipo", "teste.outro"),
        ("pede_acao", True),
        ("item_tipo", "outro"),
        ("item_id", uuid.uuid7()),
        ("caminho", "/outro"),
        ("destinatario_id", uuid.uuid7()),
        ("chave", "fato:2"),
    ],
)
def test_not_r05_o_modelo_recusa_alterar_o_conteudo(campo: str, novo: Any) -> None:
    notificacao = _criar()
    original = getattr(notificacao, campo)

    setattr(notificacao, campo, novo)
    with pytest.raises(NotificacaoImutavel):
        notificacao.save()

    assert getattr(Notificacao.objects.get(pk=notificacao.pk), campo) == original


def test_not_r05_alterar_o_conteudo_fora_do_update_fields_nao_e_gravado_nem_recusado() -> None:
    notificacao = _criar()
    notificacao.titulo = "Mudou só na memória"

    notificacao.save(update_fields=["email_tentativas"])

    assert Notificacao.objects.get(pk=notificacao.pk).titulo == "Título"


def test_not_r05_nenhuma_notificacao_e_apagada() -> None:
    notificacao = _criar()

    with pytest.raises(NotificacaoImutavel):
        notificacao.delete()

    assert Notificacao.objects.filter(pk=notificacao.pk).exists()


def test_o_resultado_do_envio_pode_ser_gravado() -> None:
    notificacao = _criar()
    agora = timezone.now()

    notificacao.email_situacao = SituacaoDoEmail.ENVIADO
    notificacao.email_enviado_em = agora
    notificacao.email_tentativas = 1
    notificacao.save(update_fields=["email_situacao", "email_enviado_em", "email_tentativas"])

    gravada = Notificacao.objects.get(pk=notificacao.pk)
    assert (gravada.email_situacao, gravada.email_enviado_em, gravada.email_tentativas) == (
        SituacaoDoEmail.ENVIADO,
        agora,
        1,
    )


def test_not_r04_marcar_lida_preenche_a_data() -> None:
    notificacao = _criar()
    agora = timezone.now()

    notificacao.marcar_lida(agora)
    notificacao.save(update_fields=["lida_em"])

    assert Notificacao.objects.get(pk=notificacao.pk).lida_em == agora


def test_not_r04_marcar_lida_de_novo_nao_muda_a_data_da_primeira_leitura() -> None:
    notificacao = _criar()
    primeira = timezone.now()
    notificacao.marcar_lida(primeira)
    notificacao.save(update_fields=["lida_em"])

    notificacao.marcar_lida(primeira + timedelta(hours=1))
    notificacao.save(update_fields=["lida_em"])

    assert Notificacao.objects.get(pk=notificacao.pk).lida_em == primeira


def test_not_r04_o_modelo_recusa_trocar_uma_data_de_leitura_ja_preenchida() -> None:
    notificacao = _criar()
    primeira = timezone.now()
    notificacao.marcar_lida(primeira)
    notificacao.save(update_fields=["lida_em"])

    notificacao.lida_em = primeira + timedelta(hours=1)
    with pytest.raises(NotificacaoImutavel):
        notificacao.save(update_fields=["lida_em"])

    assert Notificacao.objects.get(pk=notificacao.pk).lida_em == primeira


def test_not_r02_uma_notificacao_por_destinatario_e_chave() -> None:
    primeira = _criar()

    with pytest.raises(IntegrityError), transaction.atomic():
        _criar(destinatario_id=primeira.destinatario_id, chave=primeira.chave)


def test_o_id_e_um_uuid_7() -> None:
    assert _criar().id.version == 7
