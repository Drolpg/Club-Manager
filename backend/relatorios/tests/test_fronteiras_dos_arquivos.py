"""CA-26 nos arquivos: a ReportLab fica nos escritores, o domínio não a conhece, e a tarefa só chama serviços
de `relatorios` (ADR-006, ADR-019).
"""

import grimp
import pytest


@pytest.fixture(scope="module")
def grafo() -> grimp.ImportGraph:
    return grimp.build_graph("relatorios", include_external_packages=True)


def _modulos(grafo: grimp.ImportGraph, pacote: str) -> set[str]:
    return grafo.find_descendants(pacote) | {pacote}


def test_so_os_escritores_importam_a_reportlab(grafo: grimp.ImportGraph) -> None:
    quem_importa = {
        modulo
        for modulo in _modulos(grafo, "relatorios")
        if any(i.split(".")[0] == "reportlab" for i in grafo.find_modules_directly_imported_by(modulo))
    }

    assert quem_importa == {"relatorios.escritores.pdf"}


def test_o_dominio_nao_importa_a_reportlab_nem_os_escritores(grafo: grimp.ImportGraph) -> None:
    for modulo in _modulos(grafo, "relatorios.domain"):
        importados = grafo.find_modules_directly_imported_by(modulo)
        assert not any(i.startswith(("reportlab", "relatorios.escritores")) for i in importados), modulo


def test_a_tarefa_so_chama_servicos_de_relatorios(grafo: grimp.ImportGraph) -> None:
    importados = {
        i for i in grafo.find_modules_directly_imported_by("relatorios.tasks") if i.startswith("relatorios")
    }

    assert importados
    assert all(i.startswith("relatorios.services") for i in importados), importados
