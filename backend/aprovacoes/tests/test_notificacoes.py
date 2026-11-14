"""Notificações do motor: uma linha da tabela da spec funcional por teste, mais o adendo 1 (A5, A6, A7, A11).

As notificações são lidas pela caixa de cada destinatário (`GET /api/v1/notificacoes/`): os testes de
`aprovacoes` não importam os internos de `notificacoes`.
"""

from typing import Any

import pytest

from aprovacoes.models import MotivoDeDecisao
from aprovacoes.services import avisos
from aprovacoes.tests.conftest import (
    APROVAR_TESTE,
    AUTO_APROVAR,
    SOLICITACOES,
    TipoDeTeste,
    com_cargo,
    decisor_do_cenario,
    enviada,
    levar_a,
    pedido,
)
from auditoria import public as auditoria
from tests import apoio
from tests.apoio import Usuario

pytestmark = pytest.mark.django_db

CAIXA = "/api/v1/notificacoes/"


def _caixa(usuario: Usuario) -> list[dict[str, Any]]:
    resposta = apoio.cliente_de(usuario).get(CAIXA, {"limite": 50})
    assert resposta.status_code == 200, resposta.content
    return list(resposta.json()["itens"])


def _do_tipo(usuario: Usuario, tipo: str) -> list[dict[str, Any]]:
    return [n for n in _caixa(usuario) if n["tipo"] == tipo]


def _tipos(usuario: Usuario) -> set[str]:
    return {n["tipo"] for n in _caixa(usuario)}


def _motivo(texto: str) -> str:
    return str(MotivoDeDecisao.objects.get(texto=texto).id)


def _outro_admin(nome_de_usuario: str = "bruno.admin") -> Usuario:
    usuario = apoio.criar_diretor(nome_de_usuario)
    Usuario.objects.filter(pk=usuario.pk).update(admin=True)
    usuario.refresh_from_db()
    return usuario


def _post(usuario: Usuario, solicitacao: Any, acao: str, **corpo: Any) -> Any:
    resposta = apoio.cliente_de(usuario).post(f"{SOLICITACOES}{solicitacao.id}/{acao}/", corpo, format="json")
    assert resposta.status_code == 200, resposta.content
    return resposta


@pytest.fixture
def solicitante(tipo_de_teste: TipoDeTeste, diretor_com_cargo: Usuario) -> Usuario:
    return diretor_com_cargo


# --- linha 1: enviada, reenviada, reaberta ou editada → quem pode decidir (pede ação) ---


def test_ca01_o_envio_notifica_quem_pode_decidir_e_pede_acao(
    solicitante: Usuario, aprovador: Usuario, admin: Usuario
) -> None:
    sem_cargo = apoio.criar_diretor("sem.cargo")
    apoio.conceder(sem_cargo, APROVAR_TESTE)
    leitor = com_cargo("leitor")

    solicitacao = enviada(solicitante)

    for quem in (aprovador, admin):
        (notificacao,) = _do_tipo(quem, "aprovacoes.para_decidir")
        assert notificacao["pede_acao"] is True
        assert notificacao["caminho"] == f"/solicitacoes/{solicitacao.id}"
        assert "Bolas de treino" in notificacao["texto"]
    # Nem o solicitante sem auto-aprovação, nem quem não decide: sem a permissão, ou sem cargo (adendo 1, A2).
    for quem in (solicitante, leitor, sem_cargo):
        assert _do_tipo(quem, "aprovacoes.para_decidir") == []


@pytest.mark.parametrize("caminho", ["reenviada", "reaberta", "editada"])
def test_a_versao_nova_notifica_quem_pode_decidir_de_novo(
    solicitante: Usuario, aprovador: Usuario, caminho: str
) -> None:
    solicitacao = enviada(solicitante)
    if caminho == "reenviada":
        levar_a(solicitacao, "CONTESTADA")
        _post(solicitante, solicitacao, "reenviar", conteudo=pedido("Bolas oficiais"))
    elif caminho == "reaberta":
        levar_a(solicitacao, "RECUSADA")
        _post(
            solicitante,
            solicitacao,
            "reabrir",
            justificativa="Agora tem caixa",
            conteudo=pedido("Bolas oficiais"),
        )
    else:
        levar_a(solicitacao, "APROVADA")
        _post(solicitante, solicitacao, "editar", conteudo=pedido("Bolas oficiais"))

    para_decidir = _do_tipo(aprovador, "aprovacoes.para_decidir")
    assert len(para_decidir) == 2
    assert "Bolas oficiais" in para_decidir[0]["texto"]
    assert para_decidir[0]["pede_acao"] is True


def test_o_solicitante_com_auto_aprovacao_tambem_e_avisado_porque_pode_decidir(
    tipo_de_teste: TipoDeTeste,
) -> None:
    auto = com_cargo("auto", APROVAR_TESTE, AUTO_APROVAR)

    enviada(auto)

    assert len(_do_tipo(auto, "aprovacoes.para_decidir")) == 1


# --- linha 2: aprovada ou recusada → o solicitante (informativa) ---


@pytest.mark.parametrize(("situacao", "palavra"), [("APROVADA", "aprovada"), ("RECUSADA", "recusada")])
def test_ca03_a_decisao_notifica_o_solicitante_sem_pedir_acao(
    solicitante: Usuario, situacao: str, palavra: str
) -> None:
    solicitacao = levar_a(enviada(solicitante), situacao)

    (notificacao,) = _do_tipo(solicitante, "aprovacoes.decidida")
    assert notificacao["pede_acao"] is False
    assert palavra in notificacao["texto"]
    assert "Motivo do cenário" in notificacao["texto"]
    assert notificacao["caminho"] == f"/solicitacoes/{solicitacao.id}"


# --- linha 3: contestada → o solicitante (pede ação) ---


def test_ca07_a_contestacao_notifica_o_solicitante_com_texto_padrao_mensagem_e_teto(
    solicitante: Usuario, aprovador: Usuario
) -> None:
    solicitacao = enviada(solicitante)
    motivo = "Valor acima do necessário"

    _post(
        aprovador,
        solicitacao,
        "contestar",
        motivo_id=_motivo(motivo),
        mensagem="Pesquise mais duas lojas.",
        teto_sugerido="120.00",
    )

    (notificacao,) = _do_tipo(solicitante, "aprovacoes.contestada")
    assert notificacao["pede_acao"] is True
    assert "contestada" in notificacao["texto"]
    assert motivo in notificacao["texto"]
    assert "Pesquise mais duas lojas." in notificacao["texto"]
    assert "R$ 120,00" in notificacao["texto"]


def test_a11_o_texto_da_notificacao_e_cortado_para_caber(solicitante: Usuario, aprovador: Usuario) -> None:
    solicitacao = enviada(solicitante)
    _post(
        aprovador,
        solicitacao,
        "contestar",
        motivo_id=_motivo("Falta justificativa"),
        mensagem="m" * 1000,
    )

    (notificacao,) = _do_tipo(solicitante, "aprovacoes.contestada")
    assert len(notificacao["texto"]) == 500
    assert notificacao["texto"].endswith("…")
    assert len(notificacao["titulo"]) <= 120


# --- linha 4: aprovador indicado → o indicado (ação) e o admin (informativa); A6 ---


def test_ca21_a6_o_indicado_recebe_so_o_aviso_de_indicacao_e_o_admin_e_informado(
    aprovador: Usuario, admin: Usuario
) -> None:
    indicado = com_cargo("indicado")

    enviada(aprovador, indicado=indicado)

    assert _tipos(indicado) == {"aprovacoes.aprovador_indicado"}
    (aviso,) = _do_tipo(indicado, "aprovacoes.aprovador_indicado")
    assert aviso["pede_acao"] is True
    (ao_admin,) = _do_tipo(admin, "aprovacoes.indicacao_feita")
    assert ao_admin["pede_acao"] is False
    assert "Diretor indicado" in ao_admin["texto"]


def test_a6_nas_versoes_seguintes_o_indicado_recebe_o_aviso_de_decidir(aprovador: Usuario) -> None:
    indicado = com_cargo("indicado")
    solicitacao = enviada(aprovador, indicado=indicado)
    _post(indicado, solicitacao, "contestar", **_contestar())

    _post(aprovador, solicitacao, "reenviar", conteudo=pedido())

    assert len(_do_tipo(indicado, "aprovacoes.para_decidir")) == 1


def _contestar() -> dict[str, Any]:
    return {
        "motivo_id": _motivo("Faltam detalhes dos itens"),
        "mensagem": "Detalhe os itens.",
    }


# --- linha 5: aprovação própria → o admin (informativa); A5 ---


def test_ca23_a_aprovacao_propria_avisa_os_admins(tipo_de_teste: TipoDeTeste, admin: Usuario) -> None:
    auto = com_cargo("auto", APROVAR_TESTE, AUTO_APROVAR)
    outro = _outro_admin()
    solicitacao = enviada(auto)

    _post(auto, solicitacao, "aprovar", motivo_id=_motivo("Dentro do orçamento"))

    for quem in (admin, outro):
        (aviso,) = _do_tipo(quem, "aprovacoes.aprovacao_propria")
        assert aviso["pede_acao"] is False


def test_a5_a_aprovacao_propria_de_um_admin_avisa_os_outros_admins(
    tipo_de_teste: TipoDeTeste, admin: Usuario
) -> None:
    outro = _outro_admin()
    solicitacao = enviada(admin)

    _post(admin, solicitacao, "aprovar", motivo_id=_motivo("Dentro do orçamento"))

    assert len(_do_tipo(outro, "aprovacoes.aprovacao_propria")) == 1
    assert _do_tipo(admin, "aprovacoes.aprovacao_propria") == []


def test_a5_sem_outro_admin_fica_so_a_auditoria(tipo_de_teste: TipoDeTeste, admin: Usuario) -> None:
    solicitacao = enviada(admin)

    _post(admin, solicitacao, "aprovar", motivo_id=_motivo("Dentro do orçamento"))

    assert _do_tipo(admin, "aprovacoes.aprovacao_propria") == []
    registros = auditoria.historico_do_item("solicitacao", solicitacao.id)
    assert registros[-1].dados["aprovacao_propria"] is True


# --- linha 8: cancelada ou retirada → quem podia decidir (informativa); A7 ---


@pytest.mark.parametrize(("acao", "corpo"), [("retirar", {}), ("cancelar", {"motivo": "Não precisa mais"})])
def test_retirada_ou_cancelada_em_analise_avisa_quem_podia_decidir(
    solicitante: Usuario, aprovador: Usuario, acao: str, corpo: dict[str, Any]
) -> None:
    solicitacao = enviada(solicitante)

    _post(solicitante, solicitacao, acao, **corpo)

    (aviso,) = _do_tipo(aprovador, "aprovacoes.saiu_da_fila")
    assert aviso["pede_acao"] is False
    assert _do_tipo(solicitante, "aprovacoes.saiu_da_fila") == []


@pytest.mark.parametrize("situacao", ["CONTESTADA", "RETIRADA", "RECUSADA", "APROVADA"])
def test_a7_cancelada_fora_da_analise_nao_avisa_que_saiu_da_fila(
    solicitante: Usuario, aprovador: Usuario, situacao: str
) -> None:
    solicitacao = levar_a(enviada(solicitante), situacao)
    antes = len(_do_tipo(aprovador, "aprovacoes.saiu_da_fila"))

    _post(solicitante, solicitacao, "cancelar", motivo="Desisti")

    assert len(_do_tipo(aprovador, "aprovacoes.saiu_da_fila")) == antes


# --- transversais ---


def test_a_notificacao_nao_se_repete_para_o_mesmo_fato(solicitante: Usuario, aprovador: Usuario) -> None:
    solicitacao = enviada(solicitante)
    avisos.para_decidir(solicitacao, ator_id=solicitante.id, fato="enviada")

    assert len(_do_tipo(aprovador, "aprovacoes.para_decidir")) == 1


def test_o_decisor_do_cenario_tambem_e_avisado(solicitante: Usuario) -> None:
    decisor = decisor_do_cenario()

    enviada(solicitante)

    assert len(_do_tipo(decisor, "aprovacoes.para_decidir")) == 1


def test_os_tipos_de_notificacao_e_se_pedem_acao() -> None:
    assert {codigo: pede_acao for codigo, (pede_acao, _) in avisos.TIPOS.items()} == {
        "aprovacoes.para_decidir": True,
        "aprovacoes.decidida": False,
        "aprovacoes.contestada": True,
        "aprovacoes.aprovador_indicado": True,
        "aprovacoes.indicacao_feita": False,
        "aprovacoes.aprovacao_propria": False,
        "aprovacoes.lembrete": True,
        "aprovacoes.parada": False,
        "aprovacoes.saiu_da_fila": False,
    }
