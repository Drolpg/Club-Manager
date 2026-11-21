"""CA-28: `eventos` usa o motor e o financeiro só pela API pública de cada um, e nenhum dos dois o conhece.

O import-linter (`uv run poe imports`) já proíbe a direção contrária pelo contrato de camadas; aqui as duas
direções ficam ditas por nome, para o critério de aceite ter um teste próprio.
"""

import grimp
import pytest

_OUTROS = ("aprovacoes", "financeiro")


@pytest.fixture(scope="module")
def grafo() -> grimp.ImportGraph:
    return grimp.build_graph("eventos", "aprovacoes", "financeiro", include_external_packages=True)


def test_eventos_importa_so_a_api_publica_do_motor_e_do_financeiro(grafo: grimp.ImportGraph) -> None:
    importados = {
        importado
        for interno in grafo.find_descendants("eventos") | {"eventos"}
        for importado in grafo.find_modules_directly_imported_by(interno)
        if importado.split(".")[0] in _OUTROS
    }

    assert importados == {"aprovacoes.public", "financeiro.public"}


@pytest.mark.parametrize("modulo", _OUTROS)
def test_motor_e_financeiro_nao_conhecem_eventos(grafo: grimp.ImportGraph, modulo: str) -> None:
    for interno in grafo.find_descendants(modulo) | {modulo}:
        importados = grafo.find_modules_directly_imported_by(interno)
        assert not any(importado.split(".")[0] == "eventos" for importado in importados), interno
