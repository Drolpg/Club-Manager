"""CA-30: `comunicacao` usa os módulos de baixo só pela API pública de cada um, e nenhum deles o conhece.

O import-linter (`uv run poe imports`) já proíbe a direção contrária pelo contrato de camadas; aqui as duas
direções ficam ditas por nome, para o critério de aceite ter um teste próprio. O domínio puro não importa
framework.
"""

import grimp
import pytest

_DE_BAIXO = ("permissoes", "notificacoes", "auditoria", "acesso")
_PROIBIDOS = ("aprovacoes", "financeiro", "eventos", "relatorios")
_OUTROS_DA_FAMILIA = ("marca",)
_FRAMEWORKS = ("django", "rest_framework", "celery")
_TODOS = ("comunicacao", *_DE_BAIXO, *_PROIBIDOS, *_OUTROS_DA_FAMILIA)


@pytest.fixture(scope="module")
def grafo() -> grimp.ImportGraph:
    return grimp.build_graph(*_TODOS, include_external_packages=True)


def _importados_por(grafo: grimp.ImportGraph, pacote: str) -> set[str]:
    return {
        importado
        for interno in grafo.find_descendants(pacote) | {pacote}
        for importado in grafo.find_modules_directly_imported_by(interno)
    }


def test_comunicacao_importa_dos_modulos_de_baixo_so_a_api_publica(grafo: grimp.ImportGraph) -> None:
    importados = {i for i in _importados_por(grafo, "comunicacao") if i.split(".")[0] in _DE_BAIXO}

    assert importados == {f"{modulo}.public" for modulo in _DE_BAIXO}


@pytest.mark.parametrize("modulo", [*_PROIBIDOS, *_OUTROS_DA_FAMILIA])
def test_comunicacao_nao_importa_os_contextos_que_nao_sao_de_baixo(
    grafo: grimp.ImportGraph, modulo: str
) -> None:
    importados = {i for i in _importados_por(grafo, "comunicacao") if i.split(".")[0] == modulo}

    assert importados == set()


@pytest.mark.parametrize("modulo", [*_DE_BAIXO, *_PROIBIDOS, *_OUTROS_DA_FAMILIA])
def test_nenhum_outro_modulo_conhece_comunicacao(grafo: grimp.ImportGraph, modulo: str) -> None:
    for interno in grafo.find_descendants(modulo) | {modulo}:
        importados = grafo.find_modules_directly_imported_by(interno)
        assert not any(importado.split(".")[0] == "comunicacao" for importado in importados), interno


def test_o_dominio_de_comunicacao_nao_importa_framework(grafo: grimp.ImportGraph) -> None:
    dominio = "comunicacao.domain"
    modulos = grafo.find_descendants(dominio) | {dominio}
    assert len(modulos) > 1

    for interno in modulos:
        importados = grafo.find_modules_directly_imported_by(interno)
        assert not any(importado.split(".")[0] in _FRAMEWORKS for importado in importados), interno


def test_o_dominio_de_comunicacao_nao_importa_o_resto_do_modulo(grafo: grimp.ImportGraph) -> None:
    dominio = "comunicacao.domain"

    for interno in grafo.find_descendants(dominio) | {dominio}:
        for importado in grafo.find_modules_directly_imported_by(interno):
            assert importado == dominio or importado.startswith(f"{dominio}.") or "." not in importado, (
                interno,
                importado,
            )
