import uuid

from permissoes.domain.resolucao import (
    ACESSO_TOTAL,
    Fatos,
    Grupo,
    TipoDeOrigem,
    resolver_permissoes,
)

CATALOGO = {
    "convites.gerenciar": False,
    "pagamentos.validar": False,
    "solicitacoes.auto_aprovar": True,
    ACESSO_TOTAL: False,
}


def _grupo(nome: str, *permissoes: str, ativo: bool = True) -> Grupo:
    return Grupo(id=uuid.uuid7(), nome=nome, ativo=ativo, permissoes=frozenset(permissoes))


def _fatos(**extra: object) -> Fatos:
    base: dict[str, object] = {
        "ativo": True,
        "admin": False,
        "catalogo": CATALOGO,
        "cargo": None,
        "setores": (),
        "individuais": frozenset(),
    }
    base.update(extra)
    return Fatos(**base)  # type: ignore[arg-type]


def _tipos(resultado: dict[str, list], codigo: str) -> list[str]:  # type: ignore[type-arg]
    return [origem.tipo for origem in resultado.get(codigo, [])]


def test_sem_concessao_nao_ha_permissao_nenhuma() -> None:
    assert resolver_permissoes(_fatos()) == {}


def test_per_r01_usuario_inativo_nao_tem_permissao_mesmo_com_concessoes() -> None:
    fatos = _fatos(
        ativo=False,
        admin=True,
        cargo=_grupo("Tesoureiro", "pagamentos.validar"),
        individuais=frozenset({"convites.gerenciar", ACESSO_TOTAL}),
    )

    assert resolver_permissoes(fatos) == {}


def test_per_r02_admin_tem_tudo_do_catalogo_inclusive_o_que_fica_fora_do_acesso_total() -> None:
    resultado = resolver_permissoes(_fatos(admin=True))

    assert set(resultado) == {"convites.gerenciar", "pagamentos.validar", "solicitacoes.auto_aprovar"}
    assert _tipos(resultado, "solicitacoes.auto_aprovar") == [TipoDeOrigem.ADMIN]


def test_per_r03_permissao_vem_do_cargo() -> None:
    cargo = _grupo("Tesoureiro", "pagamentos.validar")

    resultado = resolver_permissoes(_fatos(cargo=cargo))

    assert set(resultado) == {"pagamentos.validar"}
    origem = resultado["pagamentos.validar"][0]
    assert (origem.tipo, origem.id, origem.nome) == (TipoDeOrigem.CARGO, cargo.id, "Tesoureiro")


def test_per_r03_permissao_vem_de_um_setor() -> None:
    resultado = resolver_permissoes(
        _fatos(cargo=_grupo("Diretor"), setores=(_grupo("Financeiro", "pagamentos.validar"),))
    )

    assert _tipos(resultado, "pagamentos.validar") == [TipoDeOrigem.SETOR]


def test_per_r03_permissao_individual() -> None:
    resultado = resolver_permissoes(_fatos(individuais=frozenset({"convites.gerenciar"})))

    assert _tipos(resultado, "convites.gerenciar") == [TipoDeOrigem.INDIVIDUAL]


def test_per_r03_as_tres_origens_se_somam_e_todas_aparecem() -> None:
    fatos = _fatos(
        cargo=_grupo("Tesoureiro", "pagamentos.validar"),
        setores=(_grupo("Financeiro", "pagamentos.validar"), _grupo("Eventos", "convites.gerenciar")),
        individuais=frozenset({"pagamentos.validar"}),
    )

    resultado = resolver_permissoes(fatos)

    assert _tipos(resultado, "pagamentos.validar") == [
        TipoDeOrigem.CARGO,
        TipoDeOrigem.SETOR,
        TipoDeOrigem.INDIVIDUAL,
    ]
    assert _tipos(resultado, "convites.gerenciar") == [TipoDeOrigem.SETOR]


def test_cargo_inativo_nao_concede() -> None:
    fatos = _fatos(cargo=_grupo("Tesoureiro", "pagamentos.validar", ativo=False))

    assert resolver_permissoes(fatos) == {}


def test_setor_inativo_nao_concede_mas_os_outros_sim() -> None:
    fatos = _fatos(
        cargo=_grupo("Diretor"),
        setores=(
            _grupo("Financeiro", "pagamentos.validar", ativo=False),
            _grupo("Eventos", "convites.gerenciar"),
        ),
    )

    assert set(resolver_permissoes(fatos)) == {"convites.gerenciar"}


def test_per_r04_acesso_total_da_tudo_menos_o_que_fica_fora_dele() -> None:
    resultado = resolver_permissoes(_fatos(individuais=frozenset({ACESSO_TOTAL})))

    assert set(resultado) == {"convites.gerenciar", "pagamentos.validar"}
    assert _tipos(resultado, "pagamentos.validar") == [TipoDeOrigem.ACESSO_TOTAL]


def test_per_r04_quem_tem_acesso_total_pode_receber_a_permissao_de_fora_por_concessao_propria() -> None:
    fatos = _fatos(individuais=frozenset({ACESSO_TOTAL, "solicitacoes.auto_aprovar"}))

    resultado = resolver_permissoes(fatos)

    assert _tipos(resultado, "solicitacoes.auto_aprovar") == [TipoDeOrigem.INDIVIDUAL]


def test_acesso_total_nunca_aparece_como_permissao_no_resultado() -> None:
    for fatos in (_fatos(admin=True), _fatos(individuais=frozenset({ACESSO_TOTAL}))):
        assert ACESSO_TOTAL not in resolver_permissoes(fatos)


def test_per_r05_codigo_fora_do_catalogo_e_ignorado() -> None:
    fatos = _fatos(
        cargo=_grupo("Tesoureiro", "permissao.que.saiu"),
        individuais=frozenset({"outra.que.saiu"}),
    )

    assert resolver_permissoes(fatos) == {}


def test_acesso_total_concedido_a_cargo_ou_setor_nao_vale() -> None:
    fatos = _fatos(cargo=_grupo("Presidente", ACESSO_TOTAL), setores=(_grupo("Financeiro", ACESSO_TOTAL),))

    assert resolver_permissoes(fatos) == {}
