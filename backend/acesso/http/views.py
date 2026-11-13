import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpRequest
from django.http.response import HttpResponseBase
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView

from acesso import portas
from acesso.http.permissions import EhAdmin, PodeGerenciarConvites, limitar_por_ip
from acesso.http.serializers import (
    CadastroGoogleSerializer,
    CadastroSerializer,
    ConfiguracaoSerializer,
    ConviteGeradoSerializer,
    ConviteSerializer,
    CredencialGoogleSerializer,
    EmailSerializer,
    HistoricoSerializer,
    IdentificadorSerializer,
    LoginSerializer,
    RedefinirSenhaSerializer,
    SessaoSerializer,
    SituacaoSerializer,
    TokenSerializer,
    UsuarioSerializer,
)
from acesso.models import Convite, Usuario
from acesso.services import cadastro, convites, historico, senha, sessao, usuarios
from acesso.services import google as servico_google


def _ator(request: Request) -> Usuario:
    """O usuário logado. As permissões da view já garantiram que há um."""
    if not isinstance(request.user, Usuario):
        raise NotAuthenticated
    return request.user


def _sessao(usuario: Usuario | None) -> dict[str, object]:
    return {"usuario": UsuarioSerializer(usuario).data if usuario else None}


class SessaoView(APIView):
    """A sessão de quem está usando o site: consultar, entrar e sair."""

    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "DELETE":
            return [IsAuthenticated()]
        return [AllowAny()]

    @extend_schema(summary="Quem está logado", responses=SessaoSerializer, auth=[])
    @method_decorator(ensure_csrf_cookie)
    def get(self, request: Request) -> Response:
        usuario = request.user if isinstance(request.user, Usuario) else None
        return Response(_sessao(usuario))

    @extend_schema(summary="Entrar com senha", request=LoginSerializer, responses=SessaoSerializer, auth=[])
    @method_decorator(csrf_protect)
    def post(self, request: Request) -> Response:
        limitar_por_ip(request)
        entrada = LoginSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        usuario = sessao.autenticar(**entrada.validated_data)
        # `login` troca a chave da sessão, o que impede fixação de sessão.
        login(request._request, usuario)
        return Response(_sessao(usuario))

    @extend_schema(summary="Sair", responses={204: None})
    def delete(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=204)


def _convite_gerado(convite: Convite, token: str) -> dict[str, object]:
    dados = dict(ConviteSerializer(convite).data)
    # O site lê o token do endereço e o envia no corpo; a API nunca recebe o token na URL.
    dados["link"] = f"{settings.SITE_URL}/convite/{token}"
    return dados


class ConvitesView(APIView):
    permission_classes = (PodeGerenciarConvites,)

    @extend_schema(summary="Listar convites", responses=ConviteSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(ConviteSerializer(convites.listar(ator=_ator(request)), many=True).data)

    @extend_schema(summary="Gerar convite", request=None, responses={201: ConviteGeradoSerializer})
    def post(self, request: Request) -> Response:
        convite, token = convites.gerar(ator=_ator(request))
        return Response(_convite_gerado(convite, token), status=201)


class RegenerarConviteView(APIView):
    permission_classes = (PodeGerenciarConvites,)

    @extend_schema(summary="Regenerar convite", request=None, responses={201: ConviteGeradoSerializer})
    def post(self, request: Request, convite_id: uuid.UUID) -> Response:
        convite, token = convites.regenerar(ator=_ator(request), convite_id=convite_id)
        return Response(_convite_gerado(convite, token), status=201)


class RevogarConviteView(APIView):
    permission_classes = (PodeGerenciarConvites,)

    @extend_schema(summary="Revogar convite", request=None, responses=ConviteSerializer)
    def post(self, request: Request, convite_id: uuid.UUID) -> Response:
        convite = convites.revogar(ator=_ator(request), convite_id=convite_id)
        return Response(ConviteSerializer(convite).data)


class ConsultarConviteView(APIView):
    """Diz ao site se um link de convite ainda vale, antes de mostrar o formulário de cadastro."""

    permission_classes = (AllowAny,)

    @extend_schema(summary="Consultar convite", request=TokenSerializer, responses={204: None}, auth=[])
    @method_decorator(csrf_protect)
    def post(self, request: Request) -> Response:
        limitar_por_ip(request)
        entrada = TokenSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        convites.consultar(token=entrada.validated_data["token"])
        return Response(status=204)


class RotaAbertaDeEscrita(APIView):
    """Base das rotas que qualquer pessoa pode chamar: exigem o token CSRF e contam para o limite por IP."""

    permission_classes = (AllowAny,)

    @method_decorator(csrf_protect)
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        return super().dispatch(request, *args, **kwargs)

    def validar(self, request: Request, serializer: type[Serializer[Any]]) -> dict[str, Any]:
        limitar_por_ip(request)
        entrada = serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        return dict(entrada.validated_data)


class CadastrosView(RotaAbertaDeEscrita):
    @extend_schema(
        summary="Cadastrar-se pelo convite",
        request=CadastroSerializer,
        responses={201: SituacaoSerializer},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        usuario = cadastro.cadastrar(**self.validar(request, CadastroSerializer))
        return Response({"situacao": usuario.situacao}, status=201)


class VerificacoesView(RotaAbertaDeEscrita):
    @extend_schema(summary="Verificar o e-mail", request=TokenSerializer, responses={204: None}, auth=[])
    def post(self, request: Request) -> Response:
        cadastro.verificar(token=self.validar(request, TokenSerializer)["token"])
        return Response(status=204)


class ReenviarVerificacaoView(RotaAbertaDeEscrita):
    @extend_schema(
        summary="Reenviar o link de verificação",
        description="Responde sempre 204, exista a conta ou não.",
        request=IdentificadorSerializer,
        responses={204: None},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        dados = self.validar(request, IdentificadorSerializer)
        cadastro.reenviar_verificacao(identificador=dados["identificador"])
        return Response(status=204)


class RecuperarSenhaView(RotaAbertaDeEscrita):
    @extend_schema(
        summary="Pedir a recuperação de senha",
        description="Responde sempre 204, exista a conta ou não.",
        request=EmailSerializer,
        responses={204: None},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        senha.pedir_recuperacao(email=self.validar(request, EmailSerializer)["email"])
        return Response(status=204)


class RedefinirSenhaView(RotaAbertaDeEscrita):
    @extend_schema(
        summary="Redefinir a senha", request=RedefinirSenhaSerializer, responses={204: None}, auth=[]
    )
    def post(self, request: Request) -> Response:
        senha.redefinir(**self.validar(request, RedefinirSenhaSerializer))
        return Response(status=204)


class UsuariosView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Listar usuários", responses=UsuarioSerializer(many=True))
    def get(self, request: Request) -> Response:
        lista = usuarios.listar(ator=_ator(request))
        # Uma consulta à porta para a lista inteira, e não uma por usuário.
        com_cargo = portas.usuarios_com_cargo([u.id for u in lista])
        return Response(UsuarioSerializer(lista, many=True, context={"com_cargo": com_cargo}).data)


_ACOES_DE_USUARIO = {
    "desativar": usuarios.desativar,
    "reativar": usuarios.reativar,
    "tornar-admin": usuarios.tornar_admin,
    "remover-admin": usuarios.remover_admin,
}


class AcaoDeUsuarioView(APIView):
    """Desativar, reativar, dar e tirar o papel de admin. A ação vem da rota (`acao`)."""

    permission_classes = (EhAdmin,)
    acao = ""

    @extend_schema(request=None, responses=UsuarioSerializer)
    def post(self, request: Request, usuario_id: uuid.UUID) -> Response:
        usuario = _ACOES_DE_USUARIO[self.acao](ator=_ator(request), usuario_id=usuario_id)
        return Response(UsuarioSerializer(usuario).data)


class SessaoGoogleView(RotaAbertaDeEscrita):
    @extend_schema(
        summary="Entrar com o Google", request=CredencialGoogleSerializer, responses=SessaoSerializer, auth=[]
    )
    def post(self, request: Request) -> Response:
        dados = self.validar(request, CredencialGoogleSerializer)
        usuario = servico_google.entrar(credencial=dados["credencial"])
        login(request._request, usuario)
        return Response(_sessao(usuario))


class CadastroGoogleView(RotaAbertaDeEscrita):
    @extend_schema(
        summary="Cadastrar-se pelo convite com o Google",
        request=CadastroGoogleSerializer,
        responses={201: SessaoSerializer},
        auth=[],
    )
    def post(self, request: Request) -> Response:
        usuario = servico_google.cadastrar(**self.validar(request, CadastroGoogleSerializer))
        login(request._request, usuario)
        return Response(_sessao(usuario), status=201)


class ConfiguracaoView(APIView):
    """O que o site precisa saber antes do login. Não traz nada sensível."""

    permission_classes = (AllowAny,)

    @extend_schema(summary="Configuração pública do acesso", responses=ConfiguracaoSerializer, auth=[])
    def get(self, request: Request) -> Response:
        return Response({"google_client_id": settings.GOOGLE_CLIENT_ID or None})


class HistoricoDoUsuarioView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Histórico de um usuário", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, usuario_id: uuid.UUID) -> Response:
        registros = historico.do_usuario(ator=_ator(request), usuario_id=usuario_id)
        return Response(HistoricoSerializer(registros, many=True).data)


class HistoricoDoConviteView(APIView):
    permission_classes = (PodeGerenciarConvites,)

    @extend_schema(summary="Histórico de um convite", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, convite_id: uuid.UUID) -> Response:
        registros = historico.do_convite(ator=_ator(request), convite_id=convite_id)
        return Response(HistoricoSerializer(registros, many=True).data)
