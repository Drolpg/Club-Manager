"""Modelos de `eventos`: métodos do aggregate, constraints e gatilhos no banco, e o registro no `ready`.

O aggregate é o modelo persistido (ADR-001): o estado só muda pelos métodos. Os gatilhos são a segunda
barreira de INV-EVT-04 e de "nada é apagado".
"""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.db import DatabaseError, IntegrityError, connection, models, transaction
from django.utils import timezone

from eventos.domain.regras import DadosDoEvento, EtapaDeAviso
from eventos.domain.situacao import SituacaoDoEvento
from eventos.models import CategoriaDeEvento, Evento, Imutavel, Presenca, RespostaDePresenca
from kernel.errors import BusinessError
from permissoes import public as permissoes
from tests import apoio

pytestmark = pytest.mark.django_db

S = SituacaoDoEvento


def _categoria(nome: str | None = None) -> CategoriaDeEvento:
    return CategoriaDeEvento.criar(nome or f"Categoria {uuid.uuid4().hex[:8]}")


def _dados(dias: int = 5, titulo: str = "Amistoso") -> DadosDoEvento:
    return DadosDoEvento(
        titulo=titulo, descricao="", local="Campo", inicio=timezone.now() + timedelta(days=dias)
    )


def _evento(*, envolve_custo: bool = False, categoria: CategoriaDeEvento | None = None) -> Evento:
    evento = Evento.propor(
        dados=_dados(),
        categoria=categoria or _categoria(),
        proponente_id=uuid.uuid7(),
        envolve_custo=envolve_custo,
    )
    evento.ligar_solicitacao_do_evento(uuid.uuid7())
    return evento


def _codigo(excecao: pytest.ExceptionInfo[BusinessError]) -> str:
    return excecao.value.code


# --- categoria ---


def test_categoria_renomeia_desativa_e_reativa_e_nao_e_apagada() -> None:
    categoria = _categoria("Treino")

    categoria.editar("Treino aberto")
    categoria.desativar()
    assert (categoria.nome, categoria.ativa) == ("Treino aberto", False)
    categoria.reativar()
    assert CategoriaDeEvento.objects.get(pk=categoria.pk).ativa
    with pytest.raises(Imutavel):
        categoria.delete()


def test_nome_de_categoria_e_unico_sem_diferenciar_maiusculas() -> None:
    _categoria("Churrasco")
    with pytest.raises(IntegrityError), transaction.atomic():
        _categoria("CHURRASCO")


# --- evento ---


def test_evento_nasce_em_aprovacao_com_o_retrato_da_categoria() -> None:
    categoria = _categoria("Confraternização")
    evento = _evento(categoria=categoria)

    assert evento.situacao == S.EM_APROVACAO
    assert evento.categoria_nome == "Confraternização"
    assert (evento.publicacoes, evento.ciclo_de_presenca) == (0, 1)
    with pytest.raises(ValueError, match="já"):
        evento.ligar_solicitacao_do_evento(uuid.uuid7())


def test_evento_nao_guarda_valor() -> None:
    """INV-EVT-02: o custo existe só no orçamento."""
    decimais = [campo.name for campo in Evento._meta.get_fields() if isinstance(campo, models.DecimalField)]

    assert decimais == []


def test_editar_diz_se_a_data_mudou_e_zera_as_marcas_de_aviso() -> None:
    evento = _evento()
    evento.marcar_aviso(EtapaDeAviso.NA_DATA, timezone.localdate())

    mesma_data = evento.inicio + timedelta(minutes=30)
    assert (
        evento.editar(_dados_com(evento, mesma_data), categoria=evento.categoria, envolve_custo=False)
        is False
    )
    assert evento.aviso_na_data_em is not None

    assert evento.editar(_dados(dias=9, titulo="Outro"), categoria=evento.categoria, envolve_custo=False)
    evento.refresh_from_db()
    assert evento.titulo == "Outro"
    assert evento.marcas_de_aviso()[EtapaDeAviso.NA_DATA] is None


def _dados_com(evento: Evento, inicio: Any) -> DadosDoEvento:
    return DadosDoEvento(titulo=evento.titulo, descricao=evento.descricao, local=evento.local, inicio=inicio)


def test_tirar_o_custo_com_orcamento_vinculado_e_recusado() -> None:
    evento = _evento(envolve_custo=True)
    evento.vincular_orcamento(uuid.uuid7())

    with pytest.raises(BusinessError) as recusa:
        evento.editar(_dados(), categoria=evento.categoria, envolve_custo=False)

    assert _codigo(recusa) == "ORCAMENTO_JA_VINCULADO"


def test_vincular_orcamento_so_com_custo_e_uma_vez() -> None:
    sem_custo = _evento()
    with pytest.raises(BusinessError) as recusa:
        sem_custo.vincular_orcamento(uuid.uuid7())
    assert _codigo(recusa) == "EVENTO_SEM_CUSTO"

    com_custo = _evento(envolve_custo=True)
    primeiro = uuid.uuid7()
    com_custo.vincular_orcamento(primeiro)
    with pytest.raises(BusinessError) as segundo:
        com_custo.vincular_orcamento(uuid.uuid7())
    assert _codigo(segundo) == "ORCAMENTO_JA_VINCULADO"

    com_custo.desvincular_orcamento(uuid.uuid7())
    assert com_custo.solicitacao_orcamentaria_id == primeiro
    com_custo.desvincular_orcamento(primeiro)
    assert Evento.objects.get(pk=com_custo.pk).solicitacao_orcamentaria_id is None


def test_mesmo_orcamento_nao_e_de_dois_eventos() -> None:
    orcamento = uuid.uuid7()
    _evento(envolve_custo=True).vincular_orcamento(orcamento)

    with pytest.raises(IntegrityError), transaction.atomic():
        _evento(envolve_custo=True).vincular_orcamento(orcamento)


def test_atualizar_situacao_devolve_a_transicao_e_conta_publicacoes() -> None:
    evento = _evento()

    assert evento.atualizar_situacao(S.EM_APROVACAO) is None
    transicao = evento.atualizar_situacao(S.PUBLICADO)
    assert transicao is not None
    assert (transicao.antes, transicao.depois) == (S.EM_APROVACAO, S.PUBLICADO)
    evento.atualizar_situacao(S.EM_APROVACAO)
    evento.atualizar_situacao(S.PUBLICADO)
    assert Evento.objects.get(pk=evento.pk).publicacoes == 2
    with pytest.raises(ValueError, match="comando"):
        evento.atualizar_situacao(S.CANCELADO)


def test_realizar_so_publicado_com_data_valida() -> None:
    evento = _evento()
    hoje = timezone.localdate()
    with pytest.raises(BusinessError) as fora:
        evento.confirmar_realizacao(data_real=hoje, motivo="", ator_id=uuid.uuid7(), hoje=hoje)
    assert _codigo(fora) == "NAO_ESTA_PUBLICADO"

    evento.atualizar_situacao(S.PUBLICADO)
    with pytest.raises(BusinessError) as sem_motivo:
        evento.confirmar_realizacao(data_real=hoje, motivo="", ator_id=uuid.uuid7(), hoje=hoje)
    assert (_codigo(sem_motivo), list(sem_motivo.value.details)) == ("VALIDATION_ERROR", ["motivo"])
    with pytest.raises(BusinessError) as futura:
        evento.confirmar_realizacao(
            data_real=hoje + timedelta(days=1), motivo="x", ator_id=uuid.uuid7(), hoje=hoje
        )
    assert _codigo(futura) == "DATA_FUTURA"

    quem = uuid.uuid7()
    evento.confirmar_realizacao(data_real=hoje, motivo="Antecipado", ator_id=quem, hoje=hoje)
    evento.refresh_from_db()
    assert (evento.situacao, evento.realizado_em_data, evento.realizado_por_id) == (S.REALIZADO, hoje, quem)
    assert evento.realizacao_motivo == "Antecipado"


def test_cancelar_exige_motivo_e_encerrado_nao_aceita_comando() -> None:
    evento = _evento()
    with pytest.raises(BusinessError) as sem_motivo:
        evento.cancelar(motivo=" ", ator_id=None)
    assert _codigo(sem_motivo) == "VALIDATION_ERROR"

    evento.cancelar(motivo="A data passou sem aprovação", ator_id=None, pelo_sistema=True)
    evento.refresh_from_db()
    assert (evento.situacao, evento.cancelado_pelo_sistema, evento.cancelado_por_id) == (
        S.CANCELADO,
        True,
        None,
    )
    for comando in (
        lambda: evento.cancelar(motivo="De novo", ator_id=None),
        lambda: evento.editar(_dados(), categoria=evento.categoria, envolve_custo=False),
        lambda: evento.vincular_orcamento(uuid.uuid7()),
    ):
        with pytest.raises(BusinessError) as encerrado:
            comando()
        assert _codigo(encerrado) == "EVENTO_ENCERRADO"
    assert evento.atualizar_situacao(S.PUBLICADO) is None


def test_evento_nao_e_apagado() -> None:
    with pytest.raises(Imutavel):
        _evento().delete()


# --- presença ---


def test_presenca_unica_por_ciclo_e_zerar_comeca_outro_ciclo() -> None:
    evento = _evento()
    diretor = uuid.uuid7()
    presenca = Presenca.responder(evento, diretor_id=diretor, resposta=RespostaDePresenca.VOU)
    assert (
        Presenca.responder(evento, diretor_id=diretor, resposta=RespostaDePresenca.NAO_VOU).pk == presenca.pk
    )
    assert Presenca.objects.get(pk=presenca.pk).resposta == RespostaDePresenca.NAO_VOU

    evento.zerar_presencas()
    nova = Presenca.responder(evento, diretor_id=diretor, resposta=RespostaDePresenca.VOU)
    assert (nova.ciclo, Presenca.objects.filter(evento=evento).count()) == (2, 2)
    with pytest.raises(Imutavel):
        nova.delete()


# --- no banco ---


def _sql(comando: str, *parametros: Any) -> None:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(comando, parametros)


@pytest.mark.parametrize("tabela", ["eventos_evento", "eventos_presenca", "eventos_categoriadeevento"])
def test_banco_recusa_apagar(tabela: str) -> None:
    evento = _evento()
    Presenca.responder(evento, diretor_id=uuid.uuid7(), resposta=RespostaDePresenca.VOU)

    with pytest.raises(DatabaseError):
        _sql(f"DELETE FROM {tabela}")  # noqa: S608 - nome fixo do parametrize


@pytest.mark.parametrize("situacao", ["REALIZADO", "CANCELADO"])
def test_banco_recusa_alterar_evento_encerrado(situacao: str) -> None:
    evento = _evento()
    if situacao == "CANCELADO":
        evento.cancelar(motivo="Chuva", ator_id=None)
    else:
        evento.atualizar_situacao(S.PUBLICADO)
        hoje = timezone.localdate()
        evento.confirmar_realizacao(data_real=hoje, motivo="Antes", ator_id=uuid.uuid7(), hoje=hoje)

    with pytest.raises(DatabaseError):
        _sql("UPDATE eventos_evento SET titulo = 'outro' WHERE id = %s", evento.id)


def test_banco_exige_motivo_e_momento_no_cancelado() -> None:
    evento = _evento()

    with pytest.raises(IntegrityError):
        _sql("UPDATE eventos_evento SET situacao = 'CANCELADO' WHERE id = %s", evento.id)


# --- registro no ready ---


def test_permissoes_e_tipo_de_solicitacao_registrados() -> None:
    for codigo in ("eventos.propor", "eventos.aprovar", "eventos.cancelar"):
        assert permissoes.nome_da_permissao(codigo) is not None
    admin = apoio.criar_admin("admin.eventos")

    tipos = apoio.cliente_de(admin).get("/api/v1/aprovacoes/tipos/").json()

    assert {"codigo": "eventos.evento", "nome": "Evento", "tem_valor": False} in tipos
