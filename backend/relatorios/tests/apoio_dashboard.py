"""Montagem de lançamentos pela API HTTP, para os testes do dashboard (M10).

`relatorios` não importa os internos dos outros módulos, nem nos testes: os lançamentos são criados pelas
rotas do `financeiro` e das `aprovacoes`, como na tela. O instante da validação ou da liquidação é fixado
trocando `django.utils.timezone.now` só durante a chamada; por isso os clientes são autenticados à força, sem
sessão (a sessão confere o horário).
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

from tests import apoio
from tests.apoio import Usuario

FIN = "/api/v1/financeiro/"
FUSO = ZoneInfo("America/Sao_Paulo")
_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def local(ano: int, mes: int, dia: int, hora: int = 12) -> datetime:
    return datetime(ano, mes, dia, hora, 0, tzinfo=FUSO)


def _pdf() -> SimpleUploadedFile:
    return SimpleUploadedFile("comp.pdf", _PDF, content_type="application/pdf")


@contextmanager
def no_instante(instante: datetime | None) -> Iterator[None]:
    if instante is None:
        yield
        return
    with mock.patch.object(timezone, "now", return_value=instante):
        yield


def diretor(nome: str, *permissoes: str) -> Usuario:
    usuario = apoio.criar_diretor(nome)
    apoio.dar_cargo(usuario)
    for permissao in permissoes:
        apoio.conceder(usuario, permissao)
    return usuario


def cliente(usuario: Usuario) -> APIClient:
    autenticado = APIClient()
    autenticado.force_authenticate(user=usuario)
    return autenticado


def _ok(resposta: Any, status: int = 200) -> Any:
    assert resposta.status_code == status, resposta.content
    return resposta.json()


class Clube:
    """Atores, categorias, chave Pix, setor e motivos; um método por lançamento."""

    def __init__(self) -> None:
        self.admin = apoio.criar_admin("adm.dash")
        self.fin = diretor(
            "fin.dash",
            "cobrancas.criar",
            "entradas.registrar",
            "gastos.aprovar",
            "saidas.enviar",
            "saidas.liquidar",
        )
        self.validador = diretor("val.dash", "pagamentos.validar", "entradas.validar")
        self.solicitante = diretor("sol.dash")
        self.devedor = diretor("dev.dash")
        self._c_admin = cliente(self.admin)
        self._c_fin = cliente(self.fin)
        self._c_val = cliente(self.validador)
        self._c_sol = cliente(self.solicitante)

        refs = _ok(self._c_fin.get(f"{FIN}referencias-gastos/"))
        self.cat_entrada = next(c["id"] for c in refs["categorias_entrada"] if c["nome"] == "Patrocínio")
        self.cat_mensalidade = next(c["id"] for c in refs["categorias_entrada"] if c["nome"] == "Mensalidade")
        self.cat_saida = next(c["id"] for c in refs["categorias_saida"] if c["nome"] == "Arbitragem")
        self.setor = refs["setores"][0]["id"]
        self.pix = _ok(
            self._c_admin.post(
                f"{FIN}chaves-pix/",
                {
                    "tipo": "EMAIL",
                    "chave": f"{uuid.uuid4().hex[:10]}@clube.local",
                    "nome_recebedor": "Clube",
                    "cidade": "Curitiba",
                    "padrao": True,
                },
                format="json",
            ),
            201,
        )["id"]
        self._motivos = {
            tipo: self._motivo(tipo)
            for tipo in ("solicitacao.aprovar", "financeiro.pagamento_validar", "financeiro.entrada_validar")
        }

    def _motivo(self, tipo: str) -> str:
        corpo = {"tipo_de_decisao": tipo, "texto": f"Motivo {uuid.uuid4().hex[:6]}"}
        return str(_ok(self._c_admin.post("/api/v1/aprovacoes/motivos/", corpo, format="json"), 201)["id"])

    def cobranca(
        self, valor: str = "100.00", *, vencimento: date | None = None, devedor: Usuario | None = None
    ) -> str:
        corpo = {
            "devedor_id": str((devedor or self.devedor).id),
            "categoria_id": self.cat_mensalidade,
            "descricao": "Mensalidade",
            "valor": valor,
            "vencimento": (vencimento or timezone.localdate() + timedelta(days=10)).isoformat(),
            "limite_de_inadimplencia": 30,
            "chave_pix_id": self.pix,
        }
        return str(_ok(self._c_fin.post(f"{FIN}cobrancas/", corpo, format="json"), 201)["id"])

    def registrar_pagamento(self, cobranca_id: str, *, devedor: Usuario | None = None) -> None:
        corpo = {
            "forma": "COMPROVANTE",
            "data_pagamento": timezone.localdate().isoformat(),
            "comprovante": _pdf(),
        }
        do_devedor = cliente(devedor or self.devedor)
        _ok(do_devedor.post(f"{FIN}cobrancas/{cobranca_id}/pagamentos/", corpo, format="multipart"), 201)

    def cobranca_paga(self, valor: str = "100.00", *, validada_em: datetime | None = None) -> str:
        cobranca_id = self.cobranca(valor)
        self.registrar_pagamento(cobranca_id)
        corpo = {"motivo_id": self._motivos["financeiro.pagamento_validar"]}
        with no_instante(validada_em):
            _ok(self._c_val.post(f"{FIN}cobrancas/{cobranca_id}/validar-pagamento/", corpo, format="json"))
        return cobranca_id

    def entrada_validada(self, valor: str = "1000.00", *, validada_em: datetime | None = None) -> str:
        corpo = {
            "categoria_id": self.cat_entrada,
            "valor": valor,
            "data": timezone.localdate().isoformat(),
            "origem": "Patrocinador",
            "evidencia_texto": "TED",
        }
        entrada_id = str(_ok(self._c_fin.post(f"{FIN}entradas/", corpo, format="json"), 201)["id"])
        decisao = {"motivo_id": self._motivos["financeiro.entrada_validar"]}
        with no_instante(validada_em):
            _ok(self._c_val.post(f"{FIN}entradas/{entrada_id}/validar/", decisao, format="json"))
        return entrada_id

    def saida(self, valor: str = "300.00") -> str:
        corpo = {
            "descricao": "Arbitragem",
            "categoria_id": self.cat_saida,
            "setor_id": self.setor,
            "itens": [{"descricao": "Arbitragem", "valor": valor}],
        }
        solicitacao = _ok(self._c_sol.post(f"{FIN}gastos/", corpo, format="json"), 201)["id"]
        aprovar = {"motivo_id": self._motivos["solicitacao.aprovar"], "texto": "Ok"}
        _ok(
            self._c_fin.post(
                f"/api/v1/aprovacoes/solicitacoes/{solicitacao}/aprovar/", aprovar, format="json"
            )
        )
        saidas = _ok(self._c_fin.get(f"{FIN}saidas/"))["itens"]
        return str(next(s["id"] for s in saidas if s["solicitacao_id"] == solicitacao))

    def enviar(self, saida_id: str, valor: str) -> None:
        corpo = {"valor": valor, "comprovante": _pdf()}
        _ok(self._c_fin.post(f"{FIN}saidas/{saida_id}/envios/", corpo, format="multipart"), 201)

    def saida_liquidada(self, valor: str = "300.00", *, liquidada_em: datetime | None = None) -> str:
        saida_id = self.saida(valor)
        self.enviar(saida_id, valor)
        prestacao = {"valor": valor, "descricao": "Recibo"}
        _ok(self._c_sol.post(f"{FIN}saidas/{saida_id}/prestacoes/", prestacao, format="multipart"), 201)
        with no_instante(liquidada_em):
            _ok(self._c_fin.post(f"{FIN}saidas/{saida_id}/liquidar/", {}, format="json"))
        return saida_id
