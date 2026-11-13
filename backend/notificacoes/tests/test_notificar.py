"""`notificar`: registro, filtro de ativos, idempotência pela chave e e-mail só depois do commit (CP2)."""

import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.db import transaction
from django.utils import timezone

from notificacoes import public, tasks
from notificacoes.models import Notificacao, PreferenciaDeAlerta, SituacaoDoEmail
from notificacoes.services import preferencias
from tests.apoio import Situacao, Usuario, criar_diretor

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def tarefa_de_email() -> Iterator[mock.MagicMock]:
    """Captura o que é enfileirado; a tarefa de verdade é testada no checkpoint 3."""
    with mock.patch.object(tasks.enviar_email, "delay") as delay:
        yield delay


@pytest.fixture(autouse=True)
def _executar_na_hora_o_que_roda_depois_do_commit(request: pytest.FixtureRequest) -> Iterator[None]:
    """Cada teste roda numa transação que nunca é confirmada; aqui o `on_commit` roda na hora.

    O teste marcado com `sem_atalho_de_commit` confere, sem o atalho, que o envio só é agendado no commit.
    """
    if request.node.get_closest_marker("sem_atalho_de_commit"):
        yield
        return
    with mock.patch("django.db.transaction.on_commit", side_effect=lambda funcao, **_: funcao()):
        yield


def _notificar(tipo: str, destinatarios: list[uuid.UUID], chave: str = "fato:1", **extra: Any) -> int:
    dados: dict[str, Any] = {
        "tipo": tipo,
        "destinatarios": destinatarios,
        "titulo": "Título do aviso",
        "texto": "Texto curto do aviso.",
        "item_tipo": "usuario",
        "item_id": uuid.uuid7(),
        "caminho": "/admin/usuarios/1",
        "chave": chave,
    }
    dados.update(extra)
    return public.notificar(**dados)


def test_ca01_dois_destinatarios_ativos_recebem_uma_notificacao_cada(
    tipos_de_teste: tuple[str, str], admin: Usuario, diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    item = uuid.uuid7()

    criadas = _notificar(pede_acao, [admin.id, diretor.id], item_id=item)

    assert criadas == 2
    por_destinatario = {n.destinatario_id: n for n in Notificacao.objects.all()}
    assert set(por_destinatario) == {admin.id, diretor.id}
    for notificacao in por_destinatario.values():
        assert (notificacao.tipo, notificacao.pede_acao) == (pede_acao, True)
        assert (notificacao.titulo, notificacao.texto) == ("Título do aviso", "Texto curto do aviso.")
        assert (notificacao.item_tipo, notificacao.item_id) == ("usuario", item)
        assert notificacao.caminho == "/admin/usuarios/1"
        assert notificacao.chave == "fato:1"
        assert notificacao.criada_em <= timezone.now()
        assert notificacao.lida_em is None
        assert notificacao.email_tentativas == 0


def test_ca02_destinatario_inativo_nao_recebe_notificacao_nova(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    inativo = criar_diretor("ines", Situacao.INATIVO)
    pendente = criar_diretor("pedro", Situacao.AGUARDANDO_VERIFICACAO)

    criadas = _notificar(pede_acao, [diretor.id, inativo.id, pendente.id])

    assert criadas == 1
    assert list(Notificacao.objects.values_list("destinatario_id", flat=True)) == [diretor.id]


def test_destinatario_que_nao_existe_e_ignorado(tipos_de_teste: tuple[str, str]) -> None:
    pede_acao, _ = tipos_de_teste

    assert _notificar(pede_acao, [uuid.uuid4()]) == 0
    assert Notificacao.objects.count() == 0


def test_destinatario_repetido_na_lista_recebe_uma_so(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste

    assert _notificar(pede_acao, [diretor.id, diretor.id]) == 1


def test_notificacoes_antigas_de_quem_foi_desativado_continuam_guardadas(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste
    _notificar(pede_acao, [diretor.id])
    Usuario.objects.filter(pk=diretor.id).update(situacao=Situacao.INATIVO)

    criadas = _notificar(pede_acao, [diretor.id], chave="fato:2")

    assert criadas == 0
    assert Notificacao.objects.filter(destinatario_id=diretor.id).count() == 1


def test_tipo_desconhecido_e_erro_de_programacao(diretor: Usuario) -> None:
    with pytest.raises(ValueError, match="desconhecido"):
        _notificar("nao.existe", [diretor.id])

    assert Notificacao.objects.count() == 0


def test_o_registro_marca_se_o_tipo_pede_acao_no_momento_da_criacao(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, informativo = tipos_de_teste

    _notificar(pede_acao, [diretor.id], chave="a")
    _notificar(informativo, [diretor.id], chave="b")

    assert dict(Notificacao.objects.values_list("chave", "pede_acao")) == {"a": True, "b": False}


def test_ca03_o_que_pede_acao_agenda_o_email_mesmo_com_os_informativos_desligados(
    tipos_de_teste: tuple[str, str], diretor: Usuario, tarefa_de_email: mock.MagicMock
) -> None:
    pede_acao, _ = tipos_de_teste
    preferencias.alterar(diretor.id, email_informativos=False)

    _notificar(pede_acao, [diretor.id])

    notificacao = Notificacao.objects.get()
    assert notificacao.email_situacao == SituacaoDoEmail.PENDENTE
    tarefa_de_email.assert_called_once_with(str(notificacao.id))


def test_o_informativo_agenda_o_email_quando_o_destinatario_nao_desligou(
    tipos_de_teste: tuple[str, str], diretor: Usuario, tarefa_de_email: mock.MagicMock
) -> None:
    _, informativo = tipos_de_teste

    _notificar(informativo, [diretor.id])

    notificacao = Notificacao.objects.get()
    assert notificacao.email_situacao == SituacaoDoEmail.PENDENTE
    tarefa_de_email.assert_called_once_with(str(notificacao.id))


def test_ca04_informativo_com_email_desligado_fica_na_caixa_e_nao_agenda_email(
    tipos_de_teste: tuple[str, str], diretor: Usuario, tarefa_de_email: mock.MagicMock
) -> None:
    _, informativo = tipos_de_teste
    preferencias.alterar(diretor.id, email_informativos=False)

    criadas = _notificar(informativo, [diretor.id])

    assert criadas == 1
    notificacao = Notificacao.objects.get()
    assert notificacao.email_situacao == SituacaoDoEmail.DISPENSADO
    tarefa_de_email.assert_not_called()


def test_a_preferencia_vale_por_destinatario(
    tipos_de_teste: tuple[str, str], admin: Usuario, diretor: Usuario
) -> None:
    _, informativo = tipos_de_teste
    preferencias.alterar(diretor.id, email_informativos=False)

    _notificar(informativo, [admin.id, diretor.id])

    situacoes = {n.destinatario_id: n.email_situacao for n in Notificacao.objects.all()}
    assert situacoes == {admin.id: SituacaoDoEmail.PENDENTE, diretor.id: SituacaoDoEmail.DISPENSADO}


def test_ca07_o_mesmo_fato_duas_vezes_gera_uma_notificacao_e_um_email(
    tipos_de_teste: tuple[str, str], admin: Usuario, diretor: Usuario, tarefa_de_email: mock.MagicMock
) -> None:
    pede_acao, _ = tipos_de_teste

    primeira = _notificar(pede_acao, [admin.id, diretor.id], chave="cadastro:1")
    segunda = _notificar(pede_acao, [admin.id, diretor.id], chave="cadastro:1")

    assert (primeira, segunda) == (2, 0)
    assert Notificacao.objects.count() == 2
    assert tarefa_de_email.call_count == 2


def test_chaves_diferentes_geram_notificacoes_diferentes_para_a_mesma_pessoa(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste

    _notificar(pede_acao, [diretor.id], chave="a")
    _notificar(pede_acao, [diretor.id], chave="b")

    assert Notificacao.objects.filter(destinatario_id=diretor.id).count() == 2


def test_a_mesma_chave_para_pessoas_diferentes_nao_se_confunde(
    tipos_de_teste: tuple[str, str], admin: Usuario, diretor: Usuario
) -> None:
    pede_acao, _ = tipos_de_teste

    _notificar(pede_acao, [admin.id], chave="mesma")
    criadas = _notificar(pede_acao, [diretor.id], chave="mesma")

    assert criadas == 1


@pytest.mark.sem_atalho_de_commit
def test_ca05_o_email_so_e_agendado_depois_do_commit(
    tipos_de_teste: tuple[str, str],
    diretor: Usuario,
    tarefa_de_email: mock.MagicMock,
    django_capture_on_commit_callbacks: Any,
) -> None:
    pede_acao, _ = tipos_de_teste

    with django_capture_on_commit_callbacks(execute=False) as pendentes:
        _notificar(pede_acao, [diretor.id])
        assert Notificacao.objects.count() == 1
        tarefa_de_email.assert_not_called()

    assert len(pendentes) == 1
    pendentes[0]()
    tarefa_de_email.assert_called_once_with(str(Notificacao.objects.get().id))


@pytest.mark.sem_atalho_de_commit
def test_ca05_transacao_desfeita_nao_deixa_notificacao_nem_email(
    tipos_de_teste: tuple[str, str],
    diretor: Usuario,
    tarefa_de_email: mock.MagicMock,
    django_capture_on_commit_callbacks: Any,
) -> None:
    pede_acao, _ = tipos_de_teste

    def fato_que_falha_depois_de_notificar() -> None:
        with transaction.atomic():
            _notificar(pede_acao, [diretor.id])
            raise RuntimeError("o fato falhou")

    with django_capture_on_commit_callbacks(execute=True) as pendentes, pytest.raises(RuntimeError):
        fato_que_falha_depois_de_notificar()

    assert pendentes == []
    assert Notificacao.objects.count() == 0
    tarefa_de_email.assert_not_called()


def test_ca19_nenhuma_preferencia_impede_o_registro(
    tipos_de_teste: tuple[str, str], diretor: Usuario
) -> None:
    _, informativo = tipos_de_teste
    preferencias.alterar(diretor.id, aviso_na_tela=False, email_informativos=False)

    criadas = _notificar(informativo, [diretor.id])

    assert criadas == 1
    campos = {campo.name for campo in PreferenciaDeAlerta._meta.get_fields()}
    assert campos == {"usuario_id", "aviso_na_tela", "email_informativos"}


def test_a_data_de_criacao_e_a_do_registro(tipos_de_teste: tuple[str, str], diretor: Usuario) -> None:
    pede_acao, _ = tipos_de_teste
    antes = timezone.now() - timedelta(seconds=1)

    _notificar(pede_acao, [diretor.id])

    assert Notificacao.objects.get().criada_em >= antes
