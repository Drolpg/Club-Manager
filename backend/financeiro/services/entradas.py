"""Casos de uso de entradas sem devedor (patrocínios, rifas, doações) e devoluções."""

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
from financeiro.domain.autorizacao import (
    PERM_ENTRADAS_REGISTRAR,
    PERM_ENTRADAS_VALIDAR,
    acoes_entrada_disponiveis,
    pode_ver_comprovante_entrada,
)
from financeiro.domain.transicoes import ComandoEntrada
from financeiro.erros import erro
from financeiro.models import CategoriaFinanceira, Entrada
from financeiro.services import autorizacao, avisos, consulta
from financeiro.services.consulta import PessoaInfo, ResumoEntradasValidadas, pessoa_dict
from kernel.anexos import AnexoSalvo, resposta_anexo, validar_e_salvar_anexo
from kernel.dinheiro import Dinheiro


def serializar_entrada(
    entrada: Entrada,
    *,
    ator_id: uuid.UUID,
    usuario: acesso.UsuarioInfo,
    cache: dict[uuid.UUID, PessoaInfo] | None = None,
) -> dict[str, Any]:
    """Serializa entrada para contrato JSON sem expor o modelo ORM."""
    pessoas = cache if cache is not None else {}
    pode_validar = autorizacao.permissao_ou_admin(usuario, PERM_ENTRADAS_VALIDAR)
    pode_comp = pode_ver_comprovante_entrada(
        ator_id=ator_id,
        ator_admin=usuario.admin,
        tem_permissao_validar=pode_validar,
        registrada_por_id=entrada.registrada_por_id,
    )
    fatos = autorizacao.fatos_entrada(entrada, ator_id)
    return {
        "id": entrada.id,
        "tipo": entrada.tipo,
        "categoria_id": entrada.categoria_id,
        "categoria_nome": entrada.categoria_nome,
        "saida_id": entrada.saida_id,
        "valor": entrada.valor,
        "data": entrada.data,
        "origem": entrada.origem,
        "evidencia_texto": entrada.evidencia_texto,
        "comprovante_disponivel": bool(entrada.comprovante_chave) and pode_comp,
        "comprovante_nome": entrada.comprovante_nome if pode_comp else "",
        "registrada_por": pessoa_dict(entrada.registrada_por_id, pessoas),
        "situacao": entrada.situacao,
        "decidido_por": (pessoa_dict(entrada.decidido_por_id, pessoas) if entrada.decidido_por_id else None),
        "motivo_texto": entrada.motivo_texto,
        "decisao_texto": entrada.decisao_texto,
        "registrada_em": entrada.registrada_em,
        "decidido_em": entrada.decidido_em,
        "estorno": consulta.serializar_estorno_resumo(entrada, pessoas),
        "acoes": acoes_entrada_disponiveis(fatos),
    }


@transaction.atomic
def registrar(
    ator_id: uuid.UUID,
    *,
    categoria_id: uuid.UUID,
    valor: Dinheiro,
    data: date,
    origem: str,
    evidencia_texto: str = "",
    arquivo: Any = None,
) -> dict[str, Any]:
    """Registra entrada sem devedor em estado EM_VALIDACAO e notifica validadores (CA-42)."""
    usuario = autorizacao.exigir_permissao(ator_id, PERM_ENTRADAS_REGISTRAR)
    categoria = CategoriaFinanceira.objects.filter(pk=categoria_id).first()
    if categoria is None:
        raise erro("NOT_FOUND")
    anexo: AnexoSalvo | None = None
    if arquivo is not None:
        anexo = validar_e_salvar_anexo(arquivo, contexto="entradas")
    entrada = Entrada.registrar(
        categoria=categoria,
        valor=valor,
        data=data,
        origem=origem,
        evidencia_texto=evidencia_texto,
        anexo=anexo,
        registrada_por_id=ator_id,
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
            "origem": entrada.origem,
            "tipo": entrada.tipo,
        },
    )
    avisos.entrada_registrada(entrada)
    return serializar_entrada(entrada, ator_id=ator_id, usuario=usuario)


def _decidir(
    ator_id: uuid.UUID,
    entrada_id: uuid.UUID,
    *,
    comando: ComandoEntrada,
    tipo_decisao: str,
    motivo_id: uuid.UUID,
    texto: str,
    acao_auditoria: str,
) -> dict[str, Any]:
    entrada = Entrada.objects.select_for_update().filter(pk=entrada_id).first()
    if entrada is None:
        autorizacao.exigir_permissao(ator_id, PERM_ENTRADAS_VALIDAR)
        raise erro("NOT_FOUND")
    autorizacao.exigir_comando_entrada(entrada, ator_id, comando)
    motivo_texto = aprovacoes.motivo_aplicado(motivo_id, tipo_decisao)
    agora = timezone.now()
    if comando == ComandoEntrada.VALIDAR:
        entrada.validar(
            por_id=ator_id, motivo_id=motivo_id, motivo_texto=motivo_texto, texto=texto, agora=agora
        )
    else:
        entrada.rejeitar(
            por_id=ator_id, motivo_id=motivo_id, motivo_texto=motivo_texto, texto=texto, agora=agora
        )
    auditoria.registrar(
        ator_id=ator_id,
        acao=acao_auditoria,
        item_tipo="entrada",
        item_id=entrada.id,
        justificativa=texto.strip() or motivo_texto,
        dados={"motivo_id": str(motivo_id), "motivo_texto": motivo_texto},
    )
    avisos.entrada_decidida(entrada)
    usuario = autorizacao.exigir_diretor_ativo(ator_id)
    return serializar_entrada(entrada, ator_id=ator_id, usuario=usuario)


@transaction.atomic
def validar(
    ator_id: uuid.UUID, entrada_id: uuid.UUID, *, motivo_id: uuid.UUID, texto: str = ""
) -> dict[str, Any]:
    """Valida entrada sem devedor em aberto (CA-43)."""
    return _decidir(
        ator_id,
        entrada_id,
        comando=ComandoEntrada.VALIDAR,
        tipo_decisao=tipos.DECISAO_ENTRADA_VALIDAR,
        motivo_id=motivo_id,
        texto=texto,
        acao_auditoria="ENTRADA_VALIDADA",
    )


@transaction.atomic
def rejeitar(
    ator_id: uuid.UUID, entrada_id: uuid.UUID, *, motivo_id: uuid.UUID, texto: str = ""
) -> dict[str, Any]:
    """Rejeita entrada sem devedor em aberto (CA-43)."""
    return _decidir(
        ator_id,
        entrada_id,
        comando=ComandoEntrada.REJEITAR,
        tipo_decisao=tipos.DECISAO_ENTRADA_REJEITAR,
        motivo_id=motivo_id,
        texto=texto,
        acao_auditoria="ENTRADA_REJEITADA",
    )


def listar(
    ator_id: uuid.UUID,
    *,
    situacao: str | None = None,
    categoria_id: uuid.UUID | None = None,
    de: date | None = None,
    ate: date | None = None,
    antes: uuid.UUID | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista entradas com paginação por cursor (leitura de gestão)."""
    usuario = autorizacao.exigir_leitura_gestao(ator_id)
    qs = Entrada.objects.all()
    if situacao:
        qs = qs.filter(situacao=situacao)
    if categoria_id:
        qs = qs.filter(categoria_id=categoria_id)
    if de:
        qs = qs.filter(data__gte=de)
    if ate:
        qs = qs.filter(data__lte=ate)
    if antes is not None:
        ancora = Entrada.objects.filter(pk=antes).values("registrada_em", "id").first()
        if ancora is None:
            raise erro("NOT_FOUND")
        qs = qs.exclude(pk=antes).filter(registrada_em__lte=ancora["registrada_em"])
        qs = qs.exclude(registrada_em=ancora["registrada_em"], id__gte=ancora["id"])
    itens_bd = list(qs[: limite + 1])
    tem_mais = len(itens_bd) > limite
    cache: dict[uuid.UUID, PessoaInfo] = {}
    return {
        "itens": [
            serializar_entrada(e, ator_id=ator_id, usuario=usuario, cache=cache) for e in itens_bd[:limite]
        ],
        "tem_mais": tem_mais,
    }


def resumo(
    ator_id: uuid.UUID,
    *,
    de: date | None = None,
    ate: date | None = None,
    categoria_id: uuid.UUID | None = None,
) -> ResumoEntradasValidadas:
    """Retorna quantidade e total das entradas VALIDADAS para leitura de gestão (CA-44)."""
    autorizacao.exigir_leitura_gestao(ator_id)
    return consulta.resumo_entradas_validadas(de=de, ate=ate, categoria_id=categoria_id)


def detalhe(ator_id: uuid.UUID, entrada_id: uuid.UUID) -> dict[str, Any]:
    usuario = autorizacao.exigir_leitura_gestao(ator_id)
    entrada = Entrada.objects.filter(pk=entrada_id).first()
    if entrada is None:
        raise erro("NOT_FOUND")
    return serializar_entrada(entrada, ator_id=ator_id, usuario=usuario)


def historico(ator_id: uuid.UUID, entrada_id: uuid.UUID) -> list[dict[str, Any]]:
    autorizacao.exigir_leitura_gestao(ator_id)
    if not Entrada.objects.filter(pk=entrada_id).exists():
        raise erro("NOT_FOUND")
    return consulta.serializar_historico(auditoria.historico_do_item("entrada", entrada_id))


def baixar_comprovante(ator_id: uuid.UUID, entrada_id: uuid.UUID) -> HttpResponse:
    """Entrega o comprovante da entrada apenas a registrador, validador e admin (CA-45)."""
    usuario = autorizacao.exigir_diretor_ativo(ator_id)
    pode_validar = autorizacao.permissao_ou_admin(usuario, PERM_ENTRADAS_VALIDAR)
    entrada = Entrada.objects.filter(pk=entrada_id).first()
    if entrada is None:
        if not (usuario.admin or pode_validar):
            raise erro("PERMISSION_DENIED")
        raise erro("NOT_FOUND")
    if not pode_ver_comprovante_entrada(
        ator_id=ator_id,
        ator_admin=usuario.admin,
        tem_permissao_validar=pode_validar,
        registrada_por_id=entrada.registrada_por_id,
    ):
        raise erro("PERMISSION_DENIED")
    if not entrada.comprovante_chave:
        raise erro("NOT_FOUND")
    return resposta_anexo(
        chave=entrada.comprovante_chave,
        nome=entrada.comprovante_nome or "comprovante",
        mime=entrada.comprovante_mime or "application/octet-stream",
    )
