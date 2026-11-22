"""Montagem de lançamentos com instante controlado, para os totais do dashboard (M10).

Cada lançamento passa pelos serviços do próprio `financeiro`, como na tela; o instante da validação, da
liquidação ou do estorno é fixado trocando `django.utils.timezone.now` só durante a chamada.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from financeiro import tipos
from financeiro.domain.autorizacao import (
    PERM_COBRANCAS_CANCELAR,
    PERM_COBRANCAS_CRIAR,
    PERM_COBRANCAS_ISENTAR,
    PERM_ENTRADAS_REGISTRAR,
    PERM_ENTRADAS_VALIDAR,
    PERM_FINANCEIRO_ESTORNAR,
    PERM_GASTOS_APROVAR,
    PERM_PAGAMENTOS_VALIDAR,
    PERM_SAIDAS_ENVIAR,
    PERM_SAIDAS_LIQUIDAR,
)
from financeiro.models import CategoriaFinanceira, Cobranca, Entrada, Saida
from financeiro.services import cobrancas, entradas, estornos, gastos, pagamentos, saidas
from financeiro.tests.conftest import conceder_permissoes, garantir_chave_pix, garantir_motivo, novo_diretor
from kernel.dinheiro import Dinheiro
from permissoes import public as permissoes

FUSO = ZoneInfo("America/Sao_Paulo")
_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def local(ano: int, mes: int, dia: int, hora: int = 12, minuto: int = 0) -> datetime:
    """Um instante no fuso do clube."""
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO)


def _pdf() -> SimpleUploadedFile:
    return SimpleUploadedFile("comp.pdf", _PDF, content_type="application/pdf")


@contextmanager
def no_instante(instante: datetime | None) -> Iterator[None]:
    """Faz `timezone.now()` devolver `instante` dentro do bloco; `None` não muda nada."""
    if instante is None:
        yield
        return
    with mock.patch.object(timezone, "now", return_value=instante):
        yield


class Livro:
    """Os atores, as categorias e os motivos de um cenário, e um método por tipo de lançamento."""

    def __init__(self) -> None:
        self.admin = novo_diretor("adm_m10", admin=True)
        self.fin = novo_diretor("fin_m10")
        conceder_permissoes(
            self.fin,
            PERM_COBRANCAS_CRIAR,
            PERM_COBRANCAS_CANCELAR,
            PERM_COBRANCAS_ISENTAR,
            PERM_PAGAMENTOS_VALIDAR,
            PERM_ENTRADAS_REGISTRAR,
            PERM_ENTRADAS_VALIDAR,
            PERM_GASTOS_APROVAR,
            PERM_SAIDAS_ENVIAR,
            PERM_SAIDAS_LIQUIDAR,
        )
        self.validador = novo_diretor("val_m10")
        conceder_permissoes(self.validador, PERM_ENTRADAS_VALIDAR, PERM_PAGAMENTOS_VALIDAR)
        self.estornador = novo_diretor("est_m10")
        conceder_permissoes(self.estornador, PERM_FINANCEIRO_ESTORNAR)
        self.solicitante = novo_diretor("sol_m10")
        conceder_permissoes(self.solicitante)
        self.devedor = novo_diretor("dev_m10")
        conceder_permissoes(self.devedor)

        self.c_admin = APIClient()
        self.c_admin.force_authenticate(user=self.admin)
        self.c_fin = APIClient()
        self.c_fin.force_authenticate(user=self.fin)

        self.cat_entrada = CategoriaFinanceira.objects.get(nome="Patrocínio", natureza="ENTRADA")
        self.cat_mensalidade = CategoriaFinanceira.objects.get(nome="Mensalidade", natureza="ENTRADA")
        self.cat_saida = CategoriaFinanceira.objects.get(nome="Arbitragem", natureza="SAIDA")
        self.setor = permissoes.listar_setores_ativos()[0]
        self.pix_id = uuid.UUID(garantir_chave_pix(self.c_admin, padrao=True))
        self.m_apr = garantir_motivo(self.c_admin, "solicitacao.aprovar")
        self.m_val_e = uuid.UUID(garantir_motivo(self.c_admin, tipos.DECISAO_ENTRADA_VALIDAR))
        self.m_rej_e = uuid.UUID(garantir_motivo(self.c_admin, tipos.DECISAO_ENTRADA_REJEITAR))
        self.m_val_p = uuid.UUID(garantir_motivo(self.c_admin, tipos.DECISAO_PAGAMENTO_VALIDAR))
        self.m_can_c = uuid.UUID(garantir_motivo(self.c_admin, tipos.DECISAO_COBRANCA_CANCELAR))
        self.m_est = uuid.UUID(garantir_motivo(self.c_admin, tipos.DECISAO_ESTORNAR))

    # Cobranças ------------------------------------------------------------------------------------------

    def cobranca(
        self,
        valor: str = "100.00",
        *,
        vencimento: date | None = None,
        devedor: Any = None,
        descricao: str = "Mensalidade",
    ) -> Cobranca:
        return cobrancas.criar_avulsa(
            ator_id=self.fin.id,
            devedor_id=(devedor or self.devedor).id,
            categoria_id=self.cat_mensalidade.id,
            descricao=descricao,
            valor=Dinheiro(valor),
            vencimento=vencimento or (timezone.localdate() + timedelta(days=10)),
            chave_pix_id=self.pix_id,
        )

    def registrar_pagamento(self, cobranca: Cobranca, *, devedor: Any = None) -> Cobranca:
        return pagamentos.registrar(
            (devedor or self.devedor).id,
            cobranca.id,
            forma="COMPROVANTE",
            data_pagamento=timezone.localdate(),
            arquivo=_pdf(),
        )

    def cobranca_paga(
        self, valor: str = "100.00", *, validada_em: datetime | None = None, devedor: Any = None
    ) -> Cobranca:
        cobranca = self.cobranca(valor, devedor=devedor)
        self.registrar_pagamento(cobranca, devedor=devedor)
        with no_instante(validada_em):
            return pagamentos.validar(self.validador.id, cobranca.id, motivo_id=self.m_val_p)

    def isentar(self, cobranca: Cobranca) -> Cobranca:
        return cobrancas.isentar(ator_id=self.fin.id, cobranca_id=cobranca.id, justificativa="Ajuda o clube")

    def cancelar(self, cobranca: Cobranca) -> Cobranca:
        return cobrancas.cancelar(ator_id=self.fin.id, cobranca_id=cobranca.id, motivo_id=self.m_can_c)

    def estornar_cobranca(self, cobranca: Cobranca, *, em: datetime | None = None) -> None:
        with no_instante(em):
            estornos.estornar_cobranca(
                self.estornador.id, cobranca.id, motivo_id=self.m_est, justificativa="Lançado em dobro"
            )

    # Entradas sem devedor ------------------------------------------------------------------------------

    def entrada(self, valor: str = "1000.00", *, origem: str = "Patrocinador") -> Entrada:
        dados = entradas.registrar(
            self.fin.id,
            categoria_id=self.cat_entrada.id,
            valor=Dinheiro(valor),
            data=timezone.localdate(),
            origem=origem,
            evidencia_texto="TED",
        )
        return Entrada.objects.get(pk=dados["id"])

    def entrada_validada(self, valor: str = "1000.00", *, validada_em: datetime | None = None) -> Entrada:
        entrada = self.entrada(valor)
        with no_instante(validada_em):
            entradas.validar(self.validador.id, entrada.id, motivo_id=self.m_val_e)
        entrada.refresh_from_db()
        return entrada

    def entrada_rejeitada(self, valor: str = "1000.00") -> Entrada:
        entrada = self.entrada(valor)
        entradas.rejeitar(self.validador.id, entrada.id, motivo_id=self.m_rej_e)
        entrada.refresh_from_db()
        return entrada

    def estornar_entrada(self, entrada: Entrada, *, em: datetime | None = None) -> None:
        with no_instante(em):
            estornos.estornar_entrada(
                self.estornador.id, entrada.id, motivo_id=self.m_est, justificativa="Lançado em dobro"
            )

    # Saídas --------------------------------------------------------------------------------------------

    def saida(self, aprovado: str = "300.00", *, descricao: str = "Arbitragem") -> Saida:
        sol = gastos.abrir_solicitacao(
            self.solicitante.id,
            descricao=descricao,
            categoria_id=self.cat_saida.id,
            setor_id=self.setor.id,
            itens=[{"descricao": descricao, "valor": aprovado}],
        )
        resp = self.c_fin.post(
            f"/api/v1/aprovacoes/solicitacoes/{sol.id}/aprovar/",
            {"motivo_id": self.m_apr, "texto": "Ok"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        return Saida.objects.get(solicitacao_id=sol.id, situacao="AGUARDANDO_ENVIO")

    def enviar(self, saida: Saida, valor: str) -> None:
        saidas.enviar_recurso(self.fin.id, saida.id, valor=Dinheiro(valor), arquivo=_pdf())

    def prestar(self, saida: Saida, gasto: str) -> None:
        saidas.prestar_contas(self.solicitante.id, saida.id, valor=Dinheiro(gasto), descricao="Recibo")

    def devolver(self, saida: Saida, valor: str, *, validar: bool = True) -> Entrada:
        dados = saidas.devolver_sobra(
            self.solicitante.id, saida.id, valor=Dinheiro(valor), evidencia_texto="Pix"
        )
        devolucao = Entrada.objects.get(pk=dados["id"])
        if validar:
            entradas.validar(self.validador.id, devolucao.id, motivo_id=self.m_val_e)
            devolucao.refresh_from_db()
        return devolucao

    def liquidar(self, saida: Saida, *, em: datetime | None = None, justificativa: str = "") -> Saida:
        with no_instante(em):
            saidas.liquidar(self.fin.id, saida.id, justificativa=justificativa)
        saida.refresh_from_db()
        return saida

    def saida_liquidada(
        self,
        aprovado: str = "300.00",
        *,
        enviado: str | None = None,
        gasto: str | None = None,
        devolvido: str | None = None,
        liquidada_em: datetime | None = None,
    ) -> Saida:
        """Aprova, envia, presta contas, devolve a sobra (se houver) e liquida."""
        saida = self.saida(aprovado)
        valor_enviado = enviado or aprovado
        self.enviar(saida, valor_enviado)
        self.prestar(saida, gasto or valor_enviado)
        if devolvido:
            self.devolver(saida, devolvido)
        justificativa = "Sem reembolso" if gasto and enviado and gasto > enviado else ""
        return self.liquidar(saida, em=liquidada_em, justificativa=justificativa)

    def estornar_saida(self, saida: Saida, *, em: datetime | None = None) -> None:
        with no_instante(em):
            estornos.estornar_saida(
                self.estornador.id, saida.id, motivo_id=self.m_est, justificativa="Lançado em dobro"
            )
