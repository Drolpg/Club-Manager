"""Casos de uso operacionais de saídas: envios, prestações, devoluções, complementos e liquidação."""

import uuid
from datetime import date, datetime
from typing import Any

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro import tipos
from financeiro.domain.autorizacao import PERM_SAIDAS_ENVIAR, PERM_SAIDAS_LIQUIDAR, pode_ver_anexos_saida
from financeiro.domain.saidas import ErroDeRegraSaida, validar_devolucao_de_sobra, validar_pedido_complemento
from financeiro.domain.transicoes import ComandoSaida, SituacaoSaida
from financeiro.erros import erro, erro_validacao
from financeiro.models import (
    CategoriaFinanceira,
    Complemento,
    Envio,
    NaturezaCategoria,
    PrestacaoDeContas,
    Saida,
    SituacaoComplemento,
    TipoEntrada,
)
from financeiro.services import autorizacao, avisos, consulta, entradas, gastos
from kernel.anexos import AnexoSalvo, resposta_anexo, validar_e_salvar_anexo
from kernel.dinheiro import Dinheiro
from permissoes import public as permissoes


def _buscar_saida_bloqueada(ator_id: uuid.UUID, saida_id: uuid.UUID) -> Saida:
    autorizacao.exigir_leitura_gestao(ator_id)
    saida = Saida.objects.select_for_update().filter(pk=saida_id).first()
    if saida is None:
        raise erro("NOT_FOUND")
    return saida


def _resolver_categoria_devolucao(categoria_id: uuid.UUID | None) -> CategoriaFinanceira:
    if categoria_id is not None:
        cat = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
        if cat is None:
            raise erro_validacao("categoria_id", "Categoria financeira não encontrada.")
        if not cat.ativa or cat.natureza != NaturezaCategoria.ENTRADA:
            raise erro("CATEGORIA_INATIVA")
        return cat
    padrao = CategoriaFinanceira.objects.filter(
        nome__iexact="Diversos", natureza=NaturezaCategoria.ENTRADA, ativa=True
    ).first()
    if padrao is not None:
        return padrao
    alternativa = CategoriaFinanceira.objects.filter(natureza=NaturezaCategoria.ENTRADA, ativa=True).first()
    if alternativa is None:
        raise erro("CATEGORIA_INATIVA")
    return alternativa


@transaction.atomic
def enviar_recurso(
    ator_id: uuid.UUID,
    saida_id: uuid.UUID,
    *,
    valor: Dinheiro,
    arquivo: Any,
    enviado_em: datetime | None = None,
    complemento_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Registra remessa inicial ou envio de complemento aprovado com comprovante (CA-08, CA-09, CA-19)."""
    autorizacao.exigir_permissao(ator_id, PERM_SAIDAS_ENVIAR)
    saida = Saida.objects.select_for_update().filter(pk=saida_id).first()
    if saida is None:
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_saida(saida, ator_id, ComandoSaida.ENVIAR_RECURSO)

    complemento: Complemento | None = None
    eh_inicial = complemento_id is None
    if complemento_id is None:
        if saida.situacao != SituacaoSaida.AGUARDANDO_ENVIO.value:
            raise erro("NAO_AGUARDA_ENVIO")
    else:
        complemento = Complemento.objects.select_for_update().filter(pk=complemento_id, saida=saida).first()
        if complemento is None or complemento.situacao != SituacaoComplemento.APROVADO:
            raise erro("NAO_AGUARDA_ENVIO")
        if Envio.objects.filter(complemento=complemento).exists():
            raise erro("NAO_AGUARDA_ENVIO")

    if arquivo is None:
        raise erro_validacao("comprovante", "Anexe o comprovante da transferência realizada.")
    anexo = validar_e_salvar_anexo(arquivo, contexto="envios")

    momento = enviado_em or timezone.now()
    envio = saida.registrar_envio(
        valor=valor,
        enviado_por_id=ator_id,
        enviado_em=momento,
        comprovante=anexo,
        complemento=complemento,
    )
    if eh_inicial:
        aprovacoes.iniciar_execucao(saida.solicitacao_id, ator_id=ator_id)

    auditoria.registrar(
        ator_id=ator_id,
        acao="RECURSO_ENVIADO",
        item_tipo="saida",
        item_id=saida.id,
        dados={
            "envio_id": str(envio.id),
            "valor": str(envio.valor),
            "complemento_id": str(complemento.id) if complemento else None,
        },
    )
    avisos.recurso_enviado(saida, envio)
    return consulta.detalhe_saida(ator_id, saida.id)


def baixar_comprovante_envio(ator_id: uuid.UUID, saida_id: uuid.UUID, envio_id: uuid.UUID) -> HttpResponse:
    """Entrega o comprovante de envio a qualquer usuário com leitura de gestão (P6)."""
    usuario = autorizacao.exigir_leitura_gestao(ator_id)
    if not pode_ver_anexos_saida(ator_le_gestao=permissoes.le_gestao(ator_id), ator_admin=usuario.admin):
        raise erro("PERMISSION_DENIED")
    envio = Envio.objects.filter(pk=envio_id, saida_id=saida_id).first()
    if envio is None:
        raise erro("NOT_FOUND")
    return resposta_anexo(
        chave=envio.comprovante_chave,
        nome=envio.comprovante_nome,
        mime=envio.comprovante_mime,
    )


@transaction.atomic
def prestar_contas(
    ator_id: uuid.UUID,
    saida_id: uuid.UUID,
    *,
    valor: Dinheiro,
    descricao: str = "",
    arquivo: Any = None,
) -> dict[str, Any]:
    """Registra a prestação de contas do solicitante e coloca a saída em conferência (CA-12, CA-13)."""
    saida = _buscar_saida_bloqueada(ator_id, saida_id)
    autorizacao.exigir_comando_saida(saida, ator_id, ComandoSaida.PRESTAR_CONTAS)
    if saida.situacao != SituacaoSaida.RECURSO_ENVIADO.value:
        raise erro("NAO_AGUARDA_PRESTACAO")
    if valor.quantia <= 0:
        raise erro("VALOR_INVALIDO")
    limpa = descricao.strip()
    if not limpa and arquivo is None:
        raise erro_validacao("comprovante", "Anexe o comprovante ou descreva a despesa realizada.")

    anexo: AnexoSalvo | None = None
    if arquivo is not None:
        anexo = validar_e_salvar_anexo(arquivo, contexto="prestacoes")

    prestacao = saida.prestar_contas(
        valor=valor,
        descricao=limpa,
        comprovante=anexo,
        por_id=ator_id,
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="PRESTACAO_REGISTRADA",
        item_tipo="saida",
        item_id=saida.id,
        dados={"prestacao_id": str(prestacao.id), "valor": str(prestacao.valor)},
    )
    avisos.prestacao_registrada(saida, prestacao)
    return consulta.detalhe_saida(ator_id, saida.id)


def baixar_comprovante_prestacao(
    ator_id: uuid.UUID, saida_id: uuid.UUID, prestacao_id: uuid.UUID
) -> HttpResponse:
    """Entrega o comprovante da prestação a quem lê gestão (P6)."""
    usuario = autorizacao.exigir_leitura_gestao(ator_id)
    if not pode_ver_anexos_saida(ator_le_gestao=permissoes.le_gestao(ator_id), ator_admin=usuario.admin):
        raise erro("PERMISSION_DENIED")
    prest = PrestacaoDeContas.objects.filter(pk=prestacao_id, saida_id=saida_id).first()
    if prest is None or not prest.comprovante_chave:
        raise erro("NOT_FOUND")
    return resposta_anexo(
        chave=prest.comprovante_chave,
        nome=prest.comprovante_nome,
        mime=prest.comprovante_mime,
    )


@transaction.atomic
def devolver_prestacao(
    ator_id: uuid.UUID,
    saida_id: uuid.UUID,
    *,
    motivo_id: uuid.UUID,
    texto: str = "",
) -> dict[str, Any]:
    """Devolve a prestação de contas para o solicitante ajustar (RF-077, CA-15)."""
    autorizacao.exigir_permissao(ator_id, PERM_SAIDAS_LIQUIDAR)
    saida = Saida.objects.select_for_update().filter(pk=saida_id).first()
    if saida is None:
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_saida(saida, ator_id, ComandoSaida.DEVOLVER_PRESTACAO)
    if saida.situacao != SituacaoSaida.EM_CONFERENCIA.value:
        raise erro("NAO_ESTA_EM_CONFERENCIA")
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_PRESTACAO_DEVOLVER)
    prest = saida.devolver_prestacao(
        por_id=ator_id,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        texto=texto,
        agora=timezone.now(),
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="PRESTACAO_DEVOLVIDA",
        item_tipo="saida",
        item_id=saida.id,
        justificativa=texto.strip() or motivo_texto,
        dados={
            "prestacao_id": str(prest.id),
            "motivo_id": str(motivo_id),
            "motivo_texto": motivo_texto,
        },
    )
    avisos.prestacao_devolvida(saida, prest)
    return consulta.detalhe_saida(ator_id, saida.id)


@transaction.atomic
def devolver_sobra(
    ator_id: uuid.UUID,
    saida_id: uuid.UUID,
    *,
    valor: Dinheiro,
    data_devolucao: date | None = None,
    categoria_id: uuid.UUID | None = None,
    origem: str = "",
    evidencia_texto: str = "",
    arquivo: Any = None,
) -> dict[str, Any]:
    """Registra devolução de sobra ligada à saída, em validação como Entrada(DEVOLUCAO) (CA-16/17)."""
    usuario = autorizacao.exigir_leitura_gestao(ator_id)
    saida = Saida.objects.select_for_update().filter(pk=saida_id).first()
    if saida is None:
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_saida(saida, ator_id, ComandoSaida.DEVOLVER_SOBRA)

    categoria = _resolver_categoria_devolucao(categoria_id)
    try:
        validar_devolucao_de_sobra(
            situacao=SituacaoSaida(saida.situacao),
            valor=valor.quantia,
            total_enviado=saida.total_enviado(),
            total_devolvido_ativo=saida.total_devolvido_ativo(),
        )
    except ErroDeRegraSaida as exc:
        if exc.codigo == "VALIDATION_ERROR":
            raise erro_validacao(exc.campo or "valor", exc.mensagem) from None
        raise erro(exc.codigo, mensagem=exc.mensagem) from None

    texto_evid = evidencia_texto.strip()
    if not texto_evid and arquivo is None:
        raise erro_validacao("evidencia_texto", "Informe o comprovante ou um texto de evidência.")

    anexo = validar_e_salvar_anexo(arquivo, contexto="entradas") if arquivo is not None else None
    from financeiro.models import Entrada

    entrada = Entrada.registrar(
        categoria=categoria,
        valor=valor,
        data=data_devolucao or timezone.localdate(),
        origem=origem.strip() or f"Devolução de sobra: {saida.descricao}"[:150],
        evidencia_texto=texto_evid,
        anexo=anexo,
        registrada_por_id=ator_id,
        tipo=TipoEntrada.DEVOLUCAO,
        saida=saida,
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="ENTRADA_REGISTRADA",
        item_tipo="entrada",
        item_id=entrada.id,
        dados={
            "categoria_id": str(categoria.id),
            "valor": str(entrada.valor),
            "data": entrada.data.isoformat(),
            "tipo": entrada.tipo,
            "saida_id": str(saida.id),
        },
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="DEVOLUCAO_REGISTRADA",
        item_tipo="saida",
        item_id=saida.id,
        dados={"entrada_id": str(entrada.id), "valor": str(entrada.valor)},
    )
    avisos.entrada_registrada(entrada)
    return entradas.serializar_entrada(entrada, ator_id=ator_id, usuario=usuario)


@transaction.atomic
def pedir_complemento(
    ator_id: uuid.UUID,
    saida_id: uuid.UUID,
    *,
    itens: list[dict[str, Any]],
    descricao: str = "",
    cotacao_id: uuid.UUID | None = None,
    aprovador_indicado_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Abre nova solicitação de gasto vinculada à saída em conferência (RF-079, P12, CA-18)."""
    saida = _buscar_saida_bloqueada(ator_id, saida_id)
    autorizacao.exigir_comando_saida(saida, ator_id, ComandoSaida.PEDIR_COMPLEMENTO)
    prest = saida.prestacao_vigente()
    try:
        validar_pedido_complemento(
            situacao=SituacaoSaida(saida.situacao),
            valor_prestacao=prest.valor if prest is not None else None,
            total_enviado=saida.total_enviado(),
            tem_complemento_em_andamento=saida.complemento_em_andamento() is not None,
        )
    except ErroDeRegraSaida as exc:
        raise erro(exc.codigo, mensagem=exc.mensagem) from None

    desc_comp = (descricao.strip() or f"Complemento: {saida.descricao}")[:200]
    sol_id = aprovacoes.enviar(
        tipo=gastos.TIPO_GASTO,
        solicitante_id=ator_id,
        aprovador_indicado_id=aprovador_indicado_id,
        conteudo={
            "descricao": desc_comp,
            "categoria_id": str(saida.categoria_id),
            "setor_id": str(saida.setor_id),
            "itens": itens,
            "cotacao_id": str(cotacao_id) if cotacao_id else None,
            "saida_origem_id": str(saida.id),
        },
    )
    info = aprovacoes.obter_solicitacao(sol_id)
    if info.valor is None:
        raise erro("VALOR_INVALIDO")
    agora = timezone.now()
    autoaprovada = info.situacao == aprovacoes.Situacao.APROVADA
    comp = Complemento.objects.create(
        saida=saida,
        solicitacao_id=sol_id,
        valor=info.valor,
        situacao=SituacaoComplemento.APROVADO if autoaprovada else SituacaoComplemento.EM_ANDAMENTO,
        aprovado_em=agora if autoaprovada else None,
        decidido_em=agora if autoaprovada else None,
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="COMPLEMENTO_SOLICITADO",
        item_tipo="saida",
        item_id=saida.id,
        dados={"complemento_id": str(comp.id), "solicitacao_id": str(sol_id), "valor": str(comp.valor)},
    )
    if autoaprovada:
        auditoria.registrar(
            ator_id=ator_id,
            acao="COMPLEMENTO_APROVADO",
            item_tipo="saida",
            item_id=saida.id,
            dados={"complemento_id": str(comp.id), "valor": str(comp.valor)},
        )
        avisos.complemento_aprovado(saida, comp)
    return {
        "id": comp.id,
        "saida_id": saida.id,
        "solicitacao_id": comp.solicitacao_id,
        "valor": comp.valor,
        "situacao": comp.situacao,
    }


@transaction.atomic
def liquidar(
    ator_id: uuid.UUID,
    saida_id: uuid.UUID,
    *,
    justificativa: str = "",
) -> dict[str, Any]:
    """Liquida saída após fechamento de contas e encerra a solicitação no motor (CA-20 a CA-25)."""
    autorizacao.exigir_permissao(ator_id, PERM_SAIDAS_LIQUIDAR)
    saida = Saida.objects.select_for_update().filter(pk=saida_id).first()
    if saida is None:
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_saida(saida, ator_id, ComandoSaida.LIQUIDAR)
    resultado = saida.liquidar(por_id=ator_id, justificativa=justificativa, agora=timezone.now())
    aprovacoes.encerrar(saida.solicitacao_id, ator_id=ator_id)
    auditoria.registrar(
        ator_id=ator_id,
        acao="SAIDA_LIQUIDADA",
        item_tipo="saida",
        item_id=saida.id,
        justificativa=justificativa.strip(),
        dados={
            "valor_nao_reembolsado": str(resultado.valor_nao_reembolsado),
            "sobra": str(resultado.sobra),
            "total_enviado": str(saida.total_enviado()),
        },
    )
    avisos.saida_liquidada(saida)
    return consulta.detalhe_saida(ator_id, saida.id)
