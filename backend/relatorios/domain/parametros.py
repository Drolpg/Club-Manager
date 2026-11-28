"""Validação dos parâmetros dos relatórios, pura (CA-03): o pedido inválido não entra na fila.

O período é um mês (`AAAA-MM`) ou um intervalo `de` e `ate` (datas ISO); a saída é sempre `de` e `ate` em ISO,
para o pedido guardar parâmetros já normalizados.
"""

import calendar
import re
from collections.abc import Mapping
from datetime import date
from typing import Any

_MES = re.compile(r"(\d{4})-(\d{2})")


class ParametroInvalido(ValueError):
    def __init__(self, campo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.campo = campo
        self.mensagem = mensagem


def _data(campo: str, valor: Any) -> date:
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ParametroInvalido(campo, "Use uma data no formato AAAA-MM-DD.") from None


def _mes(valor: Any, hoje: date) -> tuple[date, date]:
    encontrado = _MES.fullmatch(str(valor))
    if encontrado is None or not 1 <= int(encontrado.group(2)) <= 12:
        raise ParametroInvalido("mes", "Use um mês no formato AAAA-MM.")
    ano, mes = int(encontrado.group(1)), int(encontrado.group(2))
    inicio = date(ano, mes, 1)
    if inicio > hoje:
        raise ParametroInvalido("mes", "Escolha o mês corrente ou um anterior.")
    return inicio, date(ano, mes, calendar.monthrange(ano, mes)[1])


def _sobras(parametros: Mapping[str, Any], aceitos: set[str]) -> None:
    desconhecidas = sorted(set(parametros) - aceitos)
    if desconhecidas:
        raise ParametroInvalido(desconhecidas[0], "Parâmetro desconhecido para este relatório.")


def periodo(parametros: Mapping[str, Any], hoje: date) -> dict[str, str]:
    """Um mês, ou `de` e `ate`. Início depois do fim, ou depois de hoje, é recusado."""
    if "mes" in parametros:
        _sobras(parametros, {"mes"})
        inicio, fim = _mes(parametros["mes"], hoje)
        return {"de": inicio.isoformat(), "ate": fim.isoformat()}
    _sobras(parametros, {"de", "ate"})
    if "de" not in parametros or "ate" not in parametros:
        raise ParametroInvalido("de", "Informe o mês (AAAA-MM) ou o período, com início e fim.")
    inicio, fim = _data("de", parametros["de"]), _data("ate", parametros["ate"])
    if inicio > fim:
        raise ParametroInvalido("ate", "O fim do período vem antes do início.")
    if inicio > hoje:
        raise ParametroInvalido("de", "O período começa depois de hoje.")
    return {"de": inicio.isoformat(), "ate": fim.isoformat()}


def nenhum(parametros: Mapping[str, Any], hoje: date) -> dict[str, str]:
    """Para os relatórios sem parâmetros (inadimplência, meus dados)."""
    _sobras(parametros, set())
    return {}


def periodo_com_pendentes(parametros: Mapping[str, Any], hoje: date) -> dict[str, Any]:
    """O período e a opção "só pendentes" (sim ou não), para a prestação de contas."""
    resto = {chave: valor for chave, valor in parametros.items() if chave != "so_pendentes"}
    so_pendentes = parametros.get("so_pendentes", False)
    if not isinstance(so_pendentes, bool):
        raise ParametroInvalido("so_pendentes", "Use verdadeiro ou falso.")
    return {**periodo(resto, hoje), "so_pendentes": so_pendentes}


def meses(parametros: Mapping[str, Any], hoje: date) -> dict[str, str]:
    """Um intervalo de meses, `de` e `ate` em `AAAA-MM`: do primeiro dia de `de` ao último de `ate`.

    O começo não pode ser depois do mês corrente; o fim pode, porque o previsto inclui vencimentos futuros.
    """
    _sobras(parametros, {"de", "ate"})
    if "de" not in parametros or "ate" not in parametros:
        raise ParametroInvalido("de", "Informe o mês de início e o de fim (AAAA-MM).")
    inicio = _mes_qualquer("de", parametros["de"])
    fim_inicio = _mes_qualquer("ate", parametros["ate"])
    if fim_inicio < inicio:
        raise ParametroInvalido("ate", "O mês de fim vem antes do de início.")
    if inicio > hoje.replace(day=1):
        raise ParametroInvalido("de", "Escolha o mês corrente ou um anterior para começar.")
    fim = date(fim_inicio.year, fim_inicio.month, calendar.monthrange(fim_inicio.year, fim_inicio.month)[1])
    return {"de": inicio.isoformat(), "ate": fim.isoformat()}


def _mes_qualquer(campo: str, valor: Any) -> date:
    encontrado = _MES.fullmatch(str(valor))
    if encontrado is None or not 1 <= int(encontrado.group(2)) <= 12:
        raise ParametroInvalido(campo, "Use um mês no formato AAAA-MM.")
    return date(int(encontrado.group(1)), int(encontrado.group(2)), 1)
