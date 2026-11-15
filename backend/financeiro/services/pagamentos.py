"""Casos de uso de pagamento, comprovante privado e emissão do recibo PDF."""

import uuid
from datetime import date
from typing import Any

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from acesso import public as acesso
from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro import tipos
from financeiro.domain.autorizacao import PERM_PAGAMENTOS_VALIDAR, pode_ver_comprovante_cobranca
from financeiro.domain.transicoes import ComandoCobranca, SituacaoCobranca
from financeiro.erros import erro
from financeiro.models import Cobranca, FormaPagamento, Pagamento, SituacaoPagamento
from financeiro.recibo_pdf import DadosRecibo, gerar_recibo_pdf
from financeiro.services import autorizacao, avisos, consulta
from kernel.anexos import AnexoSalvo, resposta_anexo, validar_e_salvar_anexo


def _trancar_cobranca(cobranca_id: uuid.UUID) -> Cobranca:
    cobranca = (
        Cobranca.objects.select_for_update()
        .select_related("categoria", "chave_pix")
        .filter(id=cobranca_id)
        .first()
    )
    if cobranca is None:
        raise erro("NOT_FOUND")
    return cobranca


@transaction.atomic
def registrar(
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    *,
    forma: str,
    data_pagamento: date,
    recebedor_id: uuid.UUID | None = None,
    arquivo: Any = None,
) -> Cobranca:
    """Registra tentativa de pagamento com comprovante ou entrega em mão pelo devedor."""
    autorizacao.exigir_diretor_ativo(ator_id)
    cobranca = _trancar_cobranca(cobranca_id)
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.REGISTRAR_PAGAMENTO)

    forma_enum = FormaPagamento(forma)
    anexo: AnexoSalvo | None = None
    if forma_enum == FormaPagamento.COMPROVANTE:
        if recebedor_id is not None:
            raise erro("RECEBEDOR_INVALIDO")
        anexo = validar_e_salvar_anexo(arquivo, contexto="comprovantes")
    else:
        if arquivo is not None or recebedor_id is None:
            raise erro("RECEBEDOR_INVALIDO")
        recebedor = acesso.usuario_por_id(recebedor_id)
        if recebedor is None or not recebedor.ativo:
            raise erro("RECEBEDOR_INVALIDO")

    pagamento = cobranca.registrar_pagamento(
        forma=forma_enum,
        data_pagamento=data_pagamento,
        recebedor_id=recebedor_id,
        anexo=anexo,
    )
    auditoria.registrar(
        acao="COBRANCA_PAGAMENTO_REGISTRADO",
        ator_id=ator_id,
        item_tipo="cobranca",
        item_id=cobranca.id,
        dados={
            "pagamento_id": str(pagamento.id),
            "forma": pagamento.forma,
            "data_pagamento": data_pagamento.isoformat(),
            "recebedor_id": str(recebedor_id) if recebedor_id else None,
        },
    )
    avisos.pagamento_registrado(cobranca, pagamento)
    return cobranca


@transaction.atomic
def validar(
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    *,
    motivo_id: uuid.UUID,
    texto: str = "",
) -> Cobranca:
    """Valida pagamento em aberto, liquidando a cobrança (CA-15, CA-16, CA-20)."""
    cobranca = _trancar_cobranca(cobranca_id)
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.VALIDAR_PAGAMENTO)
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_PAGAMENTO_VALIDAR)
    pagamento = cobranca.validar_pagamento(
        por_id=ator_id,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        texto=texto,
        agora=timezone.now(),
    )
    auditoria.registrar(
        acao="COBRANCA_PAGAMENTO_VALIDADO",
        ator_id=ator_id,
        item_tipo="cobranca",
        item_id=cobranca.id,
        justificativa=f"{motivo_texto} {texto.strip()}".strip(),
        dados={"pagamento_id": str(pagamento.id), "valor": str(cobranca.valor)},
    )
    avisos.pagamento_validado(cobranca, pagamento)
    return cobranca


@transaction.atomic
def rejeitar(
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    *,
    motivo_id: uuid.UUID,
    texto: str = "",
) -> Cobranca:
    """Rejeita pagamento em validação e retorna cobrança para aberta ou atrasada (CA-17)."""
    cobranca = _trancar_cobranca(cobranca_id)
    autorizacao.exigir_comando_cobranca(cobranca, ator_id, ComandoCobranca.REJEITAR_PAGAMENTO)
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipos.DECISAO_PAGAMENTO_REJEITAR)
    pagamento = cobranca.rejeitar_pagamento(
        por_id=ator_id,
        motivo_id=motivo_id,
        motivo_texto=motivo_texto,
        texto=texto,
        agora=timezone.now(),
        hoje=timezone.localdate(),
    )
    auditoria.registrar(
        acao="COBRANCA_PAGAMENTO_REJEITADO",
        ator_id=ator_id,
        item_tipo="cobranca",
        item_id=cobranca.id,
        justificativa=f"{motivo_texto} {texto.strip()}".strip(),
        dados={"pagamento_id": str(pagamento.id), "nova_situacao": cobranca.situacao},
    )
    avisos.pagamento_rejeitado(cobranca, pagamento)
    return cobranca


def baixar_comprovante(
    ator_id: uuid.UUID,
    cobranca_id: uuid.UUID,
    pagamento_id: uuid.UUID,
) -> HttpResponse:
    """Serve o arquivo de comprovante somente a devedor, validador de pagamento ou admin (CA-18)."""
    usuario = autorizacao.exigir_diretor_ativo(ator_id)
    cobranca = consulta.obter_no_escopo(ator_id, cobranca_id)
    tem_validar = autorizacao.permissao_ou_admin(usuario, PERM_PAGAMENTOS_VALIDAR)
    if not pode_ver_comprovante_cobranca(
        ator_id=ator_id,
        ator_admin=usuario.admin,
        tem_permissao_validar=tem_validar,
        devedor_id=cobranca.devedor_id,
    ):
        raise erro(
            "PERMISSION_DENIED",
            mensagem="Comprovantes só ficam acessíveis ao devedor, validadores de pagamento e admin.",
        )

    pagamento = Pagamento.objects.filter(id=pagamento_id, cobranca_id=cobranca.id).first()
    if pagamento is None or not pagamento.comprovante_chave:
        raise erro("NOT_FOUND")
    return resposta_anexo(
        chave=pagamento.comprovante_chave,
        nome=pagamento.comprovante_nome,
        mime=pagamento.comprovante_mime,
    )


def emitir_recibo(ator_id: uuid.UUID, cobranca_id: uuid.UUID) -> HttpResponse:
    """Gera e devolve o recibo PDF da cobrança liquidada para quem está no escopo (CA-19)."""
    cobranca = consulta.obter_no_escopo(ator_id, cobranca_id)
    if cobranca.situacao != SituacaoCobranca.PAGA.value:
        raise erro("NAO_ESTA_PAGA")

    pagamento = (
        cobranca.pagamentos.filter(situacao=SituacaoPagamento.VALIDADO.value)
        .order_by("-decidido_em", "-id")
        .first()
    )
    if pagamento is None or cobranca.paga_em is None:
        raise erro("NAO_ESTA_PAGA")

    devedor = acesso.usuario_por_id(cobranca.devedor_id)
    data_validacao = pagamento.decidido_em.date() if pagamento.decidido_em else cobranca.paga_em.date()
    dados = DadosRecibo(
        cobranca_id=cobranca.id,
        devedor_nome=devedor.nome if devedor else "Diretor",
        categoria_nome=cobranca.categoria_nome,
        descricao=cobranca.descricao,
        valor=cobranca.valor,
        data_pagamento=pagamento.data_pagamento,
        data_validacao=data_validacao,
    )
    resposta = HttpResponse(gerar_recibo_pdf(dados), content_type="application/pdf")
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, no-store"
    resposta["Content-Disposition"] = f'inline; filename="recibo-{cobranca.id}.pdf"'
    return resposta
