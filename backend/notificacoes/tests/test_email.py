"""E-mail das notificações: conteúdo, dispensa, idempotência, nova tentativa e falha definitiva (CP3)."""

import re
import smtplib
import uuid
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.core import mail
from django.test import override_settings

from notificacoes import public, tasks
from notificacoes.models import Notificacao, SituacaoDoEmail
from notificacoes.services import email, preferencias
from notificacoes.tests.fakes import ServidorDeEmailInstavel
from tests.apoio import Situacao, Usuario

pytestmark = pytest.mark.django_db

SITE = "https://clube.exemplo"


@pytest.fixture(autouse=True)
def _executar_na_hora_o_que_roda_depois_do_commit() -> Iterator[None]:
    with mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()):
        yield


@pytest.fixture
def servidor_instavel() -> Iterator[type[ServidorDeEmailInstavel]]:
    ServidorDeEmailInstavel.reiniciar(falhas=0)
    mailers = {"default": {"BACKEND": "notificacoes.tests.fakes.ServidorDeEmailInstavel"}}
    with override_settings(MAILERS=mailers):
        yield ServidorDeEmailInstavel
    ServidorDeEmailInstavel.reiniciar(falhas=0)


def _notificar(tipo: str, destinatario: Usuario, chave: str = "fato:1") -> None:
    public.notificar(
        tipo=tipo,
        destinatarios=[destinatario.id],
        titulo="Novo diretor para classificar",
        texto="Bia concluiu o cadastro e aguarda a classificação.",
        item_tipo="usuario",
        item_id=uuid.uuid7(),
        caminho="/admin/usuarios/123",
        chave=chave,
    )


def _pendente(tipo: str, destinatario: Usuario) -> Notificacao:
    """Cria a notificação sem enviar, para os testes que chamam o envio diretamente."""
    with mock.patch.object(tasks.enviar_email, "delay"):
        _notificar(tipo, destinatario)
    return Notificacao.objects.get(destinatario_id=destinatario.id)


def test_ca03_o_que_pede_acao_vai_por_email_mesmo_com_os_informativos_desligados(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    preferencias.alterar(diretor.id, email_informativos=False)
    mail.outbox.clear()

    _notificar(pede_acao, diretor)

    assert [m.to for m in mail.outbox] == [[diretor.email]]
    assert Notificacao.objects.get().email_situacao == SituacaoDoEmail.ENVIADO


def test_o_informativo_vai_por_email_quando_o_destinatario_nao_desligou(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    _, informativo = tipos_de_teste
    mail.outbox.clear()

    _notificar(informativo, diretor)

    assert [m.to for m in mail.outbox] == [[diretor.email]]


def test_ca04_informativo_com_email_desligado_nao_envia_nenhum_email(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    _, informativo = tipos_de_teste
    preferencias.alterar(diretor.id, email_informativos=False)
    mail.outbox.clear()

    _notificar(informativo, diretor)

    assert mail.outbox == []
    notificacao = Notificacao.objects.get()
    assert (notificacao.email_situacao, notificacao.email_tentativas) == (SituacaoDoEmail.DISPENSADO, 0)


def test_ca08_o_email_traz_o_titulo_o_texto_e_o_link_do_item_sem_token(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    mail.outbox.clear()

    _notificar(pede_acao, diretor)

    mensagem = mail.outbox[0]
    assert mensagem.subject == "Novo diretor para classificar"
    assert mensagem.body == (
        f"Bia concluiu o cadastro e aguarda a classificação.\n\n{SITE}/admin/usuarios/123"
    )
    assert re.findall(r"https?://\S+", mensagem.body) == [f"{SITE}/admin/usuarios/123"]
    assert not any(marca in mensagem.body for marca in ("?", "#", "token", "senha"))
    assert getattr(mensagem, "alternatives", []) == []


def test_o_email_nao_traz_dado_pessoal_alem_do_que_o_texto_diz(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    mail.outbox.clear()

    _notificar(pede_acao, diretor)

    corpo = " ".join([str(mail.outbox[0].subject), str(mail.outbox[0].body)])
    assert diretor.email not in corpo
    assert diretor.telefone not in corpo


def test_o_envio_registra_a_situacao_a_data_e_a_tentativa(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)
    assert notificacao.email_situacao == SituacaoDoEmail.PENDENTE

    email.enviar(notificacao.id)

    notificacao.refresh_from_db()
    assert notificacao.email_situacao == SituacaoDoEmail.ENVIADO
    assert notificacao.email_enviado_em is not None
    assert notificacao.email_tentativas == 1


def test_o_envio_e_idempotente_a_tarefa_duas_vezes_manda_um_email_so(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)
    mail.outbox.clear()

    tasks.enviar_email.delay(str(notificacao.id))
    tasks.enviar_email.delay(str(notificacao.id))

    assert len(mail.outbox) == 1
    notificacao.refresh_from_db()
    assert notificacao.email_tentativas == 1


@pytest.mark.parametrize(
    "situacao", [SituacaoDoEmail.ENVIADO, SituacaoDoEmail.DISPENSADO, SituacaoDoEmail.FALHOU]
)
def test_so_a_pendente_e_enviada(
    tipos_de_teste: tuple[str, str], diretor: Usuario, situacao: SituacaoDoEmail
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)
    Notificacao.objects.filter(pk=notificacao.pk).update(email_situacao=situacao)
    mail.outbox.clear()

    email.enviar(notificacao.id)

    assert mail.outbox == []
    notificacao.refresh_from_db()
    assert (notificacao.email_situacao, notificacao.email_tentativas) == (situacao, 0)


def test_notificacao_que_nao_existe_e_ignorada() -> None:
    mail.outbox.clear()

    email.enviar(uuid.uuid4())

    assert mail.outbox == []


def test_destinatario_que_ficou_inativo_antes_do_envio_e_dispensado(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)
    Usuario.objects.filter(pk=diretor.id).update(situacao=Situacao.INATIVO)
    mail.outbox.clear()

    email.enviar(notificacao.id)

    assert mail.outbox == []
    notificacao.refresh_from_db()
    assert notificacao.email_situacao == SituacaoDoEmail.DISPENSADO
    assert notificacao.email_enviado_em is None


def _executar_como_o_worker(notificacao: Notificacao) -> Any:
    """Roda a tarefa como um worker: novas tentativas e `on_failure` valem.

    Com `CELERY_TASK_EAGER_PROPAGATES` (configuração dos testes), o Celery relança a exceção antes de tentar
    de novo e antes de chamar `on_failure`, e as novas tentativas voltam a ler a configuração global. Por isso
    a propagação é desligada só aqui, no objeto de configuração do Celery; o resto da execução fica igual.
    """
    conf = tasks.enviar_email.app.conf
    propaga = conf.task_eager_propagates
    conf.task_eager_propagates = False
    try:
        return tasks.enviar_email.apply(args=[str(notificacao.id)])
    finally:
        conf.task_eager_propagates = propaga


def test_ca06_servidor_que_falha_duas_vezes_o_envio_e_tentado_de_novo_e_acaba_enviado(
    tipos_de_teste: tuple[str, str],
    diretor: Usuario,
    servidor_instavel: type[ServidorDeEmailInstavel],
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)
    servidor_instavel.reiniciar(falhas=2)

    resultado = _executar_como_o_worker(notificacao)

    notificacao.refresh_from_db()
    assert resultado.successful()
    assert servidor_instavel.chamadas == 3
    assert len(servidor_instavel.entregues) == 1
    assert (notificacao.email_situacao, notificacao.email_tentativas) == (SituacaoDoEmail.ENVIADO, 3)


def test_ca06_esgotadas_as_cinco_tentativas_a_falha_definitiva_fica_registrada(
    tipos_de_teste: tuple[str, str],
    diretor: Usuario,
    servidor_instavel: type[ServidorDeEmailInstavel],
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)
    servidor_instavel.reiniciar(falhas=99)

    resultado = _executar_como_o_worker(notificacao)

    notificacao.refresh_from_db()
    assert resultado.failed()
    assert servidor_instavel.chamadas == 5
    assert servidor_instavel.entregues == []
    assert (notificacao.email_situacao, notificacao.email_tentativas) == (SituacaoDoEmail.FALHOU, 5)
    # A notificação continua na caixa: só o canal de e-mail falhou.
    assert notificacao.lida_em is None
    assert notificacao.email_enviado_em is None


def test_ca06_uma_notificacao_que_falhou_nao_e_enviada_de_novo(
    tipos_de_teste: tuple[str, str],
    diretor: Usuario,
    servidor_instavel: type[ServidorDeEmailInstavel],
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)
    servidor_instavel.reiniciar(falhas=99)
    _executar_como_o_worker(notificacao)
    servidor_instavel.reiniciar(falhas=0)

    tasks.enviar_email.delay(str(notificacao.id))

    assert servidor_instavel.entregues == []


def test_cada_tentativa_que_falha_fica_contada_e_a_notificacao_segue_pendente(
    tipos_de_teste: tuple[str, str],
    diretor: Usuario,
    servidor_instavel: type[ServidorDeEmailInstavel],
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)
    servidor_instavel.reiniciar(falhas=99)

    with pytest.raises(smtplib.SMTPException):
        email.enviar(notificacao.id)

    notificacao.refresh_from_db()
    assert (notificacao.email_situacao, notificacao.email_tentativas) == (SituacaoDoEmail.PENDENTE, 1)


def test_a_nova_tentativa_vale_para_falha_de_rede_e_de_smtp() -> None:
    assert set(tasks.enviar_email.autoretry_for) == {OSError, smtplib.SMTPException}
    assert tasks.enviar_email.max_retries == 4
    assert tasks.enviar_email.retry_backoff == 60


def test_um_erro_de_programacao_nao_e_tentado_de_novo_e_marca_falhou(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    notificacao = _pendente(pede_acao, diretor)

    with mock.patch("notificacoes.services.email.send_mail", side_effect=ValueError("bug")) as envio:
        resultado = _executar_como_o_worker(notificacao)

    notificacao.refresh_from_db()
    assert resultado.failed()
    assert envio.call_count == 1
    assert (notificacao.email_situacao, notificacao.email_tentativas) == (SituacaoDoEmail.FALHOU, 1)
