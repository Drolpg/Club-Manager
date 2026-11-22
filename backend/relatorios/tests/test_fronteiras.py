"""CA-08: `relatorios` usa os módulos donos só pela API pública, e nenhum módulo de baixo o conhece.

O import-linter (`uv run poe imports`) já proíbe a direção contrária pelo contrato de camadas; aqui as duas
direções ficam ditas por nome. O domínio puro não importa framework.
"""

import grimp
import pytest

# O dashboard do M10 passou a ler também `aprovacoes` e `comunicacao`, só pela API pública (técnica de
# `relatorios/dashboard-e-lancamentos`; ajuste autorizado pelo dono em 2026-11-22).
_USADOS = (
    "acesso",
    "aprovacoes",
    "auditoria",
    "comunicacao",
    "eventos",
    "financeiro",
    "notificacoes",
    "permissoes",
)
_NAO_USADOS = ("marca",)
_FRAMEWORKS = ("django", "rest_framework", "celery")
_TODOS = ("relatorios", *_USADOS, *_NAO_USADOS)


@pytest.fixture(scope="module")
def grafo() -> grimp.ImportGraph:
    return grimp.build_graph(*_TODOS, include_external_packages=True)


def _importados_por(grafo: grimp.ImportGraph, pacote: str) -> set[str]:
    return {
        importado
        for interno in grafo.find_descendants(pacote) | {pacote}
        for importado in grafo.find_modules_directly_imported_by(interno)
    }


def test_relatorios_importa_dos_outros_so_a_api_publica(grafo: grimp.ImportGraph) -> None:
    importados = {i for i in _importados_por(grafo, "relatorios") if i.split(".")[0] in _TODOS[1:]}

    assert importados == {f"{modulo}.public" for modulo in _USADOS}


@pytest.mark.parametrize("modulo", _NAO_USADOS)
def test_relatorios_nao_importa_o_que_nao_usa(grafo: grimp.ImportGraph, modulo: str) -> None:
    importados = {i for i in _importados_por(grafo, "relatorios") if i.split(".")[0] == modulo}

    assert importados == set()


@pytest.mark.parametrize("modulo", [*_USADOS, *_NAO_USADOS])
def test_nenhum_outro_modulo_conhece_relatorios(grafo: grimp.ImportGraph, modulo: str) -> None:
    for interno in grafo.find_descendants(modulo) | {modulo}:
        importados = grafo.find_modules_directly_imported_by(interno)
        assert not any(importado.split(".")[0] == "relatorios" for importado in importados), interno


def test_o_dominio_de_relatorios_nao_importa_framework(grafo: grimp.ImportGraph) -> None:
    dominio = "relatorios.domain"
    modulos = grafo.find_descendants(dominio) | {dominio}
    assert len(modulos) > 1

    for interno in modulos:
        importados = grafo.find_modules_directly_imported_by(interno)
        assert not any(importado.split(".")[0] in _FRAMEWORKS for importado in importados), interno
