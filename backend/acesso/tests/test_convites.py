from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from acesso.models import Convite, Usuario
from acesso.services import convites
from auditoria import public as auditoria
from kernel.errors import BusinessError

pytestmark = pytest.mark.django_db

URL = "/api/v1/acesso/convites/"
CONSULTAR = f"{URL}consultar/"


def _token(resposta: Any) -> str:
    link: str = resposta.json()["link"]
    assert link.startswith("https://clube.exemplo/convite/")
    return link.rsplit("/", 1)[1]


def _gerar(client: APIClient) -> Any:
    resposta = client.post(URL)
    assert resposta.status_code == 201, resposta.content
    return resposta


def _depois(**tempo: int) -> Any:
    return mock.patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(**tempo))


def test_ca03_admin_gera_um_convite_e_recebe_o_link(client_admin: APIClient, admin: Usuario) -> None:
    resposta = _gerar(client_admin)

    corpo = resposta.json()
    assert corpo["situacao"] == "ATIVO"
    assert corpo["gerado_por"] == {"id": str(admin.id), "nome": "Ana Admin"}
    assert len(_token(resposta)) >= 40
    assert APIClient().post(CONSULTAR, {"token": _token(resposta)}).status_code == 204


def test_convite_vale_24_horas_a_partir_da_geracao(client_admin: APIClient) -> None:
    _gerar(client_admin)

    convite = Convite.objects.get()
    assert convite.expira_em - convite.gerado_em == timedelta(hours=24)


def test_token_do_convite_nao_e_guardado_nem_auditado_em_claro(client_admin: APIClient) -> None:
    token = _token(_gerar(client_admin))

    convite = Convite.objects.get()
    assert token not in str(Convite.objects.values().get())
    historico = auditoria.historico_do_item("convite", convite.id)
    assert [r.acao for r in historico] == ["CONVITE_GERADO"]
    assert token not in str(historico)


def test_o_link_so_aparece_na_geracao_e_nunca_na_lista(client_admin: APIClient) -> None:
    token = _token(_gerar(client_admin))

    lista = client_admin.get(URL)

    assert "link" not in lista.json()[0]
    assert token not in lista.content.decode()


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [("post", URL), ("get", URL), ("post", URL + "{id}/regenerar/"), ("post", URL + "{id}/revogar/")],
)
def test_ca04_quem_nao_e_admin_nao_mexe_em_convites(
    client_admin: APIClient, client_diretor: APIClient, metodo: str, caminho: str
) -> None:
    convite_id = _gerar(client_admin).json()["id"]
    url = caminho.format(id=convite_id)

    como_diretor = getattr(client_diretor, metodo)(url)
    sem_sessao = getattr(APIClient(), metodo)(url)

    assert como_diretor.status_code == 403
    assert como_diretor.json()["error"]["code"] == "PERMISSION_DENIED"
    assert sem_sessao.status_code == 401
    assert Convite.objects.count() == 1
    assert Convite.objects.get().revogado_em is None


def test_servico_recusa_quem_nao_e_admin_mesmo_sem_passar_pela_rota(diretor: Usuario) -> None:
    with pytest.raises(BusinessError) as erro:
        convites.gerar(ator=diretor)

    assert erro.value.code == "PERMISSION_DENIED"
    assert Convite.objects.count() == 0


def test_ca05_convite_com_mais_de_24_horas_e_invalido(client_admin: APIClient) -> None:
    token = _token(_gerar(client_admin))

    with _depois(hours=24):
        resposta = APIClient().post(CONSULTAR, {"token": token})
        lista = client_admin.get(URL)

    assert resposta.status_code == 404
    assert resposta.json()["error"] == {
        "code": "CONVITE_INVALIDO",
        "message": "Convite inválido ou expirado.",
        "details": None,
    }
    assert lista.json()[0]["situacao"] == "EXPIRADO"


def test_ca06_convite_revogado_usado_ou_inexistente_tem_a_mesma_resposta(
    client_admin: APIClient, admin: Usuario
) -> None:
    revogado = _gerar(client_admin)
    client_admin.post(f"{URL}{revogado.json()['id']}/revogar/")
    usado = _gerar(client_admin)
    convite_usado = Convite.objects.get(pk=usado.json()["id"])
    convite_usado.marcar_usado(usuario=admin, agora=timezone.now())
    convite_usado.save()
    expirado = _gerar(client_admin)

    with _depois(hours=25):
        respostas = [
            APIClient().post(CONSULTAR, {"token": token})
            for token in (_token(revogado), _token(usado), _token(expirado), "token-que-nunca-existiu")
        ]

    assert {r.status_code for r in respostas} == {404}
    assert len({r.content for r in respostas}) == 1


def test_ca07_regenerar_invalida_o_link_antigo_e_cria_um_novo_de_24_horas(client_admin: APIClient) -> None:
    antigo = _gerar(client_admin)

    with _depois(hours=3):
        novo = client_admin.post(f"{URL}{antigo.json()['id']}/regenerar/")
        consulta_antigo = APIClient().post(CONSULTAR, {"token": _token(antigo)})
        consulta_novo = APIClient().post(CONSULTAR, {"token": _token(novo)})

    assert novo.status_code == 201
    assert novo.json()["id"] != antigo.json()["id"]
    assert consulta_antigo.status_code == 404
    assert consulta_novo.status_code == 204
    convite_novo = Convite.objects.get(pk=novo.json()["id"])
    assert convite_novo.expira_em - convite_novo.gerado_em == timedelta(hours=24)
    assert str(convite_novo.substitui_id) == antigo.json()["id"]


def test_ca07_convite_expirado_pode_ser_regenerado(client_admin: APIClient) -> None:
    antigo = _gerar(client_admin)

    with _depois(hours=30):
        novo = client_admin.post(f"{URL}{antigo.json()['id']}/regenerar/")
        lista = {c["id"]: c["situacao"] for c in client_admin.get(URL).json()}

    assert novo.status_code == 201
    assert lista[novo.json()["id"]] == "ATIVO"
    assert lista[antigo.json()["id"]] == "REVOGADO"


def test_convite_usado_ou_revogado_nao_pode_ser_regenerado(client_admin: APIClient) -> None:
    convite_id = _gerar(client_admin).json()["id"]
    client_admin.post(f"{URL}{convite_id}/revogar/")

    resposta = client_admin.post(f"{URL}{convite_id}/regenerar/")

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == "CONVITE_NAO_PODE_SER_REGENERADO"
    assert Convite.objects.count() == 1


def test_revogar_um_convite_ativo_e_auditar(client_admin: APIClient, admin: Usuario) -> None:
    gerado = _gerar(client_admin)

    resposta = client_admin.post(f"{URL}{gerado.json()['id']}/revogar/")

    assert resposta.status_code == 200
    assert resposta.json()["situacao"] == "REVOGADO"
    assert APIClient().post(CONSULTAR, {"token": _token(gerado)}).status_code == 404
    historico = auditoria.historico_do_item("convite", Convite.objects.get().id)
    assert [r.acao for r in historico] == ["CONVITE_GERADO", "CONVITE_REVOGADO"]
    assert historico[1].ator_id == admin.id


def test_so_convite_ativo_pode_ser_revogado(client_admin: APIClient) -> None:
    convite_id = _gerar(client_admin).json()["id"]
    client_admin.post(f"{URL}{convite_id}/revogar/")

    resposta = client_admin.post(f"{URL}{convite_id}/revogar/")

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == "CONVITE_NAO_ESTA_ATIVO"


def test_convite_que_nao_existe_devolve_404(client_admin: APIClient) -> None:
    resposta = client_admin.post(f"{URL}019a0000-0000-7000-8000-000000000000/revogar/")

    assert resposta.status_code == 404
    assert resposta.json()["error"]["code"] == "NOT_FOUND"


def test_ca08_lista_mostra_situacao_quem_gerou_e_quando(client_admin: APIClient, admin: Usuario) -> None:
    primeiro = _gerar(client_admin).json()
    segundo = _gerar(client_admin).json()
    client_admin.post(f"{URL}{primeiro['id']}/revogar/")

    lista = client_admin.get(URL).json()

    assert [c["id"] for c in lista] == [segundo["id"], primeiro["id"]]
    assert [c["situacao"] for c in lista] == ["ATIVO", "REVOGADO"]
    assert all(c["gerado_por"] == {"id": str(admin.id), "nome": "Ana Admin"} for c in lista)
    assert all(c["gerado_em"] and c["expira_em"] for c in lista)


def test_consulta_de_convite_e_limitada_por_ip(db: None) -> None:
    client = APIClient()
    for _ in range(20):
        assert client.post(CONSULTAR, {"token": "qualquer"}).status_code == 404

    resposta = client.post(CONSULTAR, {"token": "qualquer"})

    assert resposta.status_code == 429
    assert resposta.json()["error"]["code"] == "MUITAS_TENTATIVAS"
