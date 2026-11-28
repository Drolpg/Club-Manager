"""Massa fixa para o conteúdo dos relatórios (CA-16 a CA-25), montada pelas rotas, como na tela.

Estende o `Clube` dos testes do dashboard com estorno, cobrança atrasada, convocação, justificativa e
questionamento. A rotina diária do `financeiro` roda pela tarefa registrada no Celery, pelo nome, sem importar
o módulo. Tudo acontece com o relógio fixo em 20/11/2026, para os números não dependerem de hoje.
"""

import re
from contextlib import ExitStack
from datetime import date, datetime
from typing import Any

from celery import current_app as celery

from relatorios.domain.documento import Documento, Tabela
from relatorios.tests.apoio_dashboard import Clube, _ok, cliente, diretor, local, no_instante
from tests.apoio import Usuario

FIN = "/api/v1/financeiro/"
AGORA = local(2026, 11, 20, 10)
HOJE = date(2026, 11, 20)
OUT = {"de": "2026-10-01", "ate": "2026-10-31"}
SEGREDO_DA_JUSTIFICATIVA = "SEGREDO-DA-JUSTIFICATIVA"
SEGREDO_DO_QUESTIONAMENTO = "SEGREDO-DO-QUESTIONAMENTO"


class Massa(Clube):
    """O clube com lançamentos de outubro e novembro de 2026, estorno, inadimplência e prestação pendente."""

    def __init__(self) -> None:
        super().__init__()
        self.estornador = diretor("est.conteudo", "financeiro.estornar")
        self.devedor2 = diretor("dev2.conteudo")
        self._c_est = cliente(self.estornador)
        self._m_estorno = self._motivo("financeiro.estornar")

        self.paga_em_outubro = self.cobranca_paga("100.00", validada_em=local(2026, 10, 5))
        self.patrocinio = self.entrada_validada("1000.00", validada_em=local(2026, 10, 6))
        self.arbitragem = self.saida_liquidada("300.00", liquidada_em=local(2026, 10, 9))
        self.estornar_entrada(self.patrocinio, em=local(2026, 10, 25))
        self.cobranca_paga("7.00", validada_em=local(2026, 11, 2))

        self.atrasada = self._cobranca_antiga("50.00", date(2026, 10, 1), self.devedor)
        self.questionada = self._cobranca_antiga("20.00", date(2026, 10, 2), self.devedor2)
        self.rodar_rotina_do_financeiro(local(2026, 11, 5, 6))
        self._ao_devedor(self.devedor, self.atrasada, "justificar-divida", SEGREDO_DA_JUSTIFICATIVA)
        self._ao_devedor(self.devedor2, self.questionada, "questionar", SEGREDO_DO_QUESTIONAMENTO)

        self.pendente = self.saida("80.00")
        self.enviar(self.pendente, "80.00")

    def _cobranca_antiga(self, valor: str, vencimento: date, devedor: Usuario) -> str:
        """Criada em 20/09/2026, antes do vencimento: a rotina a marca atrasada e, 30 dias depois, convoca."""
        with no_instante(local(2026, 9, 20)):
            return self.cobranca(valor, vencimento=vencimento, devedor=devedor)

    def _ao_devedor(self, devedor: Usuario, cobranca_id: str, acao: str, texto: str) -> None:
        resposta = cliente(devedor).post(
            f"{FIN}cobrancas/{cobranca_id}/{acao}/", {"texto": texto}, format="json"
        )
        assert resposta.status_code in (200, 201), resposta.content

    def estornar_entrada(self, entrada_id: str, *, em: datetime) -> None:
        corpo = {"motivo_id": self._m_estorno, "justificativa": "Lançado em dobro"}
        with no_instante(em):
            _ok(self._c_est.post(f"{FIN}entradas/{entrada_id}/estornar/", corpo, format="json"), 201)

    @staticmethod
    def rodar_rotina_do_financeiro(instante: datetime) -> None:
        celery.loader.import_default_modules()
        with no_instante(instante):
            celery.tasks["financeiro.processar_rotina_diaria"].apply().get()


def relogio_fixo() -> ExitStack:
    pilha = ExitStack()
    pilha.enter_context(no_instante(AGORA))
    return pilha


def resumo(documento: Documento) -> dict[str, Any]:
    return {item.rotulo: item.valor for item in documento.resumo}


def tabela(documento: Documento, titulo: str) -> Tabela:
    return next(t for t in documento.tabelas if t.titulo == titulo)


def coluna(tabela_: Tabela, nome: str) -> list[Any]:
    indice = [c.nome for c in tabela_.colunas].index(nome)
    return [linha[indice] for linha in tabela_.linhas]


def texto_do_pdf(conteudo: bytes) -> str:
    """O texto de um PDF sem compressão, com os escapes octais da ReportLab decodificados."""
    bruto = conteudo.decode("latin-1")
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), bruto)
