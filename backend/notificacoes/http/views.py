"""Rotas da caixa de entrada e das preferências. Todas são do usuário logado e só mostram o que é dele.

Não há rota que apague notificação nem que desligue o registro (RN 1, RN 3).
"""

import uuid
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from notificacoes.http.serializers import (
    ConsultaDaCaixaSerializer,
    ItemSerializer,
    MarcadasSerializer,
    PaginaSerializer,
    PreferenciasEntradaSerializer,
    PreferenciasSerializer,
    ResumoSerializer,
)
from notificacoes.services import consulta, preferencias


def _usuario_id(request: Request) -> uuid.UUID:
    """O ID de quem está logado. A permissão da view já garantiu que há um."""
    usuario_id = getattr(request.user, "id", None)
    if usuario_id is None:
        raise NotAuthenticated
    return uuid.UUID(str(usuario_id))


def _validar(serializer: type[Any], dados: Any) -> dict[str, Any]:
    entrada = serializer(data=dados)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


class CaixaView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Caixa de entrada",
        description="As notificações do usuário, da mais recente para a mais antiga. `antes` é o ID da "
        "última recebida; `limite` vai de 1 a 50 (padrão 20).",
        parameters=[ConsultaDaCaixaSerializer],
        responses=PaginaSerializer,
    )
    def get(self, request: Request) -> Response:
        parametros = _validar(ConsultaDaCaixaSerializer, request.query_params)
        pagina = consulta.listar(
            _usuario_id(request), antes=parametros.get("antes"), limite=parametros["limite"]
        )
        return Response(PaginaSerializer(pagina).data)


class ResumoView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(summary="Quantidade de não lidas e a última que chegou", responses=ResumoSerializer)
    def get(self, request: Request) -> Response:
        return Response(ResumoSerializer(consulta.resumo(_usuario_id(request))).data)


class LerView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(summary="Abrir (marcar como lida) uma notificação", request=None, responses=ItemSerializer)
    def post(self, request: Request, notificacao_id: uuid.UUID) -> Response:
        return Response(ItemSerializer(consulta.ler(_usuario_id(request), notificacao_id)).data)


class LerTodasView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(summary="Marcar todas como lidas", request=None, responses=MarcadasSerializer)
    def post(self, request: Request) -> Response:
        return Response(MarcadasSerializer({"marcadas": consulta.ler_todas(_usuario_id(request))}).data)


class PreferenciasView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(summary="Minhas preferências de alerta", responses=PreferenciasSerializer)
    def get(self, request: Request) -> Response:
        return Response(PreferenciasSerializer(preferencias.obter(_usuario_id(request))).data)

    @extend_schema(
        summary="Alterar minhas preferências de alerta",
        description="Só as chaves enviadas mudam. Nenhuma desliga o registro da notificação.",
        request=PreferenciasEntradaSerializer,
        responses=PreferenciasSerializer,
    )
    def put(self, request: Request) -> Response:
        dados = _validar(PreferenciasEntradaSerializer, request.data)
        atuais = preferencias.alterar(_usuario_id(request), **dados)
        return Response(PreferenciasSerializer(atuais).data)
