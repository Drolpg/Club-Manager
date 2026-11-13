import re
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from acesso import tasks
from acesso.domain.cadastro import cadastro_vencido
from acesso.models import Convite, Situacao, Usuario
from acesso.public import CadastroConcluido
from acesso.services import cadastro
from acesso.tests.conftest import SENHA, criar_diretor
from auditoria import public as auditoria
from kernel import events

pytestmark = pytest.mark.django_db

CONVITES = "/api/v1/acesso/convites/"
CADASTROS = "/api/v1/acesso/cadastros/"
VERIFICACOES = "/api/v1/acesso/verificacoes/"
REENVIAR = f"{VERIFICACOES}reenviar/"
SESSAO = "/api/v1/acesso/sessao/"


@pytest.fixture(autouse=True)
def _executar_na_hora_o_que_roda_depois_do_commit(request: pytest.FixtureRequest) -> Any:
    """Cada teste roda dentro de uma transação que nunca é confirmada, então o que o código agenda para
    depois do commit não rodaria. Aqui isso roda na hora. O teste marcado com `sem_atalho_de_commit` prova,
    sem este atalho, que o envio só é enfileirado depois do commit.
    """
    if request.node.get_closest_marker("sem_atalho_de_commit"):
        yield
        return
    with mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()):
        yield


@pytest.fixture
def token(client_admin: APIClient) -> str:
    link: str = client_admin.post(CONVITES).json()["link"]
    return link.rsplit("/", 1)[1]


def _dados(token: str, **extra: str) -> dict[str, str]:
    dados = {
        "token": token,
        "nome": "Caio Convidado",
        "nome_de_usuario": "caio",
        "telefone": "(11) 97777-6666",
        "email": "Caio@Exemplo.com",
        "senha": SENHA,
    }
    dados.update(extra)
    return dados


def _cadastrar(token: str, **extra: str) -> Any:
    return APIClient().post(CADASTROS, _dados(token, **extra))


def _token_de_verificacao(mensagem: Any) -> str:
    achado = re.search(r"https://clube\.exemplo/verificar/(\S+)", mensagem.body)
    assert achado, mensagem.body
    return achado.group(1)


def _depois(**tempo: int) -> Any:
    return mock.patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(**tempo))


def _convite_ativo(token: str) -> bool:
    return bool(APIClient().post(f"{CONVITES}consultar/", {"token": token}).status_code == 204)


def test_cadastro_vence_em_24_horas() -> None:
    criado = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)

    assert not cadastro_vencido(agora=criado + timedelta(hours=23, minutes=59), criado_em=criado)
    assert cadastro_vencido(agora=criado + timedelta(hours=24), criado_em=criado)


def test_ca09_cadastro_valido_fica_aguardando_usa_o_convite_e_envia_o_link(token: str) -> None:
    mail.outbox.clear()

    resposta = _cadastrar(token)

    assert resposta.status_code == 201
    usuario = Usuario.objects.get(nome_de_usuario="caio")
    assert usuario.situacao == Situacao.AGUARDANDO_VERIFICACAO
    assert usuario.admin is False
    assert usuario.email == "caio@exemplo.com"
    assert usuario.telefone == "11977776666"
    assert usuario.check_password(SENHA)
    assert not _convite_ativo(token)
    assert Convite.objects.get().usado_por == usuario
    assert [m.to for m in mail.outbox] == [["caio@exemplo.com"]]
    assert _token_de_verificacao(mail.outbox[0])


def test_resposta_do_cadastro_nao_devolve_dados_nem_abre_sessao(token: str) -> None:
    client = APIClient()

    resposta = client.post(CADASTROS, _dados(token))

    assert resposta.json() == {"situacao": "AGUARDANDO_VERIFICACAO"}
    assert client.get(SESSAO).json() == {"usuario": None}


def test_ca11_verificar_ativa_a_conta_sem_cargo_e_publica_o_cadastro_concluido(
    token: str, admin: Usuario, tratadores_de_eventos: None
) -> None:
    events.unsubscribe_all_for_tests()  # só o tratador do teste: `acesso` não manda e-mail
    publicados: list[CadastroConcluido] = []
    events.subscribe(CadastroConcluido, publicados.append)
    criar_diretor("inativo.admin", Situacao.INATIVO)
    Usuario.objects.filter(nome_de_usuario="inativo.admin").update(admin=True)
    _cadastrar(token)
    token_de_verificacao = _token_de_verificacao(mail.outbox[-1])
    mail.outbox.clear()

    with _depois(hours=23):
        resposta = APIClient().post(VERIFICACOES, {"token": token_de_verificacao})

    assert resposta.status_code == 204
    usuario = Usuario.objects.get(nome_de_usuario="caio")
    assert usuario.situacao == Situacao.ATIVO
    assert usuario.email_verificado_em is not None
    assert usuario.admin is False
    # Mudança de spec do M4 (CA-20): o e-mail simples aos admins virou o evento, tratado por `notificacoes`.
    assert publicados == [CadastroConcluido(usuario_id=usuario.id)]
    assert mail.outbox == []
    client = APIClient()
    assert client.post(SESSAO, {"identificador": "caio", "senha": SENHA}).status_code == 200
    assert client.get(SESSAO).json()["usuario"]["tem_cargo"] is False


def test_cadastro_audita_o_uso_do_convite_e_a_conclusao_sem_senha_nem_token(token: str) -> None:
    _cadastrar(token)
    token_de_verificacao = _token_de_verificacao(mail.outbox[-1])
    APIClient().post(VERIFICACOES, {"token": token_de_verificacao})

    usuario = Usuario.objects.get(nome_de_usuario="caio")
    do_convite = auditoria.historico_do_item("convite", Convite.objects.get().id)
    do_usuario = auditoria.historico_do_item("usuario", usuario.id)
    assert [r.acao for r in do_convite] == ["CONVITE_GERADO", "CONVITE_USADO"]
    assert do_convite[1].ator_id == usuario.id
    assert [r.acao for r in do_usuario] == ["CADASTRO_CONCLUIDO"]
    tudo = str(do_convite) + str(do_usuario)
    assert SENHA not in tudo
    assert token not in tudo
    assert token_de_verificacao not in tudo


def test_link_de_verificacao_so_funciona_uma_vez(token: str) -> None:
    _cadastrar(token)
    token_de_verificacao = _token_de_verificacao(mail.outbox[-1])
    APIClient().post(VERIFICACOES, {"token": token_de_verificacao})

    resposta = APIClient().post(VERIFICACOES, {"token": token_de_verificacao})

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "LINK_INVALIDO"


def test_link_de_verificacao_adulterado_e_recusado(token: str) -> None:
    _cadastrar(token)
    token_de_verificacao = _token_de_verificacao(mail.outbox[-1])

    resposta = APIClient().post(VERIFICACOES, {"token": token_de_verificacao[:-3] + "abc"})

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "LINK_INVALIDO"
    assert Usuario.objects.get(nome_de_usuario="caio").situacao == Situacao.AGUARDANDO_VERIFICACAO


def test_ca12_cadastro_nao_verificado_em_24_horas_nao_verifica_e_e_descartado(
    token: str, client_admin: APIClient
) -> None:
    _cadastrar(token)
    token_de_verificacao = _token_de_verificacao(mail.outbox[-1])
    descartado = Usuario.objects.get(nome_de_usuario="caio").id

    with _depois(hours=24):
        verificacao = APIClient().post(VERIFICACOES, {"token": token_de_verificacao})
        tasks.descartar_cadastros_vencidos.delay()
        tasks.descartar_cadastros_vencidos.delay()
        outro_token = client_admin.post(CONVITES).json()["link"].rsplit("/", 1)[1]
        de_novo = _cadastrar(outro_token)

    assert verificacao.status_code == 400
    assert verificacao.json()["error"]["code"] == "LINK_INVALIDO"
    assert not Usuario.objects.filter(pk=descartado).exists()
    assert de_novo.status_code == 201
    assert not _convite_ativo(token)
    assert [r.acao for r in auditoria.historico_do_item("usuario", descartado)] == ["CADASTRO_DESCARTADO"]


def test_cadastro_vencido_ainda_nao_descartado_nao_prende_o_nome_de_usuario(
    token: str, client_admin: APIClient
) -> None:
    _cadastrar(token)

    with _depois(hours=25):
        outro_token = client_admin.post(CONVITES).json()["link"].rsplit("/", 1)[1]
        resposta = _cadastrar(outro_token)

    assert resposta.status_code == 201
    assert Usuario.objects.filter(nome_de_usuario="caio").count() == 1


def test_descarte_nao_toca_em_cadastro_dentro_do_prazo_nem_em_conta_ativa(token: str, admin: Usuario) -> None:
    _cadastrar(token)

    with _depois(hours=23):
        tasks.descartar_cadastros_vencidos.delay()

    assert Usuario.objects.filter(nome_de_usuario="caio").exists()
    assert Usuario.objects.filter(pk=admin.pk).exists()


@pytest.mark.parametrize(
    ("campos", "status", "codigo"),
    [
        ({"nome_de_usuario": "ANA.Admin"}, 409, "NOME_DE_USUARIO_EM_USO"),
        ({"email": "ANA@exemplo.com"}, 409, "EMAIL_EM_USO"),
        ({"senha": "12345678"}, 400, "VALIDATION_ERROR"),
        ({"nome_de_usuario": "a b"}, 400, "VALIDATION_ERROR"),
        ({"telefone": "123"}, 400, "VALIDATION_ERROR"),
    ],
)
def test_ca13_dado_invalido_ou_em_uso_nao_cria_conta_e_nao_gasta_o_convite(
    token: str, campos: dict[str, str], status: int, codigo: str
) -> None:
    resposta = _cadastrar(token, **campos)

    assert resposta.status_code == status
    assert resposta.json()["error"]["code"] == codigo
    assert (
        not Usuario.objects.filter(nome_de_usuario__iexact=_dados(token, **campos)["nome_de_usuario"])
        .exclude(admin=True)
        .exists()
    )
    assert _convite_ativo(token)


def test_ca13_senha_fraca_aponta_o_campo(token: str) -> None:
    resposta = _cadastrar(token, senha="12345678")

    assert "senha" in resposta.json()["error"]["details"]


def test_cadastro_com_convite_invalido_nao_cria_conta(db: None) -> None:
    resposta = _cadastrar("token-que-nao-existe")

    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "CONVITE_INVALIDO"
    assert Usuario.objects.count() == 0


def test_o_mesmo_convite_nao_serve_para_dois_cadastros(token: str) -> None:
    assert _cadastrar(token).status_code == 201

    segundo = _cadastrar(token, nome_de_usuario="dora", email="dora@exemplo.com")

    assert segundo.status_code == 404
    assert segundo.json()["error"]["code"] == "CONVITE_INVALIDO"
    assert not Usuario.objects.filter(nome_de_usuario="dora").exists()


def test_o_uso_do_convite_bloqueia_a_linha_para_cadastros_simultaneos(token: str) -> None:
    with mock.patch.object(
        Convite.objects, "select_for_update", wraps=Convite.objects.select_for_update
    ) as bloqueio:
        _cadastrar(token)

    assert bloqueio.called


def test_ca14_o_cadastro_nao_aceita_nem_guarda_cpf(token: str) -> None:
    resposta = APIClient().post(CADASTROS, {**_dados(token), "cpf": "12345678909"})

    assert resposta.status_code == 201
    assert "cpf" not in {campo.name for campo in Usuario._meta.get_fields()}
    assert "12345678909" not in str(Usuario.objects.filter(nome_de_usuario="caio").values().get())


def test_o_token_nunca_passa_pela_fila(token: str) -> None:
    with mock.patch.object(tasks.enviar_email_de_verificacao, "delay") as enfileirar:
        _cadastrar(token)

    usuario = Usuario.objects.get(nome_de_usuario="caio")
    enfileirar.assert_called_once_with(str(usuario.id))


def test_reenvio_manda_outro_link_valido_para_quem_aguarda_verificacao(token: str) -> None:
    _cadastrar(token)
    mail.outbox.clear()

    resposta = APIClient().post(REENVIAR, {"identificador": "CAIO@exemplo.com"})

    assert resposta.status_code == 204
    assert [m.to for m in mail.outbox] == [["caio@exemplo.com"]]
    verificacao = APIClient().post(VERIFICACOES, {"token": _token_de_verificacao(mail.outbox[0])})
    assert verificacao.status_code == 204


@pytest.mark.parametrize("identificador", ["ninguem", "ana.admin"])
def test_reenvio_responde_igual_e_nao_envia_nada_para_conta_inexistente_ou_ativa(
    admin: Usuario, identificador: str
) -> None:
    mail.outbox.clear()

    resposta = APIClient().post(REENVIAR, {"identificador": identificador})

    assert resposta.status_code == 204
    assert mail.outbox == []


def test_reenvio_e_limitado_a_tres_por_hora(token: str) -> None:
    _cadastrar(token)
    mail.outbox.clear()

    respostas = [APIClient().post(REENVIAR, {"identificador": "caio"}) for _ in range(4)]

    assert {r.status_code for r in respostas} == {204}
    assert len(mail.outbox) == 3


def test_servico_de_cadastro_normaliza_o_que_recebe(token: str) -> None:
    usuario = cadastro.cadastrar(**_dados(token, nome="  Caio  ", nome_de_usuario=" caio "))

    assert usuario.nome == "Caio"
    assert usuario.nome_de_usuario == "caio"


@pytest.mark.sem_atalho_de_commit
def test_o_email_so_e_enfileirado_depois_do_commit(
    token: str, django_capture_on_commit_callbacks: Any
) -> None:
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=False) as pendentes:
        resposta = _cadastrar(token)
        assert resposta.status_code == 201
        assert mail.outbox == []

    assert len(pendentes) == 1
    pendentes[0]()
    assert [m.to for m in mail.outbox] == [["caio@exemplo.com"]]
