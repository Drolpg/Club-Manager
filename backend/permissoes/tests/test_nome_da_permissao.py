"""`nome_da_permissao`: o nome do catálogo, para quem monta texto sobre uma permissão (`notificacoes`)."""

from permissoes import public
from permissoes.catalogo import CONVITES_GERENCIAR
from permissoes.domain.resolucao import ACESSO_TOTAL


def test_devolve_o_nome_de_uma_permissao_do_catalogo() -> None:
    assert public.nome_da_permissao(CONVITES_GERENCIAR) == "Gerenciar convites"
    assert public.nome_da_permissao(ACESSO_TOTAL) == "Acesso total"


def test_permissao_que_o_catalogo_nao_conhece_devolve_nada() -> None:
    assert public.nome_da_permissao("nao.existe") is None
