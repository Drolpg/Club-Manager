"""Escritor de CSV (P23): UTF-8 com BOM, `;`, vírgula decimal e datas `dd/mm/aaaa`, como o Excel em português.

Primeiro o cabeçalho e o resumo, em linhas `rótulo;valor`; depois, cada tabela com o título e as colunas,
separada por uma linha em branco. Todo texto passa pelo escape contra injeção de fórmula.
"""

import csv
import io

from relatorios.domain.csv_seguro import escapar_celula, formatar_para_csv
from relatorios.domain.documento import Cabecalho, Documento


def escrever_csv(documento: Documento, cabecalho: Cabecalho) -> bytes:
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(["Relatório", escapar_celula(documento.titulo)])
    escritor.writerow(["Parâmetros", escapar_celula(documento.parametros)])
    escritor.writerow(["Gerado em", cabecalho.gerado_em.strftime("%d/%m/%Y %H:%M")])
    escritor.writerow(["Gerado por", escapar_celula(cabecalho.gerado_por)])
    for item in documento.resumo:
        escritor.writerow([escapar_celula(item.rotulo), formatar_para_csv(item.valor, item.tipo)])
    for tabela in documento.tabelas:
        escritor.writerow([])
        escritor.writerow([escapar_celula(tabela.titulo)])
        escritor.writerow([escapar_celula(coluna.nome) for coluna in tabela.colunas])
        for linha in tabela.linhas:
            escritor.writerow(
                [
                    formatar_para_csv(valor, coluna.tipo)
                    for valor, coluna in zip(linha, tabela.colunas, strict=True)
                ]
            )
    return saida.getvalue().encode("utf-8-sig")
