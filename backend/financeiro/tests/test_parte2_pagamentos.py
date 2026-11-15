"""Parte 2: Pagamentos, comprovantes privados, recibo PDF e concorrência (CA-11 a CA-20)."""

import threading
from datetime import timedelta
from io import BytesIO
from typing import Any
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from financeiro import tipos
from financeiro.domain.autorizacao import PERM_COBRANCAS_CRIAR, PERM_PAGAMENTOS_VALIDAR
from financeiro.tests.conftest import (
    BASE_FIN,
    client,
    conceder_permissoes,
    criar_cobranca,
    erro,
    garantir_categoria,
    garantir_chave_pix,
    garantir_motivo,
    hoje_local,
    notificacoes_do,
    novo_diretor,
)
from tests.apoio import Situacao, Usuario

pytestmark = pytest.mark.django_db

_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 24
_WEBP_BYTES = b"RIFF\x18\x00\x00\x00WEBP" + b"\x00" * 16


def _upload(nome: str, conteudo: bytes, mime: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, conteudo, content_type=mime)


def _cenario_basico() -> dict[str, Any]:
    admin = novo_diretor("admin", admin=True)
    c_admin = client(admin)
    emissor = novo_diretor("emissor")
    validador = novo_diretor("validador")
    devedor = novo_diretor("devedor")
    outro_cargo = novo_diretor("outro")
    conceder_permissoes(emissor, PERM_COBRANCAS_CRIAR)
    conceder_permissoes(validador, PERM_PAGAMENTOS_VALIDAR)
    conceder_permissoes(outro_cargo)
    cat_id = garantir_categoria(c_admin)
    pix_id = garantir_chave_pix(c_admin, padrao=True)
    m_val = garantir_motivo(c_admin, tipos.DECISAO_PAGAMENTO_VALIDAR, "Conferido no extrato")
    m_rej = garantir_motivo(c_admin, tipos.DECISAO_PAGAMENTO_REJEITAR, "Comprovante ilegível")
    cobranca = criar_cobranca(
        client(emissor),
        devedor_id=devedor.id,
        categoria_id=cat_id,
        chave_pix_id=pix_id,
    )
    return {
        "admin": admin,
        "c_admin": c_admin,
        "emissor": emissor,
        "c_emissor": client(emissor),
        "validador": validador,
        "c_validador": client(validador),
        "devedor": devedor,
        "c_devedor": client(devedor),
        "outro_cargo": outro_cargo,
        "c_outro_cargo": client(outro_cargo),
        "cat_id": cat_id,
        "pix_id": pix_id,
        "m_val": m_val,
        "m_rej": m_rej,
        "cobranca": cobranca,
    }


def _registrar_comprovante(
    c_ator: APIClient,
    cobranca_id: str,
    arquivo: SimpleUploadedFile | None = None,
) -> Any:
    anexo = arquivo or _upload("comp.pdf", _PDF_BYTES, "application/pdf")
    return c_ator.post(
        f"{BASE_FIN}cobrancas/{cobranca_id}/pagamentos/",
        {
            "forma": "COMPROVANTE",
            "data_pagamento": hoje_local().isoformat(),
            "comprovante": anexo,
        },
        format="multipart",
    )


def test_ca11_registrar_pagamento_com_comprovante_e_formatos_permitidos() -> None:
    ctx = _cenario_basico()
    for idx, (nome, dados, mime) in enumerate(
        [
            ("p.pdf", _PDF_BYTES, "application/pdf"),
            ("p.png", _PNG_BYTES, "image/png"),
            ("p.jpg", _JPEG_BYTES, "image/jpeg"),
            ("p.webp", _WEBP_BYTES, "image/webp"),
        ]
    ):
        cob = criar_cobranca(
            ctx["c_emissor"],
            devedor_id=ctx["devedor"].id,
            categoria_id=ctx["cat_id"],
            chave_pix_id=ctx["pix_id"],
            descricao=f"Cobranca {idx}",
        )
        resp = _registrar_comprovante(ctx["c_devedor"], cob["id"], _upload(nome, dados, mime))
        assert resp.status_code == 201, resp.content
        body = resp.json()
        assert body["situacao"] == "EM_VALIDACAO"
        assert len(body["pagamentos"]) == 1
        pag = body["pagamentos"][0]
        assert pag["forma"] == "COMPROVANTE"
        assert pag["comprovante_disponivel"] is True
        assert pag["situacao"] == "EM_VALIDACAO"

    itens_val = notificacoes_do(ctx["c_validador"])
    assert any(n["tipo"] == tipos.NOTIF_PAGAMENTO_REGISTRADO for n in itens_val)


def test_ca12_registrar_pagamento_em_mao_notifica_recebedor_e_validadores() -> None:
    ctx = _cenario_basico()
    cob = ctx["cobranca"]

    resp = ctx["c_devedor"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/pagamentos/",
        {
            "forma": "EM_MAO",
            "data_pagamento": hoje_local().isoformat(),
            "recebedor_id": str(ctx["emissor"].id),
        },
        format="json",
    )

    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["situacao"] == "EM_VALIDACAO"
    pag = body["pagamentos"][0]
    assert pag["forma"] == "EM_MAO"
    assert pag["recebedor"]["id"] == str(ctx["emissor"].id)
    assert pag["comprovante_disponivel"] is False

    itens_val = notificacoes_do(ctx["c_validador"])
    assert any(n["tipo"] == tipos.NOTIF_PAGAMENTO_REGISTRADO for n in itens_val)


def test_ca13_ca14_recusa_anexo_invalido_recebedor_invalido_e_duplo_pagamento() -> None:
    ctx = _cenario_basico()
    cob_id = ctx["cobranca"]["id"]
    url = f"{BASE_FIN}cobrancas/{cob_id}/pagamentos/"

    # Outro usuário que não é devedor -> 403 SO_O_DEVEDOR
    r_outro = _registrar_comprovante(ctx["c_validador"], cob_id)
    assert erro(r_outro) == (403, "SO_O_DEVEDOR")

    # COMPROVANTE sem arquivo -> 400 VALIDATION_ERROR
    r_sem = ctx["c_devedor"].post(
        url,
        {"forma": "COMPROVANTE", "data_pagamento": hoje_local().isoformat()},
        format="multipart",
    )
    assert erro(r_sem) == (400, "VALIDATION_ERROR")

    # > 5 MB -> 400 VALIDATION_ERROR
    grande = _upload("grande.pdf", _PDF_BYTES + b"0" * (5 * 1024 * 1024), "application/pdf")
    r_grande = _registrar_comprovante(ctx["c_devedor"], cob_id, grande)
    assert erro(r_grande) == (400, "VALIDATION_ERROR")

    # SVG/HTML disfarçado de PNG -> 400 VALIDATION_ERROR
    disfarce = _upload("fake.png", b"<svg><script>alert(1)</script></svg>", "image/png")
    r_fake = _registrar_comprovante(ctx["c_devedor"], cob_id, disfarce)
    assert erro(r_fake) == (400, "VALIDATION_ERROR")

    # EM_MAO para si mesmo -> 422 RECEBEDOR_INVALIDO
    r_si = ctx["c_devedor"].post(
        url,
        {
            "forma": "EM_MAO",
            "data_pagamento": hoje_local().isoformat(),
            "recebedor_id": str(ctx["devedor"].id),
        },
        format="json",
    )
    assert erro(r_si) == (422, "RECEBEDOR_INVALIDO")

    # EM_MAO para usuário inativo -> 422 RECEBEDOR_INVALIDO
    inativo = novo_diretor("inativo", situacao=Situacao.INATIVO)
    r_inat = ctx["c_devedor"].post(
        url,
        {
            "forma": "EM_MAO",
            "data_pagamento": hoje_local().isoformat(),
            "recebedor_id": str(inativo.id),
        },
        format="json",
    )
    assert erro(r_inat) == (422, "RECEBEDOR_INVALIDO")

    # Válido, depois duplicado em EM_VALIDACAO -> 422 NAO_ACEITA_PAGAMENTO
    r_ok = _registrar_comprovante(ctx["c_devedor"], cob_id)
    assert r_ok.status_code == 201
    r_dup = _registrar_comprovante(ctx["c_devedor"], cob_id)
    assert erro(r_dup) == (422, "NAO_ACEITA_PAGAMENTO")


def test_ca15_ca16_validar_pagamento_e_impedir_auto_validacao() -> None:
    ctx = _cenario_basico()
    # Devedor com permissão de validar (ou admin) ainda não valida própria cobrança.
    devedor_val: Usuario = novo_diretor("devval")
    conceder_permissoes(devedor_val, PERM_PAGAMENTOS_VALIDAR)
    cob = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=devedor_val.id,
        categoria_id=ctx["cat_id"],
        chave_pix_id=ctx["pix_id"],
    )
    c_dev_val = client(devedor_val)
    assert _registrar_comprovante(c_dev_val, cob["id"]).status_code == 201

    r_auto = c_dev_val.post(
        f"{BASE_FIN}cobrancas/{cob['id']}/validar-pagamento/",
        {"motivo_id": ctx["m_val"], "texto": "auto"},
        format="json",
    )
    assert erro(r_auto) == (403, "DEVEDOR_NAO_VALIDA")

    cob_admin = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["admin"].id,
        categoria_id=ctx["cat_id"],
        chave_pix_id=ctx["pix_id"],
    )
    assert _registrar_comprovante(ctx["c_admin"], cob_admin["id"]).status_code == 201
    r_auto_admin = ctx["c_admin"].post(
        f"{BASE_FIN}cobrancas/{cob_admin['id']}/validar-pagamento/",
        {"motivo_id": ctx["m_val"], "texto": "auto-admin"},
        format="json",
    )
    assert erro(r_auto_admin) == (403, "DEVEDOR_NAO_VALIDA")

    # Sem permissão de validar -> 403
    r_sem_perm = ctx["c_outro_cargo"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/validar-pagamento/",
        {"motivo_id": ctx["m_val"], "texto": ""},
        format="json",
    )
    assert r_sem_perm.status_code == 403

    # Validador aprova -> PAGA + auditoria + notificação
    r_val = ctx["c_validador"].post(
        f"{BASE_FIN}cobrancas/{cob['id']}/validar-pagamento/",
        {"motivo_id": ctx["m_val"], "texto": "Pix confirmado"},
        format="json",
    )
    assert r_val.status_code == 200, r_val.content
    body = r_val.json()
    assert body["situacao"] == "PAGA"
    assert body["paga_em"] is not None
    assert body["pagamentos"][0]["situacao"] == "VALIDADO"
    assert body["pagamentos"][0]["motivo_texto"] == "Conferido no extrato"
    assert "registrar_pagamento" not in body["acoes"]

    itens_dev = notificacoes_do(c_dev_val)
    assert any(n["tipo"] == tipos.NOTIF_PAGAMENTO_VALIDADO for n in itens_dev)


def test_ca17_rejeitar_pagamento_retorna_para_aberta_ou_atrasada_e_permite_reenvio() -> None:
    ctx = _cenario_basico()

    # Caso 1: vencimento futuro -> volta para ABERTA
    cob_futura = ctx["cobranca"]
    assert _registrar_comprovante(ctx["c_devedor"], cob_futura["id"]).status_code == 201
    r_rej = ctx["c_validador"].post(
        f"{BASE_FIN}cobrancas/{cob_futura['id']}/rejeitar-pagamento/",
        {"motivo_id": ctx["m_rej"], "texto": "Imagem cortada"},
        format="json",
    )
    assert r_rej.status_code == 200, r_rej.content
    assert r_rej.json()["situacao"] == "ABERTA"
    assert r_rej.json()["pagamentos"][0]["situacao"] == "REJEITADO"

    # Reenvio após rejeição funciona e preserva histórico
    r_novo = _registrar_comprovante(ctx["c_devedor"], cob_futura["id"])
    assert r_novo.status_code == 201
    assert len(r_novo.json()["pagamentos"]) == 2

    # Caso 2: após vencimento passar -> rejeição retorna para ATRASADA
    cob_vencida = criar_cobranca(
        ctx["c_emissor"],
        devedor_id=ctx["devedor"].id,
        categoria_id=ctx["cat_id"],
        chave_pix_id=ctx["pix_id"],
        vencimento=hoje_local(),
    )
    assert _registrar_comprovante(ctx["c_devedor"], cob_vencida["id"]).status_code == 201
    with mock.patch(
        "financeiro.services.pagamentos.timezone.localdate",
        return_value=hoje_local() + timedelta(days=3),
    ):
        r_rej2 = ctx["c_validador"].post(
            f"{BASE_FIN}cobrancas/{cob_vencida['id']}/rejeitar-pagamento/",
            {"motivo_id": ctx["m_rej"], "texto": "Falta autenticação"},
            format="json",
        )
    assert r_rej2.status_code == 200
    assert r_rej2.json()["situacao"] == "ATRASADA"

    itens_dev = notificacoes_do(ctx["c_devedor"])
    assert any(n["tipo"] == tipos.NOTIF_PAGAMENTO_REJEITADO for n in itens_dev)


def test_ca18_ca19_acesso_privado_ao_comprovante_e_recibo_pdf() -> None:
    ctx = _cenario_basico()
    cob_id = ctx["cobranca"]["id"]

    # Recibo antes do pagamento -> 422 NAO_ESTA_PAGA
    assert erro(ctx["c_devedor"].get(f"{BASE_FIN}cobrancas/{cob_id}/recibo/")) == (
        422,
        "NAO_ESTA_PAGA",
    )

    r_reg = _registrar_comprovante(ctx["c_devedor"], cob_id)
    assert r_reg.status_code == 201
    pag_id = r_reg.json()["pagamentos"][0]["id"]
    url_comp = f"{BASE_FIN}cobrancas/{cob_id}/pagamentos/{pag_id}/comprovante/"

    # Diretor comum com cargo (sem pagamentos.validar) -> 403 PERMISSION_DENIED
    assert erro(ctx["c_outro_cargo"].get(url_comp)) == (403, "PERMISSION_DENIED")

    # Devedor, validador e admin conseguem baixar com headers seguros
    for c_autorizado in (ctx["c_devedor"], ctx["c_validador"], ctx["c_admin"]):
        r_comp = c_autorizado.get(url_comp)
        assert r_comp.status_code == 200
        assert r_comp.headers["X-Content-Type-Options"] == "nosniff"
        assert "private" in r_comp.headers["Cache-Control"]
        assert "no-store" in r_comp.headers["Cache-Control"]
        assert r_comp.content.startswith(b"%PDF-1.4")

    # Valida e emite recibo
    assert (
        ctx["c_validador"]
        .post(
            f"{BASE_FIN}cobrancas/{cob_id}/validar-pagamento/",
            {"motivo_id": ctx["m_val"], "texto": "OK"},
            format="json",
        )
        .status_code
        == 200
    )

    for c_escopo in (ctx["c_devedor"], ctx["c_outro_cargo"], ctx["c_admin"]):
        r_rec = c_escopo.get(f"{BASE_FIN}cobrancas/{cob_id}/recibo/")
        assert r_rec.status_code == 200
        assert r_rec.headers["Content-Type"] == "application/pdf"
        assert r_rec.headers["X-Content-Type-Options"] == "nosniff"
        assert r_rec.content.startswith(b"%PDF-1.4")

    # Diretor sem cargo de outro usuário -> 403 PERMISSION_DENIED no recibo e no comprovante
    sem_cargo = novo_diretor("semcargo")
    assert erro(client(sem_cargo).get(f"{BASE_FIN}cobrancas/{cob_id}/recibo/")) == (
        403,
        "PERMISSION_DENIED",
    )
    assert erro(client(sem_cargo).get(url_comp)) == (403, "PERMISSION_DENIED")


@pytest.mark.django_db(transaction=True)
def test_ca20_validacao_concorrente_respeita_select_for_update() -> None:
    admin = novo_diretor("admin", admin=True)
    c_admin = client(admin)
    val1 = novo_diretor("valone")
    val2 = novo_diretor("valtwo")
    devedor = novo_diretor("devconc")
    conceder_permissoes(val1, PERM_COBRANCAS_CRIAR, PERM_PAGAMENTOS_VALIDAR)
    conceder_permissoes(val2, PERM_PAGAMENTOS_VALIDAR)

    cat_id = garantir_categoria(c_admin)
    pix_id = garantir_chave_pix(c_admin, padrao=True)
    m_val = garantir_motivo(c_admin, tipos.DECISAO_PAGAMENTO_VALIDAR, "Conferido")
    cob = criar_cobranca(
        client(val1),
        devedor_id=devedor.id,
        categoria_id=cat_id,
        chave_pix_id=pix_id,
        vencimento=timezone.localdate() + timedelta(days=5),
    )
    anexo = SimpleUploadedFile(
        "conc.png",
        BytesIO(_PNG_BYTES).getvalue(),
        content_type="image/png",
    )
    assert _registrar_comprovante(client(devedor), cob["id"], anexo).status_code == 201

    barreira = threading.Barrier(2)
    resultados: list[int] = []
    trava = threading.Lock()
    url_val = f"{BASE_FIN}cobrancas/{cob['id']}/validar-pagamento/"

    def _tentar(usuario: Usuario) -> None:
        try:
            c = client(usuario)
            barreira.wait(timeout=5)
            resp = c.post(url_val, {"motivo_id": m_val, "texto": "Simultâneo"}, format="json")
            with trava:
                resultados.append(resp.status_code)
        finally:
            connection.close()

    t1 = threading.Thread(target=_tentar, args=(val1,))
    t2 = threading.Thread(target=_tentar, args=(val2,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert sorted(resultados) == [200, 422]
    detalhe = client(devedor).get(f"{BASE_FIN}cobrancas/{cob['id']}/").json()
    assert detalhe["situacao"] == "PAGA"
    assert sum(1 for p in detalhe["pagamentos"] if p["situacao"] == "VALIDADO") == 1
