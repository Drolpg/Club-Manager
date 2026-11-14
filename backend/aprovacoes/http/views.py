"""Rotas do motor de aprovações. Só validam a entrada, chamam um serviço e formatam a saída (ADR-004)."""

import uuid
from typing import Any, ClassVar

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from aprovacoes import tipos
from aprovacoes.http.permissions import EhAdmin, LeGestao
from aprovacoes.http.serializers import (
    ConsultaDeMotivosSerializer,
    MotivoSerializer,
    NovoMotivoSerializer,
    TextoDoMotivoSerializer,
    TipoDeDecisaoSerializer,
)
from aprovacoes.services import motivos


def _ator_id(request: Request) -> uuid.UUID:
    """O ID de quem está logado. As permissões da view já garantiram que há um."""
    usuario_id = getattr(request.user, "id", None)
    if usuario_id is None:
        raise NotAuthenticated
    return uuid.UUID(str(usuario_id))


def _validar(serializer: type[Any], dados: Any) -> dict[str, Any]:
    entrada = serializer(data=dados)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


class MotivosView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        return [LeGestao()] if self.request.method == "GET" else [EhAdmin()]

    @extend_schema(
        summary="Motivos de decisão",
        description="Os ativos, por tipo de decisão e texto. `todos=1` traz também os inativos (só o admin).",
        parameters=[ConsultaDeMotivosSerializer],
        responses=MotivoSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        consulta = _validar(ConsultaDeMotivosSerializer, request.query_params)
        lista = motivos.listar(
            _ator_id(request),
            tipo_de_decisao=consulta.get("tipo_de_decisao"),
            incluir_inativos=consulta["todos"],
        )
        return Response(MotivoSerializer(lista, many=True).data)

    @extend_schema(summary="Criar motivo", request=NovoMotivoSerializer, responses={201: MotivoSerializer})
    def post(self, request: Request) -> Response:
        dados = _validar(NovoMotivoSerializer, request.data)
        motivo = motivos.criar(
            ator_id=_ator_id(request), tipo_de_decisao=dados["tipo_de_decisao"], texto=dados["texto"]
        )
        return Response(MotivoSerializer(motivo).data, status=201)


class AcaoDeMotivoView(APIView):
    """Editar, desativar e reativar um motivo; `acao` vem da rota."""

    permission_classes = (EhAdmin,)
    acao: ClassVar[str] = ""

    @extend_schema(request=TextoDoMotivoSerializer, responses=MotivoSerializer)
    def post(self, request: Request, motivo_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        if self.acao == "editar":
            texto = _validar(TextoDoMotivoSerializer, request.data)["texto"]
            motivo = motivos.editar(ator_id=ator_id, motivo_id=motivo_id, texto=texto)
        elif self.acao == "desativar":
            motivo = motivos.desativar(ator_id=ator_id, motivo_id=motivo_id)
        else:
            motivo = motivos.reativar(ator_id=ator_id, motivo_id=motivo_id)
        return Response(MotivoSerializer(motivo).data)


class TiposDeDecisaoView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Tipos de decisão", responses=TipoDeDecisaoSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(TipoDeDecisaoSerializer(tipos.listar_tipos_de_decisao(), many=True).data)
