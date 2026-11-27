"""O que os relatórios do clube têm em comum: o período dos parâmetros, o texto dos parâmetros e os nomes
legíveis das situações. Os números vêm sempre das consultas públicas dos módulos donos.
"""

import uuid
from datetime import date, timedelta
from typing import Any

from acesso import public as acesso
from financeiro import public as financeiro
from permissoes import public as permissoes
from relatorios.domain.documento import ItemDoResumo, TipoDeColuna

DE_ATE = "De {de} a {ate}"


def periodo(parametros: dict[str, Any]) -> tuple[date, date]:
    return date.fromisoformat(parametros["de"]), date.fromisoformat(parametros["ate"])


def data(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def texto_do_periodo(de: date, ate: date) -> str:
    return DE_ATE.format(de=data(de), ate=data(ate))


def vespera(dia: date) -> date:
    return dia - timedelta(days=1)


def le_gestao(usuario_id: uuid.UUID) -> bool:
    """Os seis relatórios do clube: quem lê os dados de gestão (RN-022)."""
    return permissoes.le_gestao(usuario_id)


def ativo(usuario_id: uuid.UUID) -> bool:
    """ "Meus dados": todo usuário ativo."""
    usuario = acesso.usuario_por_id(usuario_id)
    return usuario is not None and usuario.ativo


def legivel(codigo: str, nomes: dict[str, str]) -> str:
    return nomes.get(codigo, codigo.replace("_", " ").capitalize())


SITUACOES_DE_SAIDA = {
    "AGUARDANDO_ENVIO": "Aguardando envio",
    "RECURSO_ENVIADO": "Recurso enviado",
    "EM_CONFERENCIA": "Em conferência",
    "LIQUIDADA": "Liquidada",
    "CANCELADA": "Cancelada",
    "ESTORNADA": "Estornada",
}
SITUACOES_DE_EVENTO = {
    "EM_APROVACAO": "Em aprovação",
    "PUBLICADO": "Publicado",
    "RECUSADO": "Recusado",
    "REALIZADO": "Realizado",
    "CANCELADO": "Cancelado",
}
SITUACOES_DE_COBRANCA = {
    "ABERTA": "Aberta",
    "ATRASADA": "Atrasada",
    "EM_VALIDACAO": "Em validação",
    "PAGA": "Paga",
    "ISENTA": "Isenta",
    "CANCELADA": "Cancelada",
    "PERDOADA": "Perdoada",
    "RENEGOCIADA": "Renegociada",
    "ESTORNADA": "Estornada",
}


def saldos(de: date, ate: date, totais: financeiro.TotaisDoPeriodo) -> tuple[ItemDoResumo, ...]:
    return (
        ItemDoResumo("Saldo no início", financeiro.saldo_acumulado(vespera(de)), TipoDeColuna.DINHEIRO),
        ItemDoResumo("Entradas", totais.entradas, TipoDeColuna.DINHEIRO),
        ItemDoResumo("Saídas", totais.saidas, TipoDeColuna.DINHEIRO),
        ItemDoResumo("Resultado", totais.resultado, TipoDeColuna.DINHEIRO),
        ItemDoResumo("Saldo no fim", financeiro.saldo_acumulado(ate), TipoDeColuna.DINHEIRO),
    )
