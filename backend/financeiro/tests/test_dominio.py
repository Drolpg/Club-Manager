"""Testes unitários puros do domínio financeiro (sem banco e sem framework)."""

import uuid
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser

import pytest

from financeiro.domain.autorizacao import (
    FatosCobranca,
    FatosEntrada,
    acoes_cobranca_disponiveis,
    acoes_entrada_disponiveis,
    avaliar_cobranca,
    avaliar_entrada,
    pode_ver_comprovante_cobranca,
    pode_ver_comprovante_entrada,
)
from financeiro.domain.competencia import (
    Periodicidade,
    Periodo,
    RecorrenciaParaGeracao,
    SuspensaoParaVerificacao,
    competencia_da_data,
    competencias_a_gerar,
    data_vencimento_da_competencia,
    suspensa_na_data,
)
from financeiro.domain.pix import (
    TipoChavePix,
    crc16_ccitt,
    gerar_pix_copia_e_cola,
    normalizar_e_validar_chave,
)
from financeiro.domain.qrcode_svg import (
    _TABELA_M,
    _bits_formato,
    _bits_versao,
    _desenhar_base,
    gerar_qrcode_svg,
)
from financeiro.domain.transicoes import (
    ComandoCobranca,
    ComandoEntrada,
    SituacaoCobranca,
    SituacaoEntrada,
    data_limite_convocacao,
    dias_pausados_em_decisao,
    estado_sem_pagamento,
    transicao_cobranca_permitida,
    transicao_entrada_permitida,
)


def _extrair_tlv(codigo: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    pos = 0
    while pos < len(codigo):
        tag = codigo[pos : pos + 2]
        tamanho = int(codigo[pos + 2 : pos + 4])
        valor = codigo[pos + 4 : pos + 4 + tamanho]
        campos[tag] = valor
        pos += 4 + tamanho
    return campos


class TestPix:
    @pytest.mark.parametrize(
        ("tipo", "entrada", "esperado"),
        [
            (TipoChavePix.EMAIL, " Financeiro@Clube.ORG.br ", "financeiro@clube.org.br"),
            (TipoChavePix.TELEFONE, "(11) 99988-7766", "+5511999887766"),
            (TipoChavePix.TELEFONE, "+5511999887766", "+5511999887766"),
            (TipoChavePix.CNPJ, "11.222.333/0001-81", "11222333000181"),
            (TipoChavePix.CPF, "529.982.247-25", "52998224725"),
            (
                TipoChavePix.ALEATORIA,
                "123E4567-E89B-12D3-A456-426614174000",
                "123e4567-e89b-12d3-a456-426614174000",
            ),
        ],
    )
    def test_CA03_normaliza_e_valida_chaves_validas(self, tipo: str, entrada: str, esperado: str) -> None:
        assert normalizar_e_validar_chave(tipo, entrada) == esperado

    @pytest.mark.parametrize(
        ("tipo", "entrada"),
        [
            (TipoChavePix.EMAIL, "nao-eh-email"),
            (TipoChavePix.EMAIL, "sem-dominio@localhost"),
            (TipoChavePix.TELEFONE, "12345"),
            (TipoChavePix.CNPJ, "11.111.111/1111-11"),
            (TipoChavePix.CNPJ, "11.222.333/0001-82"),
            (TipoChavePix.CPF, "111.111.111-11"),
            (TipoChavePix.CPF, "529.982.247-26"),
            (TipoChavePix.ALEATORIA, "chave-nao-uuid"),
            ("INVALIDO", "qualquer"),
        ],
    )
    def test_CA03_recusa_chaves_invalidas(self, tipo: str, entrada: str) -> None:
        with pytest.raises(ValueError, match=r".+"):
            normalizar_e_validar_chave(tipo, entrada)

    def test_CA07_crc16_ccitt_padrao_bacen(self) -> None:
        # Vetor oficial EMV QR Code / Bacen: CRC de "123456789" com 0x1021 init 0xFFFF = 0x29B1.
        assert crc16_ccitt("123456789") == "29B1"

    def test_CA07_gera_br_code_valido_com_campos_obrigatorios_e_crc(self) -> None:
        cob_id = uuid.UUID("01932e50-1234-7000-8000-000000000042")
        codigo = gerar_pix_copia_e_cola(
            chave="financeiro@clube.org.br",
            nome_recebedor="Associação Atlética São José",
            cidade="São Paulo",
            valor=Decimal("150.00"),
            cobranca_id=cob_id,
        )

        assert codigo.startswith("000201")
        campos = _extrair_tlv(codigo)
        assert campos["00"] == "01"
        sub26 = _extrair_tlv(campos["26"])
        assert sub26["00"] == "br.gov.bcb.pix"
        assert sub26["01"] == "financeiro@clube.org.br"
        assert campos["52"] == "0000"
        assert campos["53"] == "986"
        assert campos["54"] == "150.00"
        assert campos["58"] == "BR"
        assert campos["59"] == "Associacao Atletica Sao J"
        assert len(campos["59"]) <= 25
        assert campos["60"] == "Sao Paulo"
        assert len(campos["60"]) <= 15
        sub62 = _extrair_tlv(campos["62"])
        assert len(sub62["05"]) == 25
        assert sub62["05"].isalnum()
        assert codigo[-8:-4] == "6304"
        assert campos["63"] == crc16_ccitt(codigo[:-4])


class TestQrCodeSvg:
    def test_CA07_gera_svg_valido_deterministico_sem_scripts(self) -> None:
        codigo = gerar_pix_copia_e_cola(
            chave="financeiro@clube.org.br",
            nome_recebedor="Clube Atletico",
            cidade="Sao Paulo",
            valor=Decimal("85.50"),
            cobranca_id=uuid.UUID("01932e50-1234-7000-8000-000000000001"),
        )
        svg1 = gerar_qrcode_svg(codigo)
        svg2 = gerar_qrcode_svg(codigo)

        assert svg1 == svg2
        assert "<script" not in svg1.lower()

        tags: list[tuple[str, dict[str, str | None]]] = []

        class _Parser(HTMLParser):
            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                tags.append((tag, dict(attrs)))

        _Parser().feed(svg1)
        assert tags[0][0] == "svg"
        view_box = (tags[0][1]["viewbox"] or "").split()
        assert len(view_box) == 4
        assert int(view_box[2]) == int(view_box[3])
        assert int(view_box[2]) >= 29
        caminhos = [attrs for tag, attrs in tags if tag == "path"]
        assert len(caminhos) == 1
        assert len(caminhos[0]["d"] or "") > 200

    def test_recusa_codigo_vazio(self) -> None:
        with pytest.raises(ValueError, match="vazio"):
            gerar_qrcode_svg("")

    def test_conformidade_iso18004_versoes_e_bch(self) -> None:
        # Vetores oficiais ISO/IEC 18004: formato M+mask1 = 0x5125, versao 7 = 0x07C94.
        assert _bits_formato(1) == 0x5125
        assert _bits_versao(7) == 0x07C94
        remainder_esperado = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, **dict.fromkeys(range(7, 14), 0)}
        for v in range(14, 21):
            remainder_esperado[v] = 3

        for versao in range(1, 21):
            _, funcao = _desenhar_base(versao)
            livres = sum(1 for linha in funcao for cel in linha if not cel)
            dados, ec, g1, _, g2, _ = _TABELA_M[versao - 1]
            total_bytes = dados + ec * (g1 + g2)
            assert livres == total_bytes * 8 + remainder_esperado[versao]


class TestTransicoes:
    def test_INV_COB_02_situacoes_finais_nao_aceitam_comandos(self) -> None:
        # Adendo P4 (M7): `PAGA` aceita apenas `ESTORNAR`, enquanto `ESTORNADA` e as demais finais
        # não aceitam nenhum comando.
        finais_imutaveis = (
            SituacaoCobranca.ISENTA,
            SituacaoCobranca.CANCELADA,
            SituacaoCobranca.PERDOADA,
            SituacaoCobranca.RENEGOCIADA,
            SituacaoCobranca.ESTORNADA,
        )
        for sit in finais_imutaveis:
            for cmd in ComandoCobranca:
                assert not transicao_cobranca_permitida(sit, cmd), f"{sit} não aceita {cmd}"
        for cmd in ComandoCobranca:
            esperado = cmd == ComandoCobranca.ESTORNAR
            assert transicao_cobranca_permitida(SituacaoCobranca.PAGA, cmd) is esperado

    def test_INV_COB_07_estado_sem_pagamento(self) -> None:
        hoje = date(2026, 11, 15)
        assert estado_sem_pagamento(date(2026, 11, 15), hoje) == SituacaoCobranca.ABERTA
        assert estado_sem_pagamento(date(2026, 11, 16), hoje) == SituacaoCobranca.ABERTA
        assert estado_sem_pagamento(date(2026, 11, 14), hoje) == SituacaoCobranca.ATRASADA

    def test_pausa_inadimplencia_e_data_limite_convocacao(self) -> None:
        vencimento = date(2026, 10, 10)
        # Questionado antes de vencer: pausa efetiva só começa após o vencimento.
        assert dias_pausados_em_decisao(date(2026, 10, 5), vencimento, date(2026, 10, 14)) == 4
        # Questionado já vencido em 12/10, mantido em 17/10 = 5 dias pausados.
        assert dias_pausados_em_decisao(date(2026, 10, 12), vencimento, date(2026, 10, 17)) == 5
        assert dias_pausados_em_decisao(None, vencimento, date(2026, 10, 17)) == 0
        # 30 dias + 5 pausados => limite vai a 2026-11-14.
        assert data_limite_convocacao(vencimento, 30, 5) == date(2026, 11, 14)

    def test_transicoes_entrada(self) -> None:
        assert transicao_entrada_permitida(SituacaoEntrada.EM_VALIDACAO, ComandoEntrada.VALIDAR)
        assert transicao_entrada_permitida(SituacaoEntrada.EM_VALIDACAO, ComandoEntrada.REJEITAR)
        assert not transicao_entrada_permitida(SituacaoEntrada.VALIDADA, ComandoEntrada.REJEITAR)
        assert not transicao_entrada_permitida(SituacaoEntrada.REJEITADA, ComandoEntrada.VALIDAR)


class TestCompetencia:
    def test_periodo_recusa_fim_antes_do_inicio(self) -> None:
        Periodo(inicio=date(2026, 11, 1), fim=date(2026, 11, 1))
        with pytest.raises(ValueError, match="anterior"):
            Periodo(inicio=date(2026, 11, 10), fim=date(2026, 11, 9))

    def test_ajusta_dia_29_a_31_para_ultimo_dia_do_mes(self) -> None:
        assert data_vencimento_da_competencia(Periodicidade.MENSAL, "2026-02", dia_vencimento=31) == date(
            2026, 2, 28
        )
        assert data_vencimento_da_competencia(Periodicidade.MENSAL, "2024-02", dia_vencimento=31) == date(
            2024, 2, 29
        )
        assert data_vencimento_da_competencia(
            Periodicidade.ANUAL, "2026", dia_vencimento=30, mes_vencimento=2
        ) == date(2026, 2, 28)

    def test_CA21_competencia_mensal_antecedencia_10_dias(self) -> None:
        rec = RecorrenciaParaGeracao(
            id=uuid.uuid4(),
            periodicidade=Periodicidade.MENSAL,
            dia_vencimento=10,
            mes_vencimento=None,
            antecedencia_dias=10,
            a_partir_de=date(2026, 11, 1),
        )
        # Dia 30/10 ainda faltam 11 dias -> nada.
        assert competencias_a_gerar(rec, date(2026, 10, 30)) == []
        # A partir de 31/10, como a_partir_de é 01/11, gera 2026-11? Não: no dia 31/10 a_partir_de é 01/11;
        # vencimento 10/11 >= a_partir_de 01/11 e 10/11 - 10d = 31/10 <= 31/10 -> gera 2026-11!
        elegiveis = competencias_a_gerar(rec, date(2026, 10, 31))
        assert [c.codigo for c in elegiveis] == ["2026-11"]
        assert elegiveis[0].vencimento == date(2026, 11, 10)

    def test_CA23_competencias_semanal_e_anual(self) -> None:
        semanal = RecorrenciaParaGeracao(
            id=uuid.uuid4(),
            periodicidade=Periodicidade.SEMANAL,
            dia_vencimento=5,  # sexta-feira ISO
            mes_vencimento=None,
            antecedencia_dias=2,
            a_partir_de=date(2026, 11, 9),
        )
        # 2026-11-13 é sexta da semana W46; antecedência 2 dias = 2026-11-11.
        assert [c.codigo for c in competencias_a_gerar(semanal, date(2026, 11, 11))] == ["2026-W46"]

        anual = RecorrenciaParaGeracao(
            id=uuid.uuid4(),
            periodicidade=Periodicidade.ANUAL,
            dia_vencimento=20,
            mes_vencimento=11,
            antecedencia_dias=5,
            a_partir_de=date(2026, 11, 1),
        )
        assert [c.codigo for c in competencias_a_gerar(anual, date(2026, 11, 15))] == ["2026"]
        assert competencia_da_data(Periodicidade.SEMANAL, date(2026, 11, 13)) == "2026-W46"

    def test_CA26_suspensa_na_data_especifica_e_geral(self) -> None:
        rec_a = uuid.uuid4()
        rec_b = uuid.uuid4()
        suspensoes = [
            SuspensaoParaVerificacao(
                recorrencia_id=rec_a, inicio=date(2026, 11, 1), fim=date(2026, 11, 30), vigente=True
            ),
            SuspensaoParaVerificacao(recorrencia_id=None, inicio=date(2026, 12, 1), fim=None, vigente=True),
        ]
        assert suspensa_na_data(suspensoes, rec_a, date(2026, 11, 10))
        assert not suspensa_na_data(suspensoes, rec_b, date(2026, 11, 10))
        assert suspensa_na_data(suspensoes, rec_b, date(2026, 12, 10))


class TestAutorizacao:
    def test_separacao_de_funcoes_cobranca_e_acoes(self) -> None:
        dev = uuid.uuid4()
        outro = uuid.uuid4()
        fatos_dev = FatosCobranca(
            ator_id=dev,
            ator_admin=True,
            ator_le_gestao=True,
            permissoes_ator=frozenset({"pagamentos.validar", "dividas.decidir", "questionamentos.decidir"}),
            devedor_id=dev,
            situacao=SituacaoCobranca.EM_VALIDACAO,
            tem_questionamento_aberto=False,
            tem_convocacao_aberta=False,
        )
        res = avaliar_cobranca(ComandoCobranca.VALIDAR_PAGAMENTO, fatos_dev)
        assert not res.pode
        assert res.codigo_erro == "DEVEDOR_NAO_VALIDA"
        assert acoes_cobranca_disponiveis(fatos_dev) == []

        fatos_outro = FatosCobranca(
            ator_id=outro,
            ator_admin=False,
            ator_le_gestao=True,
            permissoes_ator=frozenset({"pagamentos.validar"}),
            devedor_id=dev,
            situacao=SituacaoCobranca.EM_VALIDACAO,
            tem_questionamento_aberto=False,
            tem_convocacao_aberta=False,
        )
        assert avaliar_cobranca(ComandoCobranca.VALIDAR_PAGAMENTO, fatos_outro).pode
        assert acoes_cobranca_disponiveis(fatos_outro) == ["validar_pagamento", "rejeitar_pagamento"]

    def test_separacao_de_funcoes_entrada(self) -> None:
        reg = uuid.uuid4()
        val = uuid.uuid4()
        fatos_reg = FatosEntrada(
            ator_id=reg,
            ator_admin=True,
            tem_permissao_validar=True,
            registrada_por_id=reg,
            situacao=SituacaoEntrada.EM_VALIDACAO,
        )
        res = avaliar_entrada(ComandoEntrada.VALIDAR, fatos_reg)
        assert not res.pode
        assert res.codigo_erro == "REGISTRADOR_NAO_VALIDA"
        assert acoes_entrada_disponiveis(fatos_reg) == []

        fatos_val = FatosEntrada(
            ator_id=val,
            ator_admin=False,
            tem_permissao_validar=True,
            registrada_por_id=reg,
            situacao=SituacaoEntrada.EM_VALIDACAO,
        )
        assert acoes_entrada_disponiveis(fatos_val) == ["validar", "rejeitar"]

    def test_visibilidade_comprovante(self) -> None:
        dev, outro = uuid.uuid4(), uuid.uuid4()
        assert pode_ver_comprovante_cobranca(
            ator_id=dev, ator_admin=False, tem_permissao_validar=False, devedor_id=dev
        )
        assert not pode_ver_comprovante_cobranca(
            ator_id=outro, ator_admin=False, tem_permissao_validar=False, devedor_id=dev
        )
        assert pode_ver_comprovante_cobranca(
            ator_id=outro, ator_admin=False, tem_permissao_validar=True, devedor_id=dev
        )
        assert pode_ver_comprovante_entrada(
            ator_id=dev, ator_admin=False, tem_permissao_validar=False, registrada_por_id=dev
        )
        assert not pode_ver_comprovante_entrada(
            ator_id=outro, ator_admin=False, tem_permissao_validar=False, registrada_por_id=dev
        )
