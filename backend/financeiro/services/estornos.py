"""Casos de uso de estorno financeiro como lançamento compensatório ligado (ADR-013, INV-SAI-09)."""

import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from acesso import public as acesso
from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro import tipos
from financeiro.domain.autorizacao import PERM_FINANCEIRO_ESTORNAR
from financeiro.domain.saidas import calcular_valor_realizado_saida
from financeiro.domain.transicoes import ComandoCobranca, ComandoEntrada, ComandoSaida
from financeiro.erros import erro, erro_validacao
from financeiro.models import AlvoEstorno, Cobranca, Entrada, Estorno, Saida
from financeiro.services import autorizacao, avisos, consulta, entradas
from kernel.errors import BusinessError


def _validar_justificativa(justificativa: str) -> str:
    limpa = justificativa.strip()
    if not limpa:
        raise erro_validacao("justificativa", "Informe a justificativa do estorno.")
    if len(limpa) > 1000:
        raise erro_validacao("justificativa", "Use no máximo 1000 caracteres na justificativa.")
    return limpa


def _serializar_estorno(estorno: Estorno, cache: dict[uuid.UUID, consulta.PessoaInfo]) -> dict[str, Any]:
    alvo_id = estorno.saida_id or estorno.entrada_id or estorno.cobranca_id
    return {
        "id": estorno.id,
        "alvo_tipo": estorno.alvo_tipo,
        "alvo_id": alvo_id,
        "valor": estorno.valor,
        "motivo_id": estorno.motivo_id,
        "motivo_texto": estorno.motivo_texto,
        "justificativa": estorno.justificativa,
        "registrado_por": consulta.pessoa_dict(estorno.registrado_por_id, cache),
        "registrado_em": estorno.registrado_em,
    }


def _registrar_estorno(
    *,
    ator_id: uuid.UUID,
    alvo_tipo: AlvoEstorno,
    item_tipo: str,
    item_id: uuid.UUID,
    saida: Saida | None = None,
    entrada: Entrada | None = None,
    cobranca: Cobranca | None = None,
    valor: Decimal,
    motivo_id: uuid.UUID,
    justificativa: str,
    interessado_id: uuid.UUID,
    titulo_aviso: str,
    texto_aviso: str,
    caminho: str,
) -> Estorno:
    just_limpa = _validar_justificativa(justificativa)
    if valor <= Decimal("0.00"):
        raise erro("NAO_PODE_ESTORNAR")
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_ESTORNAR)
    agora = timezone.now()
    estorno = Estorno.objects.create(
        alvo_tipo=alvo_tipo,
        saida=saida,
        entrada=entrada,
        cobranca=cobranca,
        valor=valor,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        justificativa=just_limpa,
        registrado_por_id=ator_id,
        registrado_em=agora,
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="ESTORNO_REGISTRADO",
        item_tipo="estorno",
        item_id=estorno.id,
        justificativa=just_limpa,
        dados={
            "alvo_tipo": alvo_tipo.value,
            "alvo_id": str(item_id),
            "valor": str(valor),
            "motivo_id": str(motivo_id),
            "motivo_texto": motivo_texto,
        },
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao=f"{item_tipo.upper()}_ESTORNADA",
        item_tipo=item_tipo,
        item_id=item_id,
        justificativa=just_limpa,
        dados={
            "estorno_id": str(estorno.id),
            "valor": str(valor),
            "motivo_id": str(motivo_id),
            "motivo_texto": motivo_texto,
        },
    )
    avisos.registro_estornado(
        estorno_id=estorno.id,
        item_tipo=item_tipo,
        item_id=item_id,
        interessado_id=interessado_id,
        titulo=titulo_aviso,
        texto=texto_aviso,
        caminho=caminho,
    )
    return estorno


@transaction.atomic
def estornar_saida(
    ator_id: uuid.UUID, saida_id: uuid.UUID, *, motivo_id: uuid.UUID, justificativa: str
) -> dict[str, Any]:
    """Estorna saída liquidada criando lançamento compensatório imutável (ADR-013, CA-27/28)."""
    autorizacao.exigir_permissao(ator_id, PERM_FINANCEIRO_ESTORNAR)
    saida = Saida.objects.select_for_update().filter(pk=saida_id).first()
    if saida is None:
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_saida(saida, ator_id, ComandoSaida.ESTORNAR)
    valor_realizado = calcular_valor_realizado_saida(saida.total_enviado(), saida.total_devolvido_validado())
    if valor_realizado <= Decimal("0.00"):
        raise erro(
            "NAO_PODE_ESTORNAR",
            mensagem="Saída com valor líquido zerado pelas devoluções não possui saldo a estornar.",
        )
    saida.estornar()
    estorno = _registrar_estorno(
        ator_id=ator_id,
        alvo_tipo=AlvoEstorno.SAIDA,
        item_tipo="saida",
        item_id=saida.id,
        saida=saida,
        valor=valor_realizado,
        motivo_id=motivo_id,
        justificativa=justificativa,
        interessado_id=saida.solicitante_id,
        titulo_aviso="Saída estornada",
        texto_aviso=f"A saída “{saida.descricao}” (R$ {valor_realizado:.2f}) foi estornada.",
        caminho=f"/saidas/{saida.id}",
    )
    cache: dict[uuid.UUID, consulta.PessoaInfo] = {}
    return {**_serializar_estorno(estorno, cache), "registro": consulta.detalhe_saida(ator_id, saida.id)}


@transaction.atomic
def estornar_entrada(
    ator_id: uuid.UUID, entrada_id: uuid.UUID, *, motivo_id: uuid.UUID, justificativa: str
) -> dict[str, Any]:
    """Estorna entrada validada; devolução vinculada a saída liquidada exige estornar a saída antes."""
    usuario: acesso.UsuarioInfo = autorizacao.exigir_permissao(ator_id, PERM_FINANCEIRO_ESTORNAR)
    entrada = Entrada.objects.select_for_update().filter(pk=entrada_id).first()
    if entrada is None:
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_entrada(entrada, ator_id, ComandoEntrada.ESTORNAR)
    entrada.estornar()
    estorno = _registrar_estorno(
        ator_id=ator_id,
        alvo_tipo=AlvoEstorno.ENTRADA,
        item_tipo="entrada",
        item_id=entrada.id,
        entrada=entrada,
        valor=entrada.valor,
        motivo_id=motivo_id,
        justificativa=justificativa,
        interessado_id=entrada.registrada_por_id,
        titulo_aviso="Entrada estornada",
        texto_aviso=f"A entrada “{entrada.origem}” (R$ {entrada.valor:.2f}) foi estornada.",
        caminho="/entradas",
    )
    cache: dict[uuid.UUID, consulta.PessoaInfo] = {}
    return {
        **_serializar_estorno(estorno, cache),
        "registro": entradas.serializar_entrada(entrada, ator_id=ator_id, usuario=usuario, cache=cache),
    }


@transaction.atomic
def estornar_cobranca(
    ator_id: uuid.UUID, cobranca_id: uuid.UUID, *, motivo_id: uuid.UUID, justificativa: str
) -> dict[str, Any]:
    """Estorna cobrança paga invalidando o recibo sem apagar o histórico (CA-27, CA-29)."""
    autorizacao.exigir_permissao(ator_id, PERM_FINANCEIRO_ESTORNAR)
    cobranca = Cobranca.objects.select_for_update().filter(pk=cobranca_id).first()
    if cobranca is None:
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.ESTORNAR)
    cobranca.estornar()
    estorno = _registrar_estorno(
        ator_id=ator_id,
        alvo_tipo=AlvoEstorno.COBRANCA,
        item_tipo="cobranca",
        item_id=cobranca.id,
        cobranca=cobranca,
        valor=cobranca.valor,
        motivo_id=motivo_id,
        justificativa=justificativa,
        interessado_id=cobranca.devedor_id,
        titulo_aviso="Cobrança estornada",
        texto_aviso=(
            f"O pagamento da cobrança “{cobranca.descricao}” (R$ {cobranca.valor:.2f}) foi estornado."
        ),
        caminho=f"/cobrancas/{cobranca.id}",
    )
    cache: dict[uuid.UUID, consulta.PessoaInfo] = {}
    return {
        **_serializar_estorno(estorno, cache),
        "registro": consulta.serializar_detalhe(cobranca, ator_id=ator_id),
    }


def listar(
    ator_id: uuid.UUID,
    *,
    alvo_tipo: str | None = None,
    antes: uuid.UUID | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista lançamentos de estorno em ordem decrescente com paginação por cursor."""
    autorizacao.exigir_leitura_gestao(ator_id)
    qs = Estorno.objects.all()
    if alvo_tipo:
        if alvo_tipo not in AlvoEstorno.values:
            raise BusinessError("NOT_FOUND", "Tipo de alvo inválido.", status=404)
        qs = qs.filter(alvo_tipo=alvo_tipo)
    if antes is not None:
        ancora = Estorno.objects.filter(pk=antes).values("registrado_em", "id").first()
        if ancora is None:
            raise erro("NOT_FOUND")
        qs = qs.exclude(pk=antes).filter(registrado_em__lte=ancora["registrado_em"])
        qs = qs.exclude(registrado_em=ancora["registrado_em"], id__gte=ancora["id"])
    itens_bd = list(qs[: limite + 1])
    tem_mais = len(itens_bd) > limite
    cache: dict[uuid.UUID, consulta.PessoaInfo] = {}
    return {
        "itens": [_serializar_estorno(e, cache) for e in itens_bd[:limite]],
        "tem_mais": tem_mais,
    }
