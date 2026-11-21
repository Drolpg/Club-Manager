"""Regras puras de `comunicacao` (spec técnica do M9, "Quem pode" e "Depois de quem pode"). Sem banco."""

import uuid
from datetime import date

import pytest

from comunicacao.domain.autorizacao import (
    Comando,
    Fatos,
    acoes_do_comentario,
    acoes_do_comunicado,
    acoes_do_documento,
    avaliar,
    ocultar_pela_gerencia,
    pode_ver_comentario,
    pode_ver_comunicado,
)
from comunicacao.domain.regras import (
    LIMITE_DO_COMENTARIO,
    LIMITE_DO_MOTIVO,
    LIMITE_DO_TEXTO,
    LIMITE_DO_TITULO,
    TIPOS_DE_REACAO,
    reuniao_no_futuro,
    validar_ata,
    validar_comentario,
    validar_comunicado,
    validar_documento,
    validar_motivo,
)
from comunicacao.domain.valores import (
    SituacaoDoComentario,
    SituacaoDoComunicado,
    SituacaoDoDocumento,
    TipoDeDocumento,
)

C = Comando
AUTOR = uuid.uuid4()
OUTRO = uuid.uuid4()
PUBLICADO = SituacaoDoComunicado.PUBLICADO
DESPUBLICADO = SituacaoDoComunicado.DESPUBLICADO
VISIVEL = SituacaoDoComentario.VISIVEL
OCULTO = SituacaoDoComentario.OCULTO
VIGENTE = SituacaoDoDocumento.VIGENTE
ARQUIVADO = SituacaoDoDocumento.ARQUIVADO
DOCUMENTO = TipoDeDocumento.DOCUMENTO
ATA = TipoDeDocumento.ATA


def fatos(**campos: object) -> Fatos:
    """Quem age é `OUTRO`, sem permissão nenhuma; o autor de tudo é `AUTOR`."""
    base: dict[str, object] = {
        "ator_id": OUTRO,
        "le_gestao": True,
        "pode_publicar": False,
        "pode_gerenciar": False,
        "pode_enviar_documentos": False,
        "pode_registrar_atas": False,
        "autor_do_comunicado_id": AUTOR,
        "situacao_do_comunicado": PUBLICADO,
        "autor_do_comentario_id": AUTOR,
        "enviado_por_id": AUTOR,
    }
    base.update(campos)
    return Fatos(**base)  # type: ignore[arg-type]


def erro_de(comando: Comando, f: Fatos) -> str | None:
    return avaliar(comando, f).erro


# --- leitura de gestão: sem ela, nada -----------------------------------------------------------------------


@pytest.mark.parametrize("comando", list(Comando))
def test_sem_leitura_de_gestao_toda_acao_e_negada(comando: Comando) -> None:
    f = fatos(
        ator_id=AUTOR,
        le_gestao=False,
        pode_publicar=True,
        pode_gerenciar=True,
        pode_enviar_documentos=True,
        pode_registrar_atas=True,
    )

    assert erro_de(comando, f) == "PERMISSION_DENIED"


# --- comunicados --------------------------------------------------------------------------------------------


def test_publicar_exige_a_permissao_de_publicar() -> None:
    assert avaliar(C.PUBLICAR, fatos(pode_publicar=True)).pode
    assert erro_de(C.PUBLICAR, fatos()) == "PERMISSION_DENIED"
    # Quem só gerencia não publica: são permissões distintas.
    assert erro_de(C.PUBLICAR, fatos(pode_gerenciar=True)) == "PERMISSION_DENIED"


@pytest.mark.parametrize(
    ("comando", "situacao"),
    [
        (C.EDITAR_COMUNICADO, PUBLICADO),
        (C.DESPUBLICAR, PUBLICADO),
        (C.REPUBLICAR, DESPUBLICADO),
    ],
)
def test_autor_com_a_permissao_ou_quem_gerencia_edita_despublica_e_republica(
    comando: Comando, situacao: SituacaoDoComunicado
) -> None:
    assert avaliar(comando, fatos(ator_id=AUTOR, pode_publicar=True, situacao_do_comunicado=situacao)).pode
    assert avaliar(comando, fatos(pode_gerenciar=True, situacao_do_comunicado=situacao)).pode


@pytest.mark.parametrize("comando", [C.EDITAR_COMUNICADO, C.DESPUBLICAR, C.REPUBLICAR])
def test_autor_que_perdeu_a_permissao_e_terceiro_sao_negados(comando: Comando) -> None:
    situacao = DESPUBLICADO if comando == C.REPUBLICAR else PUBLICADO

    assert erro_de(comando, fatos(ator_id=AUTOR, situacao_do_comunicado=situacao)) == "PERMISSION_DENIED"
    assert erro_de(comando, fatos(pode_publicar=True, situacao_do_comunicado=situacao)) == "PERMISSION_DENIED"


@pytest.mark.parametrize("comando", [C.FIXAR, C.DESAFIXAR])
def test_fixar_e_desafixar_so_com_gerenciar_nem_o_autor(comando: Comando) -> None:
    fixado = comando == C.DESAFIXAR

    assert avaliar(comando, fatos(pode_gerenciar=True, fixado=fixado)).pode
    assert erro_de(comando, fatos(ator_id=AUTOR, pode_publicar=True, fixado=fixado)) == "PERMISSION_DENIED"


def test_situacao_do_comunicado_em_cada_comando() -> None:
    g = {"pode_gerenciar": True, "pode_publicar": True}

    assert erro_de(C.EDITAR_COMUNICADO, fatos(**g, situacao_do_comunicado=DESPUBLICADO)) == (
        "COMUNICADO_NAO_PUBLICADO"
    )
    assert erro_de(C.FIXAR, fatos(**g, situacao_do_comunicado=DESPUBLICADO)) == "COMUNICADO_NAO_PUBLICADO"
    assert erro_de(C.FIXAR, fatos(**g, fixado=True)) == "JA_ESTA_FIXADO"
    assert erro_de(C.DESAFIXAR, fatos(**g, fixado=False)) == "NAO_ESTA_FIXADO"
    assert erro_de(C.DESPUBLICAR, fatos(**g, situacao_do_comunicado=DESPUBLICADO)) == (
        "COMUNICADO_JA_DESPUBLICADO"
    )
    assert erro_de(C.REPUBLICAR, fatos(**g)) == "COMUNICADO_JA_PUBLICADO"


# --- reações e comentários ----------------------------------------------------------------------------------


@pytest.mark.parametrize("comando", [C.REAGIR, C.COMENTAR])
def test_todo_diretor_com_leitura_reage_e_comenta_em_comunicado_publicado(comando: Comando) -> None:
    assert avaliar(comando, fatos()).pode
    assert erro_de(comando, fatos(situacao_do_comunicado=DESPUBLICADO)) == "COMUNICADO_NAO_PUBLICADO"


def test_retirar_a_reacao_exige_reacao_ativa_e_comunicado_publicado() -> None:
    assert avaliar(C.RETIRAR_REACAO, fatos(tem_reacao_ativa=True)).pode
    assert erro_de(C.RETIRAR_REACAO, fatos(tem_reacao_ativa=False)) == "SEM_REACAO"
    assert erro_de(C.RETIRAR_REACAO, fatos(tem_reacao_ativa=True, situacao_do_comunicado=DESPUBLICADO)) == (
        "COMUNICADO_NAO_PUBLICADO"
    )


def test_so_o_autor_do_comentario_o_edita_nem_quem_gerencia() -> None:
    assert avaliar(C.EDITAR_COMENTARIO, fatos(ator_id=AUTOR)).pode
    assert erro_de(C.EDITAR_COMENTARIO, fatos(pode_gerenciar=True)) == "PERMISSION_DENIED"
    assert erro_de(C.EDITAR_COMENTARIO, fatos(ator_id=AUTOR, situacao_do_comunicado=DESPUBLICADO)) == (
        "COMUNICADO_NAO_PUBLICADO"
    )


def test_autor_oculta_o_proprio_com_o_comunicado_publicado() -> None:
    assert avaliar(C.OCULTAR_COMENTARIO, fatos(ator_id=AUTOR, situacao_do_comentario=VISIVEL)).pode
    f = fatos(ator_id=AUTOR, situacao_do_comentario=VISIVEL, situacao_do_comunicado=DESPUBLICADO)

    assert erro_de(C.OCULTAR_COMENTARIO, f) == "COMUNICADO_NAO_PUBLICADO"


def test_quem_gerencia_oculta_em_qualquer_situacao_do_comunicado() -> None:
    assert avaliar(C.OCULTAR_COMENTARIO, fatos(pode_gerenciar=True, situacao_do_comentario=VISIVEL)).pode
    f = fatos(pode_gerenciar=True, situacao_do_comentario=VISIVEL, situacao_do_comunicado=DESPUBLICADO)

    assert avaliar(C.OCULTAR_COMENTARIO, f).pode


def test_terceiro_sem_gerenciar_nao_oculta_nem_o_autor_do_comunicado() -> None:
    # O autor do comunicado (AUTOR) comenta como terceiro: o comentário é de OUTRO.
    comentario = {"autor_do_comentario_id": OUTRO, "situacao_do_comentario": VISIVEL}

    assert erro_de(C.OCULTAR_COMENTARIO, fatos(ator_id=AUTOR, pode_publicar=True, **comentario)) == (
        "PERMISSION_DENIED"
    )
    assert erro_de(C.OCULTAR_COMENTARIO, fatos(situacao_do_comentario=VISIVEL)) == "PERMISSION_DENIED"


def test_ocultar_comentario_ja_oculto() -> None:
    f = fatos(pode_gerenciar=True, situacao_do_comentario=OCULTO)

    assert erro_de(C.OCULTAR_COMENTARIO, f) == "COMENTARIO_JA_OCULTO"


def test_reexibir_o_autor_so_o_que_ele_mesmo_ocultou_e_a_gerencia_sempre() -> None:
    assert avaliar(
        C.REEXIBIR_COMENTARIO, fatos(ator_id=AUTOR, situacao_do_comentario=OCULTO, oculto_pela_gerencia=False)
    ).pode
    assert erro_de(
        C.REEXIBIR_COMENTARIO, fatos(ator_id=AUTOR, situacao_do_comentario=OCULTO, oculto_pela_gerencia=True)
    ) == ("PERMISSION_DENIED")
    assert avaliar(
        C.REEXIBIR_COMENTARIO,
        fatos(pode_gerenciar=True, situacao_do_comentario=OCULTO, oculto_pela_gerencia=True),
    ).pode
    assert erro_de(C.REEXIBIR_COMENTARIO, fatos(situacao_do_comentario=OCULTO)) == "PERMISSION_DENIED"


def test_reexibir_comentario_que_nao_esta_oculto() -> None:
    f = fatos(pode_gerenciar=True, situacao_do_comentario=VISIVEL)

    assert erro_de(C.REEXIBIR_COMENTARIO, f) == "COMENTARIO_NAO_ESTA_OCULTO"


def test_a_ocultacao_pela_gerencia_e_de_quem_nao_e_o_autor_do_comentario() -> None:
    assert not ocultar_pela_gerencia(fatos(ator_id=AUTOR, pode_gerenciar=True))
    assert ocultar_pela_gerencia(fatos(ator_id=OUTRO, pode_gerenciar=True))


# --- documentos ---------------------------------------------------------------------------------------------


def test_enviar_documento_e_registrar_ata_sao_permissoes_distintas() -> None:
    assert avaliar(C.ENVIAR_DOCUMENTO, fatos(pode_enviar_documentos=True)).pode
    assert erro_de(C.ENVIAR_DOCUMENTO, fatos(pode_registrar_atas=True)) == "PERMISSION_DENIED"
    assert avaliar(C.REGISTRAR_ATA, fatos(pode_registrar_atas=True)).pode
    assert erro_de(C.REGISTRAR_ATA, fatos(pode_enviar_documentos=True)) == "PERMISSION_DENIED"


@pytest.mark.parametrize("comando", [C.NOVA_VERSAO, C.ARQUIVAR])
def test_quem_enviou_ainda_com_a_permissao_do_tipo_ou_quem_gerencia(comando: Comando) -> None:
    doc = {"tipo_do_documento": DOCUMENTO, "situacao_do_documento": VIGENTE}
    ata = {"tipo_do_documento": ATA, "situacao_do_documento": VIGENTE}

    assert avaliar(comando, fatos(ator_id=AUTOR, pode_enviar_documentos=True, **doc)).pode
    assert erro_de(comando, fatos(ator_id=AUTOR, pode_registrar_atas=True, **doc)) == "PERMISSION_DENIED"
    assert avaliar(comando, fatos(ator_id=AUTOR, pode_registrar_atas=True, **ata)).pode
    assert erro_de(comando, fatos(ator_id=AUTOR, pode_enviar_documentos=True, **ata)) == "PERMISSION_DENIED"
    assert avaliar(comando, fatos(pode_gerenciar=True, **doc)).pode
    assert erro_de(comando, fatos(pode_enviar_documentos=True, **doc)) == "PERMISSION_DENIED"


def test_situacao_do_documento_em_cada_comando() -> None:
    base = {"pode_gerenciar": True, "tipo_do_documento": DOCUMENTO}
    vigente = fatos(**base, situacao_do_documento=VIGENTE)
    arquivado = fatos(**base, situacao_do_documento=ARQUIVADO)

    assert erro_de(C.NOVA_VERSAO, arquivado) == "DOCUMENTO_ARQUIVADO"
    assert erro_de(C.ARQUIVAR, arquivado) == "DOCUMENTO_JA_ARQUIVADO"
    assert erro_de(C.DESARQUIVAR, vigente) == "DOCUMENTO_NAO_ESTA_ARQUIVADO"
    assert avaliar(C.NOVA_VERSAO, vigente).pode
    assert avaliar(C.ARQUIVAR, vigente).pode
    assert avaliar(C.DESARQUIVAR, arquivado).pode


# --- visibilidade -------------------------------------------------------------------------------------------


def test_comunicado_publicado_e_visto_por_quem_le_gestao() -> None:
    assert pode_ver_comunicado(PUBLICADO, fatos())
    assert not pode_ver_comunicado(PUBLICADO, fatos(le_gestao=False))


def test_comunicado_despublicado_so_o_autor_e_quem_gerencia_veem() -> None:
    assert pode_ver_comunicado(DESPUBLICADO, fatos(ator_id=AUTOR))
    assert pode_ver_comunicado(DESPUBLICADO, fatos(pode_gerenciar=True))
    assert not pode_ver_comunicado(DESPUBLICADO, fatos())
    assert not pode_ver_comunicado(DESPUBLICADO, fatos(ator_id=AUTOR, le_gestao=False))


def test_comentario_oculto_so_o_autor_e_quem_gerencia_veem() -> None:
    assert pode_ver_comentario(VISIVEL, fatos())
    assert pode_ver_comentario(OCULTO, fatos(ator_id=AUTOR))
    assert pode_ver_comentario(OCULTO, fatos(pode_gerenciar=True))
    assert not pode_ver_comentario(OCULTO, fatos())
    assert not pode_ver_comentario(VISIVEL, fatos(le_gestao=False))


# --- ações do detalhe ---------------------------------------------------------------------------------------


def test_acoes_do_comunicado_por_papel_e_situacao() -> None:
    assert acoes_do_comunicado(fatos()) == (C.REAGIR, C.COMENTAR)
    assert acoes_do_comunicado(fatos(tem_reacao_ativa=True)) == (C.REAGIR, C.RETIRAR_REACAO, C.COMENTAR)
    assert acoes_do_comunicado(fatos(ator_id=AUTOR, pode_publicar=True)) == (
        C.EDITAR_COMUNICADO,
        C.DESPUBLICAR,
        C.REAGIR,
        C.COMENTAR,
    )
    assert acoes_do_comunicado(fatos(pode_gerenciar=True, situacao_do_comunicado=DESPUBLICADO)) == (
        C.REPUBLICAR,
    )
    assert acoes_do_comunicado(fatos(pode_gerenciar=True)) == (
        C.EDITAR_COMUNICADO,
        C.DESPUBLICAR,
        C.FIXAR,
        C.REAGIR,
        C.COMENTAR,
    )
    assert acoes_do_comunicado(fatos(pode_gerenciar=True, fixado=True)) == (
        C.EDITAR_COMUNICADO,
        C.DESPUBLICAR,
        C.DESAFIXAR,
        C.REAGIR,
        C.COMENTAR,
    )


def test_acoes_do_comentario_por_papel_e_situacao() -> None:
    visivel = {"situacao_do_comentario": VISIVEL}

    assert acoes_do_comentario(fatos(ator_id=AUTOR, **visivel)) == (C.EDITAR_COMENTARIO, C.OCULTAR_COMENTARIO)
    assert acoes_do_comentario(fatos(pode_gerenciar=True, **visivel)) == (C.OCULTAR_COMENTARIO,)
    assert acoes_do_comentario(fatos(**visivel)) == ()
    assert acoes_do_comentario(
        fatos(pode_gerenciar=True, situacao_do_comentario=OCULTO, oculto_pela_gerencia=True)
    ) == (C.REEXIBIR_COMENTARIO,)


def test_acoes_do_documento_por_papel_e_situacao() -> None:
    vigente = {"tipo_do_documento": DOCUMENTO, "situacao_do_documento": VIGENTE}
    arquivado = {"tipo_do_documento": DOCUMENTO, "situacao_do_documento": ARQUIVADO}

    assert acoes_do_documento(fatos(pode_gerenciar=True, **vigente)) == (C.NOVA_VERSAO, C.ARQUIVAR)
    assert acoes_do_documento(fatos(pode_gerenciar=True, **arquivado)) == (C.DESARQUIVAR,)
    assert acoes_do_documento(fatos(**vigente)) == ()


# --- validações ---------------------------------------------------------------------------------------------


def test_comunicado_valido_nao_tem_erros() -> None:
    assert validar_comunicado("COMUNICADO", "Reunião", "Sábado, às 10h.") == {}
    assert validar_comunicado("PAUTA", "Pauta", "1. Orçamento") == {}


def test_comunicado_com_campos_invalidos() -> None:
    erros = validar_comunicado("NOTICIA", "   ", "")

    assert set(erros) == {"tipo", "titulo", "texto"}


def test_limites_do_comunicado() -> None:
    assert validar_comunicado("COMUNICADO", "t" * LIMITE_DO_TITULO, "x" * LIMITE_DO_TEXTO) == {}
    erros = validar_comunicado("COMUNICADO", "t" * (LIMITE_DO_TITULO + 1), "x" * (LIMITE_DO_TEXTO + 1))

    assert set(erros) == {"titulo", "texto"}


def test_comentario() -> None:
    assert validar_comentario("Ciente.") == {}
    assert set(validar_comentario("  ")) == {"texto"}
    assert validar_comentario("x" * LIMITE_DO_COMENTARIO) == {}
    assert set(validar_comentario("x" * (LIMITE_DO_COMENTARIO + 1))) == {"texto"}


def test_motivo() -> None:
    assert validar_motivo("Duplicado") == {}
    assert set(validar_motivo("")) == {"motivo"}
    assert set(validar_motivo("m" * (LIMITE_DO_MOTIVO + 1))) == {"motivo"}


def test_documento() -> None:
    assert validar_documento("Estatuto", "") == {}
    assert set(validar_documento("", "")) == {"titulo"}
    assert set(validar_documento("Estatuto", "d" * 1001)) == {"descricao"}


def test_ata_exige_titulo_e_data_da_reuniao() -> None:
    assert validar_ata("Ata de novembro", "", date(2026, 11, 20)) == {}
    assert set(validar_ata("", "", None)) == {"titulo", "data_da_reuniao"}


def test_reuniao_no_futuro_e_depois_de_hoje() -> None:
    hoje = date(2026, 11, 20)

    assert reuniao_no_futuro(date(2026, 11, 21), hoje)
    assert not reuniao_no_futuro(hoje, hoje)
    assert not reuniao_no_futuro(date(2026, 11, 19), hoje)


def test_as_quatro_reacoes_fixas() -> None:
    assert TIPOS_DE_REACAO == ("CIENTE", "DE_ACORDO", "DUVIDA", "COMEMORACAO")
