"""Helpers locais para a suíte HTTP do módulo financeiro."""

import uuid
from datetime import date, timedelta
from typing import Any

from rest_framework.test import APIClient

from tests.apoio import (
    Situacao,
    Usuario,
    cliente_de,
    conceder,
    criar_admin,
    criar_diretor,
    dar_cargo,
)

BASE_FIN = "/api/v1/financeiro/"
BASE_APROV = "/api/v1/aprovacoes/"

hoje_local = date.today


def erro(resposta: Any) -> tuple[int, str]:
    return resposta.status_code, resposta.json()["error"]["code"]


def novo_diretor(
    prefixo: str,
    *,
    admin: bool = False,
    situacao: Situacao = Situacao.ATIVO,
) -> Usuario:
    sufixo = uuid.uuid4().hex[:8]
    ident = f"{prefixo}_{sufixo}"[:20]
    if admin:
        return criar_admin(ident)
    return criar_diretor(ident, situacao)


def conceder_permissoes(usuario: Usuario, *codigos: str) -> None:
    """Garante cargo ativo ao diretor e concede cada permissão informada."""
    dar_cargo(usuario)
    for codigo in codigos:
        conceder(usuario, codigo)


def garantir_categoria(
    client_admin: APIClient,
    *,
    nome: str | None = None,
    natureza: str = "ENTRADA",
) -> str:
    nome_cat = nome or f"Categoria {uuid.uuid4().hex[:6]}"
    resp = client_admin.post(
        f"{BASE_FIN}categorias/",
        {"nome": nome_cat, "natureza": natureza},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    return str(resp.json()["id"])


def garantir_chave_pix(client_admin: APIClient, *, padrao: bool = True) -> str:
    chave = f"{uuid.uuid4().hex[:10]}@clube.local"
    resp = client_admin.post(
        f"{BASE_FIN}chaves-pix/",
        {
            "tipo": "EMAIL",
            "chave": chave,
            "nome_recebedor": "Clube Teste",
            "cidade": "Curitiba",
            "padrao": padrao,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    return str(resp.json()["id"])


def garantir_motivo(client_admin: APIClient, tipo_de_decisao: str, texto: str | None = None) -> str:
    resp = client_admin.post(
        f"{BASE_APROV}motivos/",
        {"tipo_de_decisao": tipo_de_decisao, "texto": texto or f"Motivo {uuid.uuid4().hex[:6]}"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    return str(resp.json()["id"])


def criar_cobranca(
    client_emissor: APIClient,
    *,
    devedor_id: uuid.UUID,
    categoria_id: str,
    chave_pix_id: str | None = None,
    valor: str = "150.00",
    vencimento: date | None = None,
    limite_de_inadimplencia: int = 30,
    descricao: str = "Mensalidade teste",
) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "devedor_id": str(devedor_id),
        "categoria_id": categoria_id,
        "descricao": descricao,
        "valor": valor,
        "vencimento": (vencimento or (hoje_local() + timedelta(days=10))).isoformat(),
        "limite_de_inadimplencia": limite_de_inadimplencia,
    }
    if chave_pix_id is not None:
        corpo["chave_pix_id"] = chave_pix_id
    resp = client_emissor.post(f"{BASE_FIN}cobrancas/", corpo, format="json")
    assert resp.status_code == 201, resp.content
    dados: dict[str, Any] = resp.json()
    return dados


def client(usuario: Usuario) -> APIClient:
    return cliente_de(usuario)


def notificacoes_do(client_usuario: APIClient) -> list[dict[str, Any]]:
    resp = client_usuario.get("/api/v1/notificacoes/")
    assert resp.status_code == 200, resp.content
    itens: list[dict[str, Any]] = resp.json()["itens"]
    return itens
