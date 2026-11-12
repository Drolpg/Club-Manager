import uuid

from django.conf import settings
from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from acesso.http.permissions import EhAdmin, limitar_por_ip
from acesso.http.serializers import (
    ConviteGeradoSerializer,
    ConviteSerializer,
    LoginSerializer,
    SessaoSerializer,
    TokenSerializer,
    UsuarioSerializer,
)
from acesso.models import Convite, Usuario
from acesso.services import convites, sessao


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
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Listar convites", responses=ConviteSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(ConviteSerializer(convites.listar(ator=_ator(request)), many=True).data)

    @extend_schema(summary="Gerar convite", request=None, responses={201: ConviteGeradoSerializer})
    def post(self, request: Request) -> Response:
        convite, token = convites.gerar(ator=_ator(request))
        return Response(_convite_gerado(convite, token), status=201)


class RegenerarConviteView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Regenerar convite", request=None, responses={201: ConviteGeradoSerializer})
    def post(self, request: Request, convite_id: uuid.UUID) -> Response:
        convite, token = convites.regenerar(ator=_ator(request), convite_id=convite_id)
        return Response(_convite_gerado(convite, token), status=201)


class RevogarConviteView(APIView):
    permission_classes = (EhAdmin,)

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
