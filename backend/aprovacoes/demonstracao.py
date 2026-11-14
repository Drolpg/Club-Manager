"""Tipo de demonstração, só para desenvolvimento (adendo 1 da technical-spec).

Com `DEBUG` ligado e `APROVACOES_TIPO_DE_DEMONSTRACAO=1`, o `ready` registra o tipo `demonstracao.pedido` (com
valor) e a permissão `demonstracao.aprovar`. É o que permite percorrer o ciclo no navegador antes de existir
um tipo de verdade (M7). Com `DEBUG` desligado, a variável é ignorada mesmo definida: em produção o tipo não
existe.
"""

import contextlib
import logging
import os
import uuid
from typing import Any

from django.conf import settings

from aprovacoes import tipos
from aprovacoes.tipos import ConteudoPreparado, MudancaDeSolicitacao
from kernel.dinheiro import Dinheiro
from kernel.errors import BusinessError
from permissoes import public as permissoes

VARIAVEL = "APROVACOES_TIPO_DE_DEMONSTRACAO"
TIPO = "demonstracao.pedido"
PERMISSAO = "demonstracao.aprovar"

logger = logging.getLogger(__name__)


def ligado() -> bool:
    valor = os.environ.get(VARIAVEL, "").strip().lower()
    return bool(settings.DEBUG) and valor in ("1", "true", "yes")


def preparar(conteudo: dict[str, Any], solicitante_id: uuid.UUID) -> ConteudoPreparado:
    """Exige uma descrição e um valor maior que zero, como faria um módulo dono."""
    erros: dict[str, list[str]] = {}
    descricao = conteudo.get("descricao")
    if not isinstance(descricao, str) or not descricao.strip():
        erros["descricao"] = ["Informe a descrição."]
    valor: Dinheiro | None = None
    with contextlib.suppress(TypeError, ValueError):
        valor = Dinheiro(str(conteudo.get("valor")))
    if valor is None or valor.quantia <= 0:
        erros["valor"] = ["Informe um valor maior que zero, com até duas casas."]
    if erros or not isinstance(descricao, str) or valor is None:
        raise BusinessError("VALIDATION_ERROR", "Os dados enviados são inválidos.", status=400, details=erros)
    return ConteudoPreparado(
        conteudo={"descricao": descricao.strip(), "valor": str(valor)}, valor=valor, resumo=descricao.strip()
    )


def ao_mudar(mudanca: MudancaDeSolicitacao) -> None:
    # Não há módulo dono de verdade: o aviso só fica no log, com IDs e códigos.
    logger.info(
        "Mudança na solicitação de demonstração",
        extra={"solicitacao_id": str(mudanca.solicitacao_id), "acontecimento": mudanca.acontecimento.value},
    )


def registrar_se_ligado() -> bool:
    """Registra a permissão e o tipo, se a demonstração estiver ligada. Devolve se registrou."""
    if not ligado():
        return False
    permissoes.registrar_permissao(
        PERMISSAO,
        "Aprovar pedidos de demonstração",
        "Só em desenvolvimento: decidir as solicitações do tipo de demonstração.",
    )
    tipos.registrar_tipo(
        codigo=TIPO,
        nome="Pedido de demonstração",
        permissao_de_aprovar=PERMISSAO,
        tem_valor=True,
        preparar=preparar,
        ao_mudar=ao_mudar,
    )
    return True
