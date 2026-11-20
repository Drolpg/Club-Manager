"""Casos de uso de cotações e solicitações estruturadas de gasto (`financeiro.gasto`)."""

import uuid
from typing import Any

from django.db import transaction
from django.http import HttpResponse

from acesso import public as acesso
from aprovacoes import public as aprovacoes
from auditoria import public as auditoria
from financeiro.domain.autorizacao import PERM_GASTOS_APROVAR, pode_ver_anexos_saida
from financeiro.domain.saidas import ErroDeRegraSaida, ItemDeGastoNormalizado, validar_itens_de_gasto
from financeiro.domain.transicoes import SituacaoSaida
from financeiro.erros import erro
from financeiro.models import CategoriaFinanceira, Cotacao, NaturezaCategoria, Saida
from financeiro.services import autorizacao
from kernel.anexos import resposta_anexo, validar_e_salvar_anexo
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError
from permissoes import public as permissoes

TIPO_GASTO = "financeiro.gasto"
MAX_DESCRICAO_GASTO = 200


def _erro_campos(erros: dict[str, list[str]]) -> BusinessError:
    return BusinessError("VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details=erros)


def _parse_uuid(valor: Any, campo: str, erros: dict[str, list[str]]) -> uuid.UUID | None:
    try:
        return valor if isinstance(valor, uuid.UUID) else uuid.UUID(str(valor))
    except TypeError, ValueError:
        erros.setdefault(campo, []).append("Identificador inválido.")
        return None


@transaction.atomic
def upload_cotacao(ator_id: uuid.UUID, arquivo: Any) -> Cotacao:
    """Grava cotação imutável em disco para reutilizar em solicitação de gasto (CA-04)."""
    autorizacao.exigir_leitura_gestao(ator_id)
    anexo = validar_e_salvar_anexo(arquivo, contexto="cotacoes")
    cotacao = Cotacao.objects.create(
        enviada_por_id=ator_id,
        chave=anexo.chave,
        nome=anexo.nome,
        mime=anexo.mime,
        tamanho=anexo.tamanho,
    )
    auditoria.registrar(
        ator_id=ator_id,
        acao="COTACAO_ENVIADA",
        item_tipo="cotacao",
        item_id=cotacao.id,
        dados={"nome": cotacao.nome, "tamanho": cotacao.tamanho},
    )
    return cotacao


def baixar_cotacao(ator_id: uuid.UUID, cotacao_id: uuid.UUID) -> HttpResponse:
    """Entrega o arquivo de cotação para qualquer usuário com leitura de gestão (P6)."""
    usuario = autorizacao.exigir_leitura_gestao(ator_id)
    if not pode_ver_anexos_saida(ator_le_gestao=permissoes.le_gestao(ator_id), ator_admin=usuario.admin):
        raise erro("PERMISSION_DENIED")
    cotacao = Cotacao.objects.filter(pk=cotacao_id).first()
    if cotacao is None:
        raise erro("NOT_FOUND")
    return resposta_anexo(chave=cotacao.chave, nome=cotacao.nome, mime=cotacao.mime)


def preparar_solicitacao_de_gasto(
    conteudo: dict[str, Any], solicitante_id: uuid.UUID
) -> aprovacoes.ConteudoPreparado:
    """Valida itens, categoria de saída, setor ativo, cotação opcional e vínculo de complemento (CA-01/02)."""
    erros: dict[str, list[str]] = {}

    desc_bruta = conteudo.get("descricao")
    desc_limpa = desc_bruta.strip() if isinstance(desc_bruta, str) else ""
    if not desc_limpa:
        erros.setdefault("descricao", []).append("Informe a descrição do gasto.")
    elif len(desc_limpa) > MAX_DESCRICAO_GASTO:
        erros.setdefault("descricao", []).append(f"Use no máximo {MAX_DESCRICAO_GASTO} caracteres.")

    cat_id = _parse_uuid(conteudo.get("categoria_id"), "categoria_id", erros)
    categoria: CategoriaFinanceira | None = None
    if cat_id is not None:
        categoria = CategoriaFinanceira.objects.filter(pk=cat_id).first()
        if categoria is None:
            erros.setdefault("categoria_id", []).append("Categoria financeira não encontrada.")
        elif not categoria.ativa or categoria.natureza != NaturezaCategoria.SAIDA:
            erros.setdefault("categoria_id", []).append("Escolha uma categoria de saída ativa.")

    setor_id = _parse_uuid(conteudo.get("setor_id"), "setor_id", erros)
    setor = permissoes.setor_por_id(setor_id) if setor_id is not None else None
    if setor_id is not None and (setor is None or not setor.ativo):
        erros.setdefault("setor_id", []).append("Escolha um setor ativo.")

    itens_norm: list[ItemDeGastoNormalizado] = []
    total = None
    bruto_itens = conteudo.get("itens")
    if not isinstance(bruto_itens, list):
        erros.setdefault("itens", []).append("Informe a lista de itens do gasto.")
    else:
        try:
            itens_norm, total_dec = validar_itens_de_gasto(bruto_itens)
            total = Dinheiro(total_dec)
        except ErroDeRegraSaida as exc:
            erros.setdefault(exc.campo or "itens", []).append(exc.mensagem)

    cotacao: Cotacao | None = None
    cot_raw = conteudo.get("cotacao_id")
    if cot_raw not in (None, ""):
        cot_id = _parse_uuid(cot_raw, "cotacao_id", erros)
        if cot_id is not None:
            cotacao = Cotacao.objects.filter(pk=cot_id).first()
            if cotacao is None:
                erros.setdefault("cotacao_id", []).append("Cotação não encontrada.")

    if conteudo.get("evento_id") not in (None, ""):
        # O vínculo com o evento é o registro `OrcamentoDeEvento`, nunca o conteúdo (adendo 1).
        erros.setdefault("evento_id", []).append("O orçamento de evento é aberto pelo evento.")

    saida_origem_id: uuid.UUID | None = None
    origem_raw = conteudo.get("saida_origem_id")
    if origem_raw not in (None, ""):
        origem_uuid = _parse_uuid(origem_raw, "saida_origem_id", erros)
        if origem_uuid is not None:
            saida_origem = Saida.objects.filter(pk=origem_uuid).first()
            if saida_origem is None:
                erros.setdefault("saida_origem_id", []).append("Saída de origem não encontrada.")
            else:
                if saida_origem.solicitante_id != solicitante_id:
                    raise erro("SO_O_SOLICITANTE")
                if saida_origem.situacao != SituacaoSaida.EM_CONFERENCIA.value:
                    raise erro("NAO_ESTA_EM_CONFERENCIA")
                prestacao = saida_origem.prestacao_vigente()
                if prestacao is None or prestacao.valor <= saida_origem.total_enviado():
                    raise erro("NAO_HA_EXCESSO_PARA_COMPLEMENTO")
                saida_origem_id = saida_origem.id

    if erros or categoria is None or setor is None or total is None:
        raise _erro_campos(erros)

    return aprovacoes.ConteudoPreparado(
        conteudo={
            "descricao": desc_limpa,
            "categoria_id": str(categoria.id),
            "categoria_nome": categoria.nome,
            "setor_id": str(setor.id),
            "setor_nome": setor.nome,
            "itens": [{"descricao": item.descricao, "valor": str(item.valor)} for item in itens_norm],
            "cotacao_id": str(cotacao.id) if cotacao else None,
            "cotacao_nome": cotacao.nome if cotacao else "",
            "saida_origem_id": str(saida_origem_id) if saida_origem_id else None,
        },
        valor=total,
        resumo=desc_limpa,
    )


@transaction.atomic
def abrir_solicitacao(
    ator_id: uuid.UUID,
    *,
    descricao: str,
    categoria_id: uuid.UUID,
    setor_id: uuid.UUID,
    itens: list[dict[str, Any]],
    cotacao_id: uuid.UUID | None = None,
    aprovador_indicado_id: uuid.UUID | None = None,
) -> aprovacoes.SolicitacaoInfo:
    """Abre solicitação estruturada de gasto no motor de aprovações (RF-073, CA-01)."""
    autorizacao.exigir_leitura_gestao(ator_id)
    solicitacao_id = aprovacoes.enviar(
        tipo=TIPO_GASTO,
        conteudo={
            "descricao": descricao,
            "categoria_id": str(categoria_id),
            "setor_id": str(setor_id),
            "itens": itens,
            "cotacao_id": str(cotacao_id) if cotacao_id else None,
        },
        solicitante_id=ator_id,
        aprovador_indicado_id=aprovador_indicado_id,
    )
    return aprovacoes.obter_solicitacao(solicitacao_id)


def _pessoas_por_ids(ids: set[uuid.UUID]) -> list[dict[str, Any]]:
    lista: list[dict[str, Any]] = []
    for uid in ids:
        usuario = acesso.usuario_por_id(uid)
        if usuario is not None and usuario.ativo:
            lista.append({"id": usuario.id, "nome": usuario.nome})
    return sorted(lista, key=lambda item: str(item["nome"]).lower())


def referencias(ator_id: uuid.UUID) -> dict[str, Any]:
    """Listas de categorias, setores, aprovadores e diretores para preencher telas de gasto."""
    autorizacao.exigir_leitura_gestao(ator_id)
    categorias_saida = [
        {"id": c.id, "nome": c.nome}
        for c in CategoriaFinanceira.objects.filter(natureza=NaturezaCategoria.SAIDA, ativa=True).order_by(
            "nome"
        )
    ]
    categorias_entrada = [
        {"id": c.id, "nome": c.nome}
        for c in CategoriaFinanceira.objects.filter(natureza=NaturezaCategoria.ENTRADA, ativa=True).order_by(
            "nome"
        )
    ]
    setores = [{"id": s.id, "nome": s.nome} for s in permissoes.listar_setores_ativos()]
    aprovadores_ids = set(permissoes.quem_pode(PERM_GASTOS_APROVAR))
    diretores_ids = set(permissoes.usuarios_ativos_com_cargo()) | {a.id for a in acesso.admins_ativos()}
    return {
        "categorias_saida": categorias_saida,
        "categorias_entrada": categorias_entrada,
        "setores": setores,
        "aprovadores_gastos": _pessoas_por_ids(aprovadores_ids),
        "diretores_ativos": _pessoas_por_ids(diretores_ids),
    }
