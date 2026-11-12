"""Regras de fronteira do monólito modular (ADR-001, ADR-003).

A direção das dependências entre módulos é verificada pelo import-linter
(`lint-imports`, contrato em pyproject.toml). Aqui ficam as duas regras que
ele não expressa de forma genérica:

1. um módulo só importa `<outro>.public` de outro módulo;
2. os pacotes `<modulo>.domain` não importam framework.
"""

import grimp
import pytest

MODULES = (
    "auditoria",
    "acesso",
    "permissoes",
    "notificacoes",
    "marca",
    "aprovacoes",
    "comunicacao",
    "financeiro",
    "eventos",
    "relatorios",
)
FRAMEWORKS = ("django", "rest_framework", "celery", "drf_spectacular")


@pytest.fixture(scope="module")
def graph() -> grimp.ImportGraph:
    return grimp.build_graph(*MODULES, "kernel", "config", include_external_packages=True)


def _owner(module: str) -> str:
    return module.split(".")[0]


def test_todo_modulo_tem_api_publica(graph: grimp.ImportGraph) -> None:
    faltando = [m for m in MODULES if f"{m}.public" not in graph.modules]

    assert faltando == []


def test_modulo_so_importa_a_api_publica_de_outro_modulo(graph: grimp.ImportGraph) -> None:
    violacoes = []
    for module in MODULES:
        internos = graph.find_descendants(module) | {module}
        for importado in internos:
            if importado in (module, f"{module}.public"):
                continue
            for importador in graph.find_modules_that_directly_import(importado):
                if _owner(importador) in MODULES and _owner(importador) != module:
                    violacoes.append(f"{importador} -> {importado}")

    assert violacoes == [], "Importe só <modulo>.public de outro módulo"


def test_pacotes_de_dominio_nao_importam_framework(graph: grimp.ImportGraph) -> None:
    violacoes = []
    for module in MODULES:
        dominio = f"{module}.domain"
        if dominio not in graph.modules:
            continue
        for interno in graph.find_descendants(dominio) | {dominio}:
            for importado in graph.find_modules_directly_imported_by(interno):
                if _owner(importado) in FRAMEWORKS:
                    violacoes.append(f"{interno} -> {importado}")

    assert violacoes == [], "Funções de decisão não importam framework"


def test_kernel_nao_conhece_os_modulos(graph: grimp.ImportGraph) -> None:
    violacoes = [
        f"{interno} -> {importado}"
        for interno in graph.find_descendants("kernel") | {"kernel"}
        for importado in graph.find_modules_directly_imported_by(interno)
        if _owner(importado) in MODULES
    ]

    assert violacoes == []
