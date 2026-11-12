from datetime import UTC, datetime, timedelta

from acesso.domain.convite import VALIDADE, SituacaoDoConvite, situacao_do_convite

GERADO = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)
EXPIRA = GERADO + VALIDADE


def _situacao(agora: datetime, usado: datetime | None = None, revogado: datetime | None = None) -> str:
    return situacao_do_convite(agora=agora, expira_em=EXPIRA, usado_em=usado, revogado_em=revogado)


def test_convite_vale_por_24_horas() -> None:
    assert timedelta(hours=24) == VALIDADE


def test_convite_dentro_do_prazo_esta_ativo() -> None:
    assert _situacao(EXPIRA - timedelta(seconds=1)) == SituacaoDoConvite.ATIVO


def test_convite_expira_exatamente_no_fim_do_prazo() -> None:
    assert _situacao(EXPIRA) == SituacaoDoConvite.EXPIRADO
    assert _situacao(EXPIRA + timedelta(days=30)) == SituacaoDoConvite.EXPIRADO


def test_convite_usado_continua_usado_depois_do_prazo() -> None:
    assert _situacao(EXPIRA + timedelta(days=1), usado=GERADO) == SituacaoDoConvite.USADO


def test_convite_revogado_continua_revogado_depois_do_prazo() -> None:
    assert _situacao(EXPIRA + timedelta(days=1), revogado=GERADO) == SituacaoDoConvite.REVOGADO


def test_usado_tem_precedencia_sobre_revogado() -> None:
    assert _situacao(GERADO, usado=GERADO, revogado=GERADO) == SituacaoDoConvite.USADO
