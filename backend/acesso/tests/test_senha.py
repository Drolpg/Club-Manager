import re
from datetime import datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from django.core import mail
from rest_framework.test import APIClient

from acesso.models import Situacao, Usuario
from acesso.tests.conftest import SENHA, criar_diretor, entrar
from auditoria import public as auditoria

pytestmark = pytest.mark.django_db

RECUPERAR = "/api/v1/acesso/senhas/recuperar/"
REDEFINIR = "/api/v1/acesso/senhas/redefinir/"
SESSAO = "/api/v1/acesso/sessao/"
NOVA_SENHA = "outra-frase-bem-comprida"


def _pedir(email: str) -> Any:
    return APIClient().post(RECUPERAR, {"email": email})


def _token(mensagem: Any) -> str:
    achado = re.search(r"https://clube\.exemplo/redefinir-senha/(\S+)", mensagem.body)
    assert achado, mensagem.body
    return achado.group(1)


def _token_para(email: str) -> str:
    mail.outbox.clear()
    _pedir(email)
    return _token(mail.outbox[-1])


def _relogio_adiantado(**tempo: int) -> Any:
    agora = datetime.now() + timedelta(**tempo)
    return mock.patch("django.contrib.auth.tokens.PasswordResetTokenGenerator._now", return_value=agora)


def test_ca24_resposta_e_igual_com_e_sem_conta_e_so_a_conta_ativa_recebe_email(diretor: Usuario) -> None:
    criar_diretor("pendente", Situacao.AGUARDANDO_VERIFICACAO)
    criar_diretor("inativo", Situacao.INATIVO)
    mail.outbox.clear()

    respostas = [
        _pedir(email)
        for email in ("BIA@exemplo.com", "ninguem@exemplo.com", "pendente@exemplo.com", "inativo@exemplo.com")
    ]

    assert {r.status_code for r in respostas} == {204}
    assert len({r.content for r in respostas}) == 1
    assert [m.to for m in mail.outbox] == [["bia@exemplo.com"]]


def test_ca25_link_dentro_do_prazo_troca_a_senha_e_encerra_as_sessoes(diretor: Usuario) -> None:
    sessao_antiga = APIClient()
    entrar(sessao_antiga, "bia")
    token = _token_para("bia@exemplo.com")

    with _relogio_adiantado(minutes=59):
        resposta = APIClient().post(REDEFINIR, {"token": token, "senha": NOVA_SENHA})

    assert resposta.status_code == 204
    assert sessao_antiga.get(SESSAO).json() == {"usuario": None}
    assert APIClient().post(SESSAO, {"identificador": "bia", "senha": SENHA}).status_code == 401
    assert APIClient().post(SESSAO, {"identificador": "bia", "senha": NOVA_SENHA}).status_code == 200


def test_ca25_o_mesmo_link_nao_funciona_de_novo(diretor: Usuario) -> None:
    token = _token_para("bia@exemplo.com")
    APIClient().post(REDEFINIR, {"token": token, "senha": NOVA_SENHA})

    de_novo = APIClient().post(REDEFINIR, {"token": token, "senha": "mais-uma-frase-comprida"})

    assert de_novo.status_code == 400
    assert de_novo.json()["error"]["code"] == "LINK_INVALIDO"
    assert Usuario.objects.get(pk=diretor.pk).check_password(NOVA_SENHA)


def test_ca26_link_com_mais_de_uma_hora_e_recusado(diretor: Usuario) -> None:
    token = _token_para("bia@exemplo.com")

    with _relogio_adiantado(minutes=61):
        resposta = APIClient().post(REDEFINIR, {"token": token, "senha": NOVA_SENHA})

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "LINK_INVALIDO"
    assert Usuario.objects.get(pk=diretor.pk).check_password(SENHA)


@pytest.mark.parametrize(
    "token", ["", "lixo", "nao-e-uuid.abc-123", "019a0000-0000-7000-8000-000000000000.abc-123"]
)
def test_link_malformado_ou_de_conta_inexistente_e_recusado(diretor: Usuario, token: str) -> None:
    resposta = APIClient().post(REDEFINIR, {"token": token, "senha": NOVA_SENHA})

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] in ("LINK_INVALIDO", "VALIDATION_ERROR")
    assert Usuario.objects.get(pk=diretor.pk).check_password(SENHA)


def test_senha_fraca_e_recusada_e_o_link_continua_valendo(diretor: Usuario) -> None:
    token = _token_para("bia@exemplo.com")

    fraca = APIClient().post(REDEFINIR, {"token": token, "senha": "12345678"})
    boa = APIClient().post(REDEFINIR, {"token": token, "senha": NOVA_SENHA})

    assert fraca.status_code == 400
    assert fraca.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "senha" in fraca.json()["error"]["details"]
    assert boa.status_code == 204


def test_conta_desativada_depois_do_pedido_nao_redefine(diretor: Usuario) -> None:
    token = _token_para("bia@exemplo.com")
    Usuario.objects.filter(pk=diretor.pk).update(situacao=Situacao.INATIVO)

    resposta = APIClient().post(REDEFINIR, {"token": token, "senha": NOVA_SENHA})

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "LINK_INVALIDO"


def test_redefinicao_e_auditada_sem_a_senha_nem_o_link(diretor: Usuario) -> None:
    token = _token_para("bia@exemplo.com")
    APIClient().post(REDEFINIR, {"token": token, "senha": NOVA_SENHA})

    historico = auditoria.historico_do_item("usuario", diretor.id)

    assert [r.acao for r in historico] == ["SENHA_REDEFINIDA"]
    assert historico[0].ator_id == diretor.id
    assert NOVA_SENHA not in str(historico)
    assert token not in str(historico)


def test_redefinir_a_senha_libera_o_login_bloqueado_por_tentativas(diretor: Usuario) -> None:
    for _ in range(5):
        APIClient().post(SESSAO, {"identificador": "bia", "senha": "senha-errada-123"})
    token = _token_para("bia@exemplo.com")
    APIClient().post(REDEFINIR, {"token": token, "senha": NOVA_SENHA})

    resposta = APIClient().post(SESSAO, {"identificador": "bia", "senha": NOVA_SENHA})

    assert resposta.status_code == 200


def test_pedido_de_recuperacao_e_limitado_a_tres_por_hora(diretor: Usuario) -> None:
    mail.outbox.clear()

    respostas = [_pedir("bia@exemplo.com") for _ in range(4)]

    assert {r.status_code for r in respostas} == {204}
    assert len(mail.outbox) == 3


def test_o_token_de_recuperacao_nunca_passa_pela_fila(diretor: Usuario) -> None:
    from acesso import tasks

    with mock.patch.object(tasks.enviar_email_de_recuperacao, "delay") as enfileirar:
        _pedir("bia@exemplo.com")

    enfileirar.assert_called_once_with(str(diretor.id))
