"""Testes unitários puros do domínio de saídas, gastos, liquidação e estornos (M7)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from financeiro.domain.autorizacao import (
    PERM_FINANCEIRO_ESTORNAR,
    PERM_GASTOS_APROVAR,
    PERM_SAIDAS_ENVIAR,
    PERM_SAIDAS_LIQUIDAR,
    FatosCobranca,
    FatosEntrada,
    FatosSaida,
    acoes_cobranca_disponiveis,
    acoes_entrada_disponiveis,
    acoes_saida_disponiveis,
    avaliar_cobranca,
    avaliar_entrada,
    avaliar_saida,
    pode_ver_anexos_saida,
)
from financeiro.domain.saidas import (
    ErroDeRegraSaida,
    avaliar_lembretes_prestacao,
    avaliar_liquidacao,
    calcular_valor_realizado_saida,
    prestacao_em_atraso,
    validar_devolucao_de_sobra,
    validar_envio_complemento,
    validar_envio_inicial,
    validar_itens_de_gasto,
    validar_pedido_complemento,
)
from financeiro.domain.transicoes import (
    SITUACOES_FINAIS_COBRANCA,
    SITUACOES_FINAIS_SAIDA,
    ComandoCobranca,
    ComandoEntrada,
    ComandoSaida,
    SituacaoCobranca,
    SituacaoEntrada,
    SituacaoSaida,
    transicao_cobranca_permitida,
    transicao_entrada_permitida,
    transicao_saida_permitida,
)


class TestTransicoesSaidaEEstorno:
    def test_matriz_completa_de_transicoes_da_saida(self) -> None:
        permitidas = {
            (SituacaoSaida.AGUARDANDO_ENVIO, ComandoSaida.ENVIAR_RECURSO),
            (SituacaoSaida.AGUARDANDO_ENVIO, ComandoSaida.CANCELAR),
            (SituacaoSaida.RECURSO_ENVIADO, ComandoSaida.ENVIAR_RECURSO),
            (SituacaoSaida.RECURSO_ENVIADO, ComandoSaida.PRESTAR_CONTAS),
            (SituacaoSaida.RECURSO_ENVIADO, ComandoSaida.DEVOLVER_SOBRA),
            (SituacaoSaida.EM_CONFERENCIA, ComandoSaida.ENVIAR_RECURSO),
            (SituacaoSaida.EM_CONFERENCIA, ComandoSaida.DEVOLVER_PRESTACAO),
            (SituacaoSaida.EM_CONFERENCIA, ComandoSaida.DEVOLVER_SOBRA),
            (SituacaoSaida.EM_CONFERENCIA, ComandoSaida.PEDIR_COMPLEMENTO),
            (SituacaoSaida.EM_CONFERENCIA, ComandoSaida.LIQUIDAR),
            (SituacaoSaida.LIQUIDADA, ComandoSaida.ESTORNAR),
        }
        for sit in SituacaoSaida:
            for cmd in ComandoSaida:
                assert transicao_saida_permitida(sit, cmd) is ((sit, cmd) in permitidas)

        assert (
            frozenset({SituacaoSaida.LIQUIDADA, SituacaoSaida.CANCELADA, SituacaoSaida.ESTORNADA})
            == SITUACOES_FINAIS_SAIDA
        )
        for cmd in ComandoSaida:
            assert not transicao_saida_permitida(SituacaoSaida.CANCELADA, cmd)
            assert not transicao_saida_permitida(SituacaoSaida.ESTORNADA, cmd)

    def test_estorno_em_cobranca_e_entrada_sem_estorno_duplo(self) -> None:
        assert SituacaoCobranca.ESTORNADA in SITUACOES_FINAIS_COBRANCA
        assert transicao_cobranca_permitida(SituacaoCobranca.PAGA, ComandoCobranca.ESTORNAR)
        for sit in SituacaoCobranca:
            if sit != SituacaoCobranca.PAGA:
                assert not transicao_cobranca_permitida(sit, ComandoCobranca.ESTORNAR)
        for cmd in ComandoCobranca:
            assert not transicao_cobranca_permitida(SituacaoCobranca.ESTORNADA, cmd)

        assert transicao_entrada_permitida(SituacaoEntrada.VALIDADA, ComandoEntrada.ESTORNAR)
        assert not transicao_entrada_permitida(SituacaoEntrada.EM_VALIDACAO, ComandoEntrada.ESTORNAR)
        assert not transicao_entrada_permitida(SituacaoEntrada.REJEITADA, ComandoEntrada.ESTORNAR)
        for cmd_ent in ComandoEntrada:
            assert not transicao_entrada_permitida(SituacaoEntrada.ESTORNADA, cmd_ent)


class TestRegrasDeSaida:
    def test_CA01_CA02_validar_itens_de_gasto_soma_e_recusa_invalidos(self) -> None:
        itens, total = validar_itens_de_gasto(
            [
                {"descricao": "  Bolas oficiais  ", "valor": "320.50"},
                {"descricao": "Redes", "valor": Decimal("179.50")},
            ]
        )
        assert len(itens) == 2
        assert itens[0].descricao == "Bolas oficiais"
        assert total == Decimal("500.00")

        for invalido in (
            [],
            [{"descricao": "   ", "valor": "10.00"}],
            [{"descricao": "Item", "valor": "0.00"}],
            [{"descricao": "Item", "valor": "-5.00"}],
            [{"descricao": "Item", "valor": "10.123"}],
            [{"descricao": "x" * 161, "valor": "10.00"}],
        ):
            with pytest.raises(ErroDeRegraSaida) as exc:
                validar_itens_de_gasto(invalido)
            assert exc.value.codigo == "VALIDATION_ERROR"
            assert exc.value.campo == "itens"

    def test_D15_CA08_CA09_envio_inicial_e_complemento(self) -> None:
        validar_envio_inicial(
            situacao=SituacaoSaida.AGUARDANDO_ENVIO,
            valor=Decimal("400.00"),
            valor_aprovado=Decimal("500.00"),
            tem_comprovante=True,
        )

        with pytest.raises(ErroDeRegraSaida) as sem_comp:
            validar_envio_inicial(
                situacao=SituacaoSaida.AGUARDANDO_ENVIO,
                valor=Decimal("100.00"),
                valor_aprovado=Decimal("500.00"),
                tem_comprovante=False,
            )
        assert sem_comp.value.codigo == "VALIDATION_ERROR"
        assert sem_comp.value.campo == "comprovante"

        with pytest.raises(ErroDeRegraSaida) as acima:
            validar_envio_inicial(
                situacao=SituacaoSaida.AGUARDANDO_ENVIO,
                valor=Decimal("500.01"),
                valor_aprovado=Decimal("500.00"),
                tem_comprovante=True,
            )
        assert acima.value.codigo == "VALOR_ACIMA_DO_APROVADO"

        with pytest.raises(ErroDeRegraSaida) as segundo_sem_comp:
            validar_envio_inicial(
                situacao=SituacaoSaida.RECURSO_ENVIADO,
                valor=Decimal("50.00"),
                valor_aprovado=Decimal("500.00"),
                tem_comprovante=True,
            )
        assert segundo_sem_comp.value.codigo == "NAO_AGUARDA_ENVIO"

        validar_envio_complemento(
            situacao=SituacaoSaida.EM_CONFERENCIA,
            valor=Decimal("120.00"),
            valor_aprovado=Decimal("500.00"),
            complementos_aprovados=Decimal("120.00"),
            total_ja_enviado=Decimal("500.00"),
            tem_complemento_aprovado_pendente=True,
            tem_comprovante=True,
        )

        with pytest.raises(ErroDeRegraSaida) as acima_saldo:
            validar_envio_complemento(
                situacao=SituacaoSaida.EM_CONFERENCIA,
                valor=Decimal("120.01"),
                valor_aprovado=Decimal("500.00"),
                complementos_aprovados=Decimal("120.00"),
                total_ja_enviado=Decimal("500.00"),
                tem_complemento_aprovado_pendente=True,
                tem_comprovante=True,
            )
        assert acima_saldo.value.codigo == "VALOR_ACIMA_DO_APROVADO"

    def test_CA16_a_CA23_devolucao_complemento_e_liquidacao(self) -> None:
        validar_devolucao_de_sobra(
            situacao=SituacaoSaida.EM_CONFERENCIA,
            valor=Decimal("80.00"),
            total_enviado=Decimal("500.00"),
            total_devolvido_ativo=Decimal("0.00"),
        )
        with pytest.raises(ErroDeRegraSaida) as exc_dev:
            validar_devolucao_de_sobra(
                situacao=SituacaoSaida.EM_CONFERENCIA,
                valor=Decimal("420.01"),
                total_enviado=Decimal("500.00"),
                total_devolvido_ativo=Decimal("80.00"),
            )
        assert exc_dev.value.codigo == "DEVOLUCAO_ACIMA_DO_ENVIADO"

        validar_pedido_complemento(
            situacao=SituacaoSaida.EM_CONFERENCIA,
            valor_prestacao=Decimal("620.00"),
            total_enviado=Decimal("500.00"),
            tem_complemento_em_andamento=False,
        )
        with pytest.raises(ErroDeRegraSaida) as exc_comp:
            validar_pedido_complemento(
                situacao=SituacaoSaida.EM_CONFERENCIA,
                valor_prestacao=Decimal("620.00"),
                total_enviado=Decimal("500.00"),
                tem_complemento_em_andamento=True,
            )
        assert exc_comp.value.codigo == "COMPLEMENTO_JA_EM_ANDAMENTO"

        # Cenário igual (CA-20)
        res_igual = avaliar_liquidacao(
            situacao=SituacaoSaida.EM_CONFERENCIA,
            valor_prestacao=Decimal("500.00"),
            total_enviado=Decimal("500.00"),
            total_devolvido_validado=Decimal("0.00"),
            tem_devolucao_em_validacao=False,
            tem_complemento_em_andamento=False,
            tem_complemento_aprovado_sem_envio=False,
            justificativa="",
        )
        assert res_igual.valor_nao_reembolsado == Decimal("0.00")

        # Cenário menor com devolução validada (CA-21)
        res_menor = avaliar_liquidacao(
            situacao=SituacaoSaida.EM_CONFERENCIA,
            valor_prestacao=Decimal("420.00"),
            total_enviado=Decimal("500.00"),
            total_devolvido_validado=Decimal("80.00"),
            tem_devolucao_em_validacao=False,
            tem_complemento_em_andamento=False,
            tem_complemento_aprovado_sem_envio=False,
            justificativa="",
        )
        assert res_menor.valor_nao_reembolsado == Decimal("0.00")
        assert calcular_valor_realizado_saida(Decimal("500.00"), Decimal("80.00")) == Decimal("420.00")

        # Bloqueio por devolução em validação (CA-21)
        with pytest.raises(ErroDeRegraSaida) as dev_pend:
            avaliar_liquidacao(
                situacao=SituacaoSaida.EM_CONFERENCIA,
                valor_prestacao=Decimal("420.00"),
                total_enviado=Decimal("500.00"),
                total_devolvido_validado=Decimal("0.00"),
                tem_devolucao_em_validacao=True,
                tem_complemento_em_andamento=False,
                tem_complemento_aprovado_sem_envio=False,
                justificativa="",
            )
        assert dev_pend.value.codigo == "DEVOLUCAO_PENDENTE"

        # Cenário maior sem reembolso exige justificativa (CA-23, Decisão 2) e veda devolução prévia
        with pytest.raises(ErroDeRegraSaida) as sem_just:
            avaliar_liquidacao(
                situacao=SituacaoSaida.EM_CONFERENCIA,
                valor_prestacao=Decimal("620.00"),
                total_enviado=Decimal("500.00"),
                total_devolvido_validado=Decimal("0.00"),
                tem_devolucao_em_validacao=False,
                tem_complemento_em_andamento=False,
                tem_complemento_aprovado_sem_envio=False,
                justificativa="   ",
            )
        assert sem_just.value.codigo == "VALIDATION_ERROR"
        assert sem_just.value.campo == "justificativa"

        with pytest.raises(ErroDeRegraSaida) as dev_incomp:
            avaliar_liquidacao(
                situacao=SituacaoSaida.EM_CONFERENCIA,
                valor_prestacao=Decimal("620.00"),
                total_enviado=Decimal("500.00"),
                total_devolvido_validado=Decimal("50.00"),
                tem_devolucao_em_validacao=False,
                tem_complemento_em_andamento=False,
                tem_complemento_aprovado_sem_envio=False,
                justificativa="Sem reembolso",
            )
        assert dev_incomp.value.codigo == "DIFERENCA_NAO_ACERTADA"

        res_maior = avaliar_liquidacao(
            situacao=SituacaoSaida.EM_CONFERENCIA,
            valor_prestacao=Decimal("620.00"),
            total_enviado=Decimal("500.00"),
            total_devolvido_validado=Decimal("0.00"),
            tem_devolucao_em_validacao=False,
            tem_complemento_em_andamento=False,
            tem_complemento_aprovado_sem_envio=False,
            justificativa="Complemento recusado pela diretoria.",
        )
        assert res_maior.valor_nao_reembolsado == Decimal("120.00")

    def test_CA14_lembretes_de_5_e_7_dias_deterministico(self) -> None:
        envio = date(2026, 11, 1)
        d4 = avaliar_lembretes_prestacao(
            situacao=SituacaoSaida.RECURSO_ENVIADO,
            primeiro_envio_em=envio,
            hoje=date(2026, 11, 5),
            lembrete_5_dias_em=None,
            aviso_7_dias_em=None,
        )
        assert (d4.enviar_lembrete_5_dias, d4.enviar_aviso_7_dias) == (False, False)
        assert not prestacao_em_atraso(
            situacao=SituacaoSaida.RECURSO_ENVIADO, primeiro_envio_em=envio, hoje=date(2026, 11, 7)
        )

        d5 = avaliar_lembretes_prestacao(
            situacao=SituacaoSaida.RECURSO_ENVIADO,
            primeiro_envio_em=envio,
            hoje=date(2026, 11, 6),
            lembrete_5_dias_em=None,
            aviso_7_dias_em=None,
        )
        assert (d5.enviar_lembrete_5_dias, d5.enviar_aviso_7_dias) == (True, False)

        d7 = avaliar_lembretes_prestacao(
            situacao=SituacaoSaida.RECURSO_ENVIADO,
            primeiro_envio_em=envio,
            hoje=date(2026, 11, 8),
            lembrete_5_dias_em=date(2026, 11, 6),
            aviso_7_dias_em=None,
        )
        assert (d7.enviar_lembrete_5_dias, d7.enviar_aviso_7_dias) == (False, True)
        assert prestacao_em_atraso(
            situacao=SituacaoSaida.RECURSO_ENVIADO, primeiro_envio_em=envio, hoje=date(2026, 11, 8)
        )

        # Em conferência ou já avisado -> não dispara
        d7_dup = avaliar_lembretes_prestacao(
            situacao=SituacaoSaida.RECURSO_ENVIADO,
            primeiro_envio_em=envio,
            hoje=date(2026, 11, 8),
            lembrete_5_dias_em=date(2026, 11, 6),
            aviso_7_dias_em=date(2026, 11, 8),
        )
        assert (d7_dup.enviar_lembrete_5_dias, d7_dup.enviar_aviso_7_dias) == (False, False)


class TestAutorizacaoSaidaEEstorno:
    def test_codigos_de_permissao_e_segregacao_na_saida(self) -> None:
        assert {
            PERM_GASTOS_APROVAR,
            PERM_SAIDAS_ENVIAR,
            PERM_SAIDAS_LIQUIDAR,
            PERM_FINANCEIRO_ESTORNAR,
        } == {"gastos.aprovar", "saidas.enviar", "saidas.liquidar", "financeiro.estornar"}

        sol = uuid.uuid4()
        fin = uuid.uuid4()

        fatos_sol_conf = FatosSaida(
            ator_id=sol,
            ator_admin=True,
            ator_le_gestao=True,
            permissoes_ator=frozenset({PERM_SAIDAS_LIQUIDAR, PERM_FINANCEIRO_ESTORNAR}),
            solicitante_id=sol,
            situacao=SituacaoSaida.EM_CONFERENCIA,
            tem_excesso_para_complemento=True,
        )
        dec_liq = avaliar_saida(ComandoSaida.LIQUIDAR, fatos_sol_conf)
        assert not dec_liq.pode
        assert dec_liq.codigo_erro == "SOLICITANTE_NAO_LIQUIDA"
        assert acoes_saida_disponiveis(fatos_sol_conf) == ["devolver_sobra", "pedir_complemento"]

        fatos_terceiro = FatosSaida(
            ator_id=fin,
            ator_admin=False,
            ator_le_gestao=True,
            permissoes_ator=frozenset({PERM_SAIDAS_LIQUIDAR}),
            solicitante_id=sol,
            situacao=SituacaoSaida.EM_CONFERENCIA,
        )
        assert avaliar_saida(ComandoSaida.PRESTAR_CONTAS, fatos_terceiro).codigo_erro == "SO_O_SOLICITANTE"
        assert acoes_saida_disponiveis(fatos_terceiro) == ["devolver_prestacao", "liquidar"]
        assert pode_ver_anexos_saida(ator_le_gestao=True, ator_admin=False)
        assert not pode_ver_anexos_saida(ator_le_gestao=False, ator_admin=False)

    def test_estorno_cobranca_e_entrada_em_autorizacao(self) -> None:
        admin_id = uuid.uuid4()
        comum_id = uuid.uuid4()
        reg_id = uuid.uuid4()
        dev_id = uuid.uuid4()

        fatos_cob_admin = FatosCobranca(
            ator_id=admin_id,
            ator_admin=True,
            ator_le_gestao=True,
            permissoes_ator=frozenset(),
            devedor_id=dev_id,
            situacao=SituacaoCobranca.PAGA,
            tem_questionamento_aberto=False,
            tem_convocacao_aberta=False,
        )
        assert avaliar_cobranca(ComandoCobranca.ESTORNAR, fatos_cob_admin).pode
        assert acoes_cobranca_disponiveis(fatos_cob_admin) == ["estornar"]

        fatos_cob_sem = FatosCobranca(
            ator_id=comum_id,
            ator_admin=False,
            ator_le_gestao=True,
            permissoes_ator=frozenset({"cobrancas.criar"}),
            devedor_id=dev_id,
            situacao=SituacaoCobranca.PAGA,
            tem_questionamento_aberto=False,
            tem_convocacao_aberta=False,
        )
        assert not avaliar_cobranca(ComandoCobranca.ESTORNAR, fatos_cob_sem).pode
        assert acoes_cobranca_disponiveis(fatos_cob_sem) == []

        fatos_ent_estorno = FatosEntrada(
            ator_id=comum_id,
            ator_admin=False,
            tem_permissao_validar=False,
            registrada_por_id=reg_id,
            situacao=SituacaoEntrada.VALIDADA,
            tem_permissao_estornar=True,
            ator_le_gestao=True,
            saida_liquidada=False,
        )
        assert avaliar_entrada(ComandoEntrada.ESTORNAR, fatos_ent_estorno).pode
        assert acoes_entrada_disponiveis(fatos_ent_estorno) == ["estornar"]

        fatos_ent_liq = FatosEntrada(
            ator_id=admin_id,
            ator_admin=True,
            tem_permissao_validar=True,
            registrada_por_id=reg_id,
            situacao=SituacaoEntrada.VALIDADA,
            saida_liquidada=True,
        )
        assert acoes_entrada_disponiveis(fatos_ent_liq) == []
