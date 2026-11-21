"""Parte 12: `financeiro.public.cobrancas_do_devedor`, a leitura que alimenta o perfil (CA-02).

Só leitura: não confere quem pergunta (é do serviço de `relatorios`) e nunca devolve comprovante.
"""

import dataclasses
import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext

from financeiro import public
from financeiro.domain.autorizacao import PERM_COBRANCAS_CRIAR
from financeiro.tests.conftest import (
    client,
    conceder_permissoes,
    criar_cobranca,
    garantir_categoria,
    garantir_chave_pix,
    hoje_local,
    novo_diretor,
)
from kernel.errors import BusinessError
from tests.apoio import Situacao, Usuario

pytestmark = pytest.mark.django_db

_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _cenario() -> dict[str, Any]:
    admin = novo_diretor("admin", admin=True)
    c_admin = client(admin)
    emissor = novo_diretor("emissor")
    conceder_permissoes(emissor, PERM_COBRANCAS_CRIAR)
    return {
        "c_emissor": client(emissor),
        "cat_id": garantir_categoria(c_admin),
        "pix_id": garantir_chave_pix(c_admin),
    }


def _cobrar(ctx: dict[str, Any], devedor: Usuario, **extra: Any) -> dict[str, Any]:
    return criar_cobranca(
        ctx["c_emissor"],
        devedor_id=devedor.id,
        categoria_id=ctx["cat_id"],
        chave_pix_id=ctx["pix_id"],
        **extra,
    )


def _pagar(devedor: Usuario, cobranca_id: str) -> None:
    resposta = client(devedor).post(
        f"/api/v1/financeiro/cobrancas/{cobranca_id}/pagamentos/",
        {
            "forma": "COMPROVANTE",
            "data_pagamento": hoje_local().isoformat(),
            "comprovante": SimpleUploadedFile("comp.pdf", _PDF, content_type="application/pdf"),
        },
        format="multipart",
    )
    assert resposta.status_code == 201, resposta.content


def test_so_as_cobrancas_do_devedor_pedido_mais_novas_primeiro() -> None:
    ctx = _cenario()
    ana, bia = novo_diretor("ana"), novo_diretor("bia")
    primeira = _cobrar(ctx, ana, descricao="Primeira")
    _cobrar(ctx, bia, descricao="Da outra pessoa")
    segunda = _cobrar(ctx, ana, descricao="Segunda")

    pagina = public.cobrancas_do_devedor(ana.id)

    assert [c.id for c in pagina.itens] == [uuid.UUID(segunda["id"]), uuid.UUID(primeira["id"])]
    assert pagina.tem_mais is False


def test_cada_cobranca_traz_situacao_valor_vencimento_e_descricao() -> None:
    ctx = _cenario()
    ana = novo_diretor("ana")
    vencimento = hoje_local() + timedelta(days=15)
    _cobrar(ctx, ana, valor="250.50", vencimento=vencimento, descricao="Taxa de novembro")

    (item,) = public.cobrancas_do_devedor(ana.id).itens

    assert item.descricao == "Taxa de novembro"
    assert item.valor == "250.50"
    assert item.vencimento == vencimento
    assert item.situacao == "ABERTA"
    assert item.pagamentos == []


def test_devedor_desativado_ou_sem_cargo_funciona() -> None:
    ctx = _cenario()
    desativado = novo_diretor("saiu")
    sem_cargo = novo_diretor("semcargo")
    _cobrar(ctx, desativado)
    _cobrar(ctx, sem_cargo)
    Usuario.objects.filter(pk=desativado.pk).update(situacao=Situacao.INATIVO)

    assert len(public.cobrancas_do_devedor(desativado.id).itens) == 1
    assert len(public.cobrancas_do_devedor(sem_cargo.id).itens) == 1


def test_usuario_sem_cobranca_devolve_pagina_vazia() -> None:
    pagina = public.cobrancas_do_devedor(uuid.uuid4())

    assert pagina.itens == []
    assert pagina.tem_mais is False


def test_os_pagamentos_vem_sem_comprovante() -> None:
    ctx = _cenario()
    ana = novo_diretor("ana")
    cobranca = _cobrar(ctx, ana)
    _pagar(ana, cobranca["id"])

    (item,) = public.cobrancas_do_devedor(ana.id).itens

    assert item.situacao == "EM_VALIDACAO"
    (pagamento,) = item.pagamentos
    assert pagamento.forma == "COMPROVANTE"
    assert pagamento.data_pagamento == hoje_local()
    assert pagamento.situacao == "EM_VALIDACAO"
    campos = {c.name for c in dataclasses.fields(pagamento)}
    assert campos == {"forma", "data_pagamento", "situacao"}
    assert "comp.pdf" not in str(item)
    assert "comprovante" not in str(item).lower().replace("forma='comprovante'", "")


def test_paginacao_por_antes_com_tem_mais() -> None:
    ctx = _cenario()
    ana = novo_diretor("ana")
    criadas = [_cobrar(ctx, ana, descricao=f"Cobrança {n}") for n in range(5)]
    ids = [uuid.UUID(c["id"]) for c in reversed(criadas)]

    primeira = public.cobrancas_do_devedor(ana.id, limite=2)
    segunda = public.cobrancas_do_devedor(ana.id, antes=primeira.itens[-1].id, limite=2)
    terceira = public.cobrancas_do_devedor(ana.id, antes=segunda.itens[-1].id, limite=2)

    assert [c.id for c in primeira.itens] == ids[:2]
    assert primeira.tem_mais is True
    assert [c.id for c in segunda.itens] == ids[2:4]
    assert segunda.tem_mais is True
    assert [c.id for c in terceira.itens] == ids[4:]
    assert terceira.tem_mais is False


def test_cursor_inexistente_e_not_found() -> None:
    ana = novo_diretor("ana")

    with pytest.raises(BusinessError) as falha:
        public.cobrancas_do_devedor(ana.id, antes=uuid.uuid4())

    assert falha.value.code == "NOT_FOUND"


def test_o_numero_de_consultas_nao_cresce_com_os_pagamentos() -> None:
    ctx = _cenario()
    ana = novo_diretor("ana")
    for n in range(4):
        _pagar(ana, _cobrar(ctx, ana, descricao=f"C{n}")["id"])

    with CaptureQueriesContext(connection) as com_quatro:
        public.cobrancas_do_devedor(ana.id, limite=4)
    with CaptureQueriesContext(connection) as com_uma:
        public.cobrancas_do_devedor(ana.id, limite=1)

    assert len(com_quatro) == len(com_uma)


def test_minhas_cobrancas_nao_mudou() -> None:
    ctx = _cenario()
    ana = novo_diretor("ana")
    conceder_permissoes(ana)
    cobranca = _cobrar(ctx, ana)

    resposta = client(ana).get("/api/v1/financeiro/minhas-cobrancas/")

    assert resposta.status_code == 200
    assert [c["id"] for c in resposta.json()["itens"]] == [cobranca["id"]]
