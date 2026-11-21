"""O serviço do perfil (CA-01 a CA-05, CA-07): só leitura, regra "dono ou admin" antes de qualquer consulta.

Banco real. Cada seção é lida do módulo dono pela API pública; o perfil não guarda nada.
"""

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.utils import timezone

from auditoria import public as auditoria
from kernel.errors import BusinessError
from notificacoes import public as notificacoes
from relatorios.services import perfil
from tests import apoio
from tests.apoio import Situacao, Usuario

pytestmark = pytest.mark.django_db


def _diretor(nome: str, *codigos: str, cargo: bool = True) -> Usuario:
    usuario = apoio.criar_diretor(f"{nome}.dir")
    if cargo:
        apoio.dar_cargo(usuario)
    for codigo in codigos:
        apoio.conceder(usuario, codigo)
    return usuario


def _registros(alvo: Usuario, acao: str = "PERFIL_CONSULTADO") -> list[auditoria.Registro]:
    return [r for r in auditoria.historico_do_item("usuario", alvo.id) if r.acao == acao]


def _codigo(excecao: pytest.ExceptionInfo[BusinessError]) -> str:
    return excecao.value.code


@pytest.fixture
def cenario(db: None) -> dict[str, Usuario]:
    return {
        "ana": _diretor("ana"),
        "bia": _diretor("bia"),
        "total": _diretor("total", "acesso.total"),
        "sem_cargo": _diretor("semcargo", cargo=False),
        "admin": apoio.criar_admin(),
    }


# --- o próprio perfil (CA-01 a CA-03) ---------------------------------------------------------------------


def test_o_dono_ve_dados_cobrancas_eventos_e_notificacoes(cenario: dict[str, Usuario]) -> None:
    ana = cenario["ana"]

    completo = perfil.perfil(ana.id, ana.id)

    assert completo.dados.nome == ana.nome
    assert completo.dados.email == ana.email
    assert completo.dados.telefone == "11988887777"
    assert completo.dados.ativo is True
    assert completo.dados.admin is False
    assert completo.dados.cargo == "Diretor"
    assert completo.cobrancas.itens == []
    assert completo.eventos.itens == []
    assert completo.notificacoes is not None
    assert completo.notificacoes.nao_lidas == 0


def test_as_cobrancas_do_dono_aparecem_com_os_dados_do_devedor(cenario: dict[str, Usuario]) -> None:
    ana = cenario["ana"]
    emissor = _diretor("emissor", "cobrancas.criar")
    c_admin = apoio.cliente_de(cenario["admin"])
    categoria = c_admin.post(
        "/api/v1/financeiro/categorias/", {"nome": "Taxa do perfil", "natureza": "ENTRADA"}, format="json"
    ).json()["id"]
    pix = c_admin.post(
        "/api/v1/financeiro/chaves-pix/",
        {
            "tipo": "EMAIL",
            "chave": "clube@clube.local",
            "nome_recebedor": "Clube",
            "cidade": "Curitiba",
            "padrao": True,
        },
        format="json",
    ).json()["id"]
    resposta = apoio.cliente_de(emissor).post(
        "/api/v1/financeiro/cobrancas/",
        {
            "devedor_id": str(ana.id),
            "categoria_id": categoria,
            "descricao": "Mensalidade",
            "valor": "150.00",
            "vencimento": (timezone.localdate() + timedelta(days=5)).isoformat(),
            "chave_pix_id": pix,
        },
        format="json",
    )
    assert resposta.status_code == 201, resposta.content

    completo = perfil.perfil(ana.id, ana.id)

    assert [c.descricao for c in completo.cobrancas.itens] == ["Mensalidade"]
    assert completo.cobrancas.itens[0].valor == "150.00"
    assert completo.cobrancas.itens[0].pagamentos == []


def test_as_paginas_das_secoes_aceitam_cursor_e_limite(cenario: dict[str, Usuario]) -> None:
    ana = cenario["ana"]

    cobrancas = perfil.cobrancas(ana.id, ana.id, limite=5)
    eventos = perfil.eventos(ana.id, ana.id, limite=5)

    assert (cobrancas.itens, cobrancas.tem_mais) == ([], False)
    assert (eventos.itens, eventos.tem_mais) == ([], False)


@pytest.mark.parametrize("limite", [0, -1, 51, 1000])
def test_limite_fora_da_faixa_e_validation_error(cenario: dict[str, Usuario], limite: int) -> None:
    ana = cenario["ana"]

    for secao in (perfil.cobrancas, perfil.eventos):
        with pytest.raises(BusinessError) as erro:
            secao(ana.id, ana.id, limite=limite)
        assert _codigo(erro) == "VALIDATION_ERROR"
        assert "limite" in erro.value.details


def test_cursor_inexistente_e_not_found(cenario: dict[str, Usuario]) -> None:
    ana = cenario["ana"]

    for secao in (perfil.cobrancas, perfil.eventos):
        with pytest.raises(BusinessError) as erro:
            secao(ana.id, ana.id, antes=uuid.uuid4())
        assert _codigo(erro) == "NOT_FOUND"


# --- usuário sem cargo e desativado (CA-07) --------------------------------------------------------------


def test_usuario_sem_cargo_ve_dados_e_secoes_vazias(cenario: dict[str, Usuario]) -> None:
    sem = cenario["sem_cargo"]

    completo = perfil.perfil(sem.id, sem.id)

    assert completo.dados.cargo is None
    assert completo.dados.setores == []
    assert completo.cobrancas.itens == []
    assert completo.eventos.itens == []
    assert completo.notificacoes is not None


# --- o admin vendo outro (CA-05) --------------------------------------------------------------------------


def test_o_admin_ve_dados_cobrancas_e_eventos_de_outro_sem_notificacoes(
    cenario: dict[str, Usuario],
) -> None:
    ana, admin = cenario["ana"], cenario["admin"]

    with mock.patch("relatorios.services.perfil.notificacoes.resumo_da_caixa") as resumo:
        completo = perfil.perfil(admin.id, ana.id)

    assert completo.dados.nome == ana.nome
    assert completo.notificacoes is None
    resumo.assert_not_called()


def test_o_admin_ve_o_perfil_de_um_desativado(cenario: dict[str, Usuario]) -> None:
    saiu = apoio.criar_diretor("saiu", situacao=Situacao.INATIVO)

    completo = perfil.perfil(cenario["admin"].id, saiu.id)

    assert completo.dados.ativo is False
    assert completo.notificacoes is None


def test_o_admin_com_alvo_inexistente_recebe_not_found(cenario: dict[str, Usuario]) -> None:
    with pytest.raises(BusinessError) as erro:
        perfil.dados(cenario["admin"].id, uuid.uuid4())

    assert _codigo(erro) == "NOT_FOUND"


def test_a_consulta_do_admin_em_outro_audita_cada_secao_sem_dado_pessoal(
    cenario: dict[str, Usuario],
) -> None:
    ana, admin = cenario["ana"], cenario["admin"]

    perfil.perfil(admin.id, ana.id)

    registros = _registros(ana)
    assert sorted(r.dados["secao"] for r in registros) == ["cobrancas", "dados", "eventos"]
    assert {r.ator_id for r in registros} == {admin.id}
    texto = " ".join(str(r) for r in registros)
    for dado in (ana.email, "11988887777", ana.nome):
        assert dado not in texto
    assert all(set(r.dados) == {"secao"} for r in registros)


def test_cada_pagina_lida_pelo_admin_conta_um_registro(cenario: dict[str, Usuario]) -> None:
    ana, admin = cenario["ana"], cenario["admin"]

    perfil.cobrancas(admin.id, ana.id)
    perfil.cobrancas(admin.id, ana.id)
    perfil.eventos(admin.id, ana.id)
    perfil.dados(admin.id, ana.id)

    assert sorted(r.dados["secao"] for r in _registros(ana)) == ["cobrancas", "cobrancas", "dados", "eventos"]


def test_o_perfil_proprio_nao_gera_auditoria_nem_o_do_admin_em_si_mesmo(
    cenario: dict[str, Usuario],
) -> None:
    ana, admin = cenario["ana"], cenario["admin"]

    perfil.perfil(ana.id, ana.id)
    perfil.perfil(admin.id, admin.id)

    assert _registros(ana) == []
    assert _registros(admin) == []


def test_o_admin_nao_ve_as_notificacoes_do_outro_pela_secao(cenario: dict[str, Usuario]) -> None:
    ana, admin = cenario["ana"], cenario["admin"]

    with mock.patch("relatorios.services.perfil.notificacoes.resumo_da_caixa") as resumo:
        assert perfil.resumo_de_notificacoes(admin.id, ana.id) is None
    resumo.assert_not_called()

    assert perfil.resumo_de_notificacoes(ana.id, ana.id) is not None


# --- quem não pode (CA-04) --------------------------------------------------------------------------------


@pytest.mark.parametrize("quem", ["bia", "total", "sem_cargo"])
def test_quem_nao_e_dono_nem_admin_recebe_403_em_toda_secao(cenario: dict[str, Usuario], quem: str) -> None:
    ator, ana = cenario[quem], cenario["ana"]
    chamadas: list[Callable[[], Any]] = [
        lambda: perfil.dados(ator.id, ana.id),
        lambda: perfil.cobrancas(ator.id, ana.id),
        lambda: perfil.eventos(ator.id, ana.id),
        lambda: perfil.resumo_de_notificacoes(ator.id, ana.id),
        lambda: perfil.perfil(ator.id, ana.id),
    ]

    for chamada in chamadas:
        with pytest.raises(BusinessError) as erro:
            chamada()
        assert _codigo(erro) == "PERMISSION_DENIED"
    assert _registros(ana) == []


def test_o_403_vem_antes_de_qualquer_consulta_e_tambem_para_id_inexistente(
    cenario: dict[str, Usuario],
) -> None:
    bia = cenario["bia"]

    with (
        mock.patch("relatorios.services.perfil.financeiro.cobrancas_do_devedor") as cobrancas,
        mock.patch("relatorios.services.perfil.eventos_publicos.eventos_do_usuario") as eventos,
        mock.patch("relatorios.services.perfil.acesso.dados_do_perfil") as dados,
    ):
        with pytest.raises(BusinessError) as inexistente:
            perfil.perfil(bia.id, uuid.uuid4())
        with pytest.raises(BusinessError) as limite_ruim:
            perfil.cobrancas(bia.id, uuid.uuid4(), limite=0)

    assert _codigo(inexistente) == "PERMISSION_DENIED"
    assert _codigo(limite_ruim) == "PERMISSION_DENIED"
    cobrancas.assert_not_called()
    eventos.assert_not_called()
    dados.assert_not_called()


def test_usuario_desativado_como_ator_e_negado(cenario: dict[str, Usuario]) -> None:
    saiu = apoio.criar_diretor("saiu", situacao=Situacao.INATIVO)

    with pytest.raises(BusinessError) as erro:
        perfil.dados(saiu.id, saiu.id)

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_admin_desativado_perde_o_acesso_aos_perfis(cenario: dict[str, Usuario]) -> None:
    admin, ana = cenario["admin"], cenario["ana"]
    Usuario.objects.filter(pk=admin.pk).update(situacao=Situacao.INATIVO)

    with pytest.raises(BusinessError) as erro:
        perfil.dados(admin.id, ana.id)

    assert _codigo(erro) == "PERMISSION_DENIED"


def test_ler_o_perfil_nao_mexe_nas_notificacoes_do_alvo(cenario: dict[str, Usuario]) -> None:
    ana, admin = cenario["ana"], cenario["admin"]
    antes = notificacoes.resumo_da_caixa(ana.id).nao_lidas

    perfil.perfil(admin.id, ana.id)

    assert notificacoes.resumo_da_caixa(ana.id).nao_lidas == antes
