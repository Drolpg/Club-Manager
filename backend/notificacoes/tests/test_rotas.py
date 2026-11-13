"""Rotas da caixa de entrada e das preferências, sob `/api/v1/notificacoes/` (CP5).

As notificações de teste nascem pela API pública, como nascem para os outros módulos.
"""

import uuid
from datetime import datetime
from typing import Any

import pytest
from rest_framework.test import APIClient

from notificacoes import public
from notificacoes.http import urls
from notificacoes.models import Notificacao
from tests.apoio import Usuario, cliente_de, criar_diretor

pytestmark = pytest.mark.django_db

BASE = "/api/v1/notificacoes/"
CAMPOS_DO_ITEM = {"id", "tipo", "pede_acao", "titulo", "texto", "caminho", "criada_em", "lida_em"}


def _criar(usuario: Usuario, chave: str, tipo: str, titulo: str = "Título") -> Notificacao:
    public.notificar(
        tipo=tipo,
        destinatarios=[usuario.id],
        titulo=titulo,
        texto=f"Texto de {chave}",
        item_tipo="usuario",
        item_id=uuid.uuid7(),
        caminho=f"/item/{chave}",
        chave=chave,
    )
    return Notificacao.objects.get(destinatario_id=usuario.id, chave=chave)


def _ids(resposta: Any) -> list[str]:
    return [item["id"] for item in resposta.json()["itens"]]


@pytest.fixture
def informativo(tipos_de_teste: tuple[str, str]) -> str:
    return tipos_de_teste[1]


@pytest.mark.parametrize(
    ("metodo", "rota"),
    [
        ("get", BASE),
        ("get", f"{BASE}resumo/"),
        ("post", f"{BASE}{uuid.uuid4()}/ler/"),
        ("post", f"{BASE}ler-todas/"),
        ("get", f"{BASE}preferencias/"),
        ("put", f"{BASE}preferencias/"),
    ],
)
def test_sem_sessao_toda_rota_responde_401(metodo: str, rota: str) -> None:
    resposta = getattr(APIClient(), metodo)(rota)

    assert resposta.status_code == 401
    assert resposta.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_ca09_a_caixa_traz_so_as_do_usuario_da_mais_recente_para_a_mais_antiga(
    informativo: str, admin: Usuario, diretor: Usuario, client_diretor: APIClient
) -> None:
    primeira = _criar(diretor, "a", informativo)
    segunda = _criar(diretor, "b", informativo)
    terceira = _criar(diretor, "c", informativo)
    _criar(admin, "do-admin", informativo)
    client_diretor.post(f"{BASE}{segunda.id}/ler/")

    resposta = client_diretor.get(BASE)

    assert resposta.status_code == 200
    assert _ids(resposta) == [str(terceira.id), str(segunda.id), str(primeira.id)]
    assert [i["lida_em"] is not None for i in resposta.json()["itens"]] == [False, True, False]
    assert resposta.json()["tem_mais"] is False


def test_ca09_o_item_traz_so_os_campos_do_contrato(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    criada = _criar(diretor, "a", informativo, titulo="Aviso")

    (item,) = client_diretor.get(BASE).json()["itens"]

    assert set(item) == CAMPOS_DO_ITEM
    assert (item["id"], item["tipo"], item["pede_acao"]) == (str(criada.id), informativo, False)
    assert (item["titulo"], item["texto"], item["caminho"]) == ("Aviso", "Texto de a", "/item/a")
    assert item["lida_em"] is None


def test_ca09_o_admin_tambem_so_ve_a_propria_caixa(
    informativo: str, admin: Usuario, diretor: Usuario, client_admin: APIClient
) -> None:
    _criar(diretor, "do-diretor", informativo)
    propria = _criar(admin, "do-admin", informativo)

    resposta = client_admin.get(BASE)

    assert _ids(resposta) == [str(propria.id)]


def test_a_caixa_vazia_responde_lista_vazia(client_diretor: APIClient) -> None:
    resposta = client_diretor.get(BASE)

    assert resposta.json() == {"itens": [], "tem_mais": False}


def test_ca10_o_resumo_conta_so_as_nao_lidas_do_usuario(
    informativo: str, admin: Usuario, diretor: Usuario, client_diretor: APIClient
) -> None:
    _criar(diretor, "a", informativo)
    lida = _criar(diretor, "b", informativo)
    ultima = _criar(diretor, "c", informativo)
    _criar(admin, "do-admin", informativo)
    client_diretor.post(f"{BASE}{lida.id}/ler/")

    resposta = client_diretor.get(f"{BASE}resumo/")

    assert resposta.status_code == 200
    assert resposta.json() == {"nao_lidas": 2, "mais_recente_id": str(ultima.id)}


def test_ca10_o_resumo_sem_notificacoes(client_diretor: APIClient) -> None:
    assert client_diretor.get(f"{BASE}resumo/").json() == {"nao_lidas": 0, "mais_recente_id": None}


def test_ca10_o_mais_recente_e_o_ultimo_que_chegou_mesmo_que_ja_lido(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    _criar(diretor, "a", informativo)
    ultima = _criar(diretor, "b", informativo)
    client_diretor.post(f"{BASE}{ultima.id}/ler/")

    assert client_diretor.get(f"{BASE}resumo/").json()["mais_recente_id"] == str(ultima.id)


def test_ca11_abrir_a_notificacao_a_marca_lida_com_data_e_diminui_o_resumo(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    _criar(diretor, "a", informativo)
    alvo = _criar(diretor, "b", informativo)
    assert client_diretor.get(f"{BASE}resumo/").json()["nao_lidas"] == 2

    resposta = client_diretor.post(f"{BASE}{alvo.id}/ler/")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == CAMPOS_DO_ITEM
    assert corpo["id"] == str(alvo.id)
    assert corpo["lida_em"] is not None
    assert Notificacao.objects.get(pk=alvo.pk).lida_em is not None
    assert client_diretor.get(f"{BASE}resumo/").json()["nao_lidas"] == 1


def test_ca12_abrir_de_novo_nao_muda_a_data_da_primeira_leitura(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    alvo = _criar(diretor, "a", informativo)
    primeira = client_diretor.post(f"{BASE}{alvo.id}/ler/").json()["lida_em"]

    segunda = client_diretor.post(f"{BASE}{alvo.id}/ler/")

    assert segunda.status_code == 200
    assert segunda.json()["lida_em"] == primeira
    assert Notificacao.objects.get(pk=alvo.pk).lida_em == datetime.fromisoformat(primeira)


def test_ca13_marcar_todas_como_lidas_so_mexe_nas_do_usuario(
    informativo: str, admin: Usuario, diretor: Usuario, client_diretor: APIClient
) -> None:
    for chave in ("a", "b", "c"):
        _criar(diretor, chave, informativo)
    do_admin = _criar(admin, "do-admin", informativo)
    ja_lida = Notificacao.objects.filter(destinatario_id=diretor.id).first()
    assert ja_lida is not None
    client_diretor.post(f"{BASE}{ja_lida.id}/ler/")
    data_da_primeira = Notificacao.objects.get(pk=ja_lida.pk).lida_em

    resposta = client_diretor.post(f"{BASE}ler-todas/")

    assert resposta.status_code == 200
    assert resposta.json() == {"marcadas": 2}
    assert not Notificacao.objects.filter(destinatario_id=diretor.id, lida_em__isnull=True).exists()
    assert Notificacao.objects.get(pk=ja_lida.pk).lida_em == data_da_primeira
    assert Notificacao.objects.get(pk=do_admin.pk).lida_em is None
    assert client_diretor.get(f"{BASE}resumo/").json()["nao_lidas"] == 0


def test_ca13_marcar_todas_sem_nenhuma_nao_lida_marca_zero(client_diretor: APIClient) -> None:
    assert client_diretor.post(f"{BASE}ler-todas/").json() == {"marcadas": 0}


@pytest.mark.parametrize("quem", ["diretor", "admin"])
def test_ca14_a_notificacao_de_outro_responde_que_nao_existe_inclusive_para_o_admin(
    informativo: str, admin: Usuario, quem: str
) -> None:
    dono = criar_diretor("dono")
    alheia = _criar(dono, "a", informativo)
    leitor = admin if quem == "admin" else criar_diretor("curioso")

    resposta = cliente_de(leitor).post(f"{BASE}{alheia.id}/ler/")

    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "NOT_FOUND"
    assert Notificacao.objects.get(pk=alheia.pk).lida_em is None


def test_ca14_notificacao_que_nao_existe_responde_igual_a_de_outro(client_diretor: APIClient) -> None:
    resposta = client_diretor.post(f"{BASE}{uuid.uuid4()}/ler/")

    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "NOT_FOUND"


def test_ca14_a_de_outro_nao_aparece_na_caixa_nem_no_resumo_nem_como_cursor(
    informativo: str, admin: Usuario, client_admin: APIClient
) -> None:
    dono = criar_diretor("dono")
    alheia = _criar(dono, "a", informativo)

    assert client_admin.get(BASE).json()["itens"] == []
    assert client_admin.get(f"{BASE}resumo/").json() == {"nao_lidas": 0, "mais_recente_id": None}
    assert client_admin.get(f"{BASE}?antes={alheia.id}").status_code == 400


def test_ca15_a_caixa_carrega_as_seguintes_por_cursor_sem_repetir_nem_pular(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    criadas = [_criar(diretor, f"n{i:02d}", informativo) for i in range(25)]
    esperado = [str(n.id) for n in reversed(criadas)]

    primeira = client_diretor.get(f"{BASE}?limite=10")
    segunda = client_diretor.get(f"{BASE}?limite=10&antes={_ids(primeira)[-1]}")
    terceira = client_diretor.get(f"{BASE}?limite=10&antes={_ids(segunda)[-1]}")

    assert [len(_ids(p)) for p in (primeira, segunda, terceira)] == [10, 10, 5]
    assert [p.json()["tem_mais"] for p in (primeira, segunda, terceira)] == [True, True, False]
    assert _ids(primeira) + _ids(segunda) + _ids(terceira) == esperado


def test_ca15_o_limite_padrao_e_20(informativo: str, diretor: Usuario, client_diretor: APIClient) -> None:
    for i in range(21):
        _criar(diretor, f"n{i:02d}", informativo)

    resposta = client_diretor.get(BASE)

    assert len(_ids(resposta)) == 20
    assert resposta.json()["tem_mais"] is True


def test_ca15_o_limite_maximo_e_50_e_o_minimo_e_1(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    for i in range(3):
        _criar(diretor, f"n{i}", informativo)

    assert len(_ids(client_diretor.get(f"{BASE}?limite=50"))) == 3
    assert len(_ids(client_diretor.get(f"{BASE}?limite=1"))) == 1
    assert client_diretor.get(f"{BASE}?limite=1").json()["tem_mais"] is True


@pytest.mark.parametrize("consulta", ["limite=0", "limite=51", "limite=-1", "limite=abc", "antes=xyz"])
def test_parametro_invalido_da_caixa_responde_400(client_diretor: APIClient, consulta: str) -> None:
    resposta = client_diretor.get(f"{BASE}?{consulta}")

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "VALIDATION_ERROR"


def test_cursor_de_notificacao_que_nao_existe_responde_400(client_diretor: APIClient) -> None:
    resposta = client_diretor.get(f"{BASE}?antes={uuid.uuid4()}")

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "VALIDATION_ERROR"


def test_ca16_as_preferencias_de_um_usuario_novo_estao_ligadas(client_diretor: APIClient) -> None:
    resposta = client_diretor.get(f"{BASE}preferencias/")

    assert resposta.status_code == 200
    assert resposta.json() == {"aviso_na_tela": True, "email_informativos": True}


def test_ca17_alterar_as_preferencias_muda_so_as_do_usuario(
    admin: Usuario, client_admin: APIClient, client_diretor: APIClient
) -> None:
    resposta = client_diretor.put(
        f"{BASE}preferencias/", {"aviso_na_tela": False, "email_informativos": False}
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"aviso_na_tela": False, "email_informativos": False}
    assert client_diretor.get(f"{BASE}preferencias/").json() == {
        "aviso_na_tela": False,
        "email_informativos": False,
    }
    assert client_admin.get(f"{BASE}preferencias/").json() == {
        "aviso_na_tela": True,
        "email_informativos": True,
    }


def test_ca17_o_put_aceita_so_uma_chave_e_deixa_a_outra_como_esta(client_diretor: APIClient) -> None:
    client_diretor.put(f"{BASE}preferencias/", {"aviso_na_tela": False})

    resposta = client_diretor.put(f"{BASE}preferencias/", {"email_informativos": False})

    assert resposta.json() == {"aviso_na_tela": False, "email_informativos": False}


def test_ca17_a_mudanca_vale_para_as_proximas_notificacoes(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    antes = _criar(diretor, "antes", informativo)
    client_diretor.put(f"{BASE}preferencias/", {"email_informativos": False})

    depois = _criar(diretor, "depois", informativo)

    assert Notificacao.objects.get(pk=antes.pk).email_situacao == "PENDENTE"
    assert Notificacao.objects.get(pk=depois.pk).email_situacao == "DISPENSADO"


@pytest.mark.parametrize(
    "corpo", [{"aviso_na_tela": "sim"}, {"email_informativos": 1}, {"aviso_na_tela": None}]
)
def test_preferencia_que_nao_e_booleana_responde_400_e_nao_muda_nada(
    client_diretor: APIClient, corpo: dict[str, Any]
) -> None:
    resposta = client_diretor.put(f"{BASE}preferencias/", corpo)

    assert resposta.status_code == 400
    assert resposta.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client_diretor.get(f"{BASE}preferencias/").json() == {
        "aviso_na_tela": True,
        "email_informativos": True,
    }


def test_ca19_nenhuma_rota_apaga_nem_desliga_o_registro(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    alvo = _criar(diretor, "a", informativo)

    respostas = [
        client_diretor.delete(BASE),
        client_diretor.delete(f"{BASE}{alvo.id}/"),
        client_diretor.delete(f"{BASE}{alvo.id}/ler/"),
        client_diretor.delete(f"{BASE}preferencias/"),
        client_diretor.patch(f"{BASE}{alvo.id}/ler/"),
        client_diretor.post(BASE),
    ]

    assert [r.status_code for r in respostas] == [405, 404, 405, 405, 405, 405]
    assert Notificacao.objects.filter(pk=alvo.pk).exists()


def test_ca19_o_put_de_preferencias_ignora_campo_que_tentaria_desligar_o_registro(
    informativo: str, diretor: Usuario, client_diretor: APIClient
) -> None:
    resposta = client_diretor.put(
        f"{BASE}preferencias/", {"registrar": False, "aviso_na_tela": False, "caixa": False}
    )

    assert resposta.status_code == 200
    assert set(resposta.json()) == {"aviso_na_tela", "email_informativos"}
    assert _criar(diretor, "a", informativo).pk is not None


def test_ca19_as_rotas_do_modulo_sao_so_as_da_especificacao() -> None:
    caminhos = sorted(str(p.pattern) for p in urls.urlpatterns)

    assert caminhos == ["", "<uuid:notificacao_id>/ler/", "ler-todas/", "preferencias/", "resumo/"]
