"""Entrar com senha (RF-006)."""

from django.db.models import Q

from acesso.domain.identificacao import normalizar_email
from acesso.models import Situacao, Usuario
from kernel import rate_limit
from kernel.errors import BusinessError

# 5 tentativas erradas em 15 minutos bloqueiam temporariamente o login da conta (funcional, P4).
LIMITE_DE_TENTATIVAS = 5
JANELA_DE_TENTATIVAS = 15 * 60
_ESCOPO = "login"


def _credenciais_invalidas() -> BusinessError:
    # A mesma resposta para conta inexistente, senha errada e conta inativa (RN-025).
    return BusinessError("CREDENCIAIS_INVALIDAS", "Usuário ou senha inválidos.", status=401)


def _chave_da_conta(identificador: str, usuario: Usuario | None) -> str:
    # Nome de usuário e e-mail da mesma conta contam juntos; conta inexistente conta pelo que foi digitado.
    return str(usuario.id) if usuario else identificador


def autenticar(*, identificador: str, senha: str) -> Usuario:
    """Devolve o usuário ativo dono das credenciais, ou levanta o erro correspondente."""
    identificador = normalizar_email(identificador)
    usuario = Usuario.objects.filter(
        Q(nome_de_usuario__iexact=identificador) | Q(email__iexact=identificador)
    ).first()
    chave = _chave_da_conta(identificador, usuario)

    if rate_limit.exceeded(_ESCOPO, chave, limit=LIMITE_DE_TENTATIVAS):
        raise BusinessError(
            "MUITAS_TENTATIVAS", "Muitas tentativas. Espere alguns minutos e tente de novo.", status=429
        )

    if usuario is None:
        # Calcula um hash mesmo assim, para o tempo de resposta não revelar que a conta não existe.
        Usuario().set_password(senha)
        rate_limit.hit(_ESCOPO, chave, window=JANELA_DE_TENTATIVAS)
        raise _credenciais_invalidas()

    if not usuario.check_password(senha):
        rate_limit.hit(_ESCOPO, chave, window=JANELA_DE_TENTATIVAS)
        raise _credenciais_invalidas()

    if usuario.situacao == Situacao.AGUARDANDO_VERIFICACAO:
        raise BusinessError("EMAIL_NAO_VERIFICADO", "Falta verificar o seu e-mail para entrar.", status=403)
    if usuario.situacao != Situacao.ATIVO:
        raise _credenciais_invalidas()

    rate_limit.reset(_ESCOPO, chave)
    return usuario
