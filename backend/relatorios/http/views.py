"""Rotas do perfil e do dashboard (`/api/v1/relatorios/...`). Só leitura e sem regra de negócio (ADR-004).

A classe de permissão exige só a sessão ativa; quem pode ver e a auditoria são do serviço. A ordem é sessão
(401) → quem pode ver (403) → entrada (400) → existência (404).
"""

import uuid
from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, PolymorphicProxySerializer, extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from relatorios.http.permissoes import UsuarioAtivo
from relatorios.http.serializers import (
    DashboardBasicoSerializer,
    DashboardCompletoSerializer,
    PaginaDeCobrancasSerializer,
    PaginaDeEventosSerializer,
    PerfilSerializer,
)
from relatorios.services import dashboard, perfil

_PARAMETROS = [
    OpenApiParameter("antes", OpenApiTypes.UUID, description="ID do último item da página anterior"),
    OpenApiParameter("limite", OpenApiTypes.INT, description="De 1 a 50; padrão 10"),
]


def _ator_id(request: Request) -> uuid.UUID:
    raw_id = getattr(request.user, "id", None)
    if raw_id is None:
        raise NotAuthenticated
    return uuid.UUID(str(raw_id))


def _pagina(request: Request) -> dict[str, Any]:
    """Cursor e limite da consulta. O que não se lê vira valor que o serviço recusa, depois do 403."""
    dados: dict[str, Any] = {}
    bruto = request.query_params.get("limite")
    if bruto is not None:
        try:
            dados["limite"] = int(bruto)
        except ValueError:
            dados["limite"] = 0
    antes = request.query_params.get("antes")
    if antes is not None:
        try:
            dados["antes"] = uuid.UUID(antes)
        except ValueError:
            dados["antes"] = uuid.UUID(int=0)
    return dados


def _perfil(ator_id: uuid.UUID, alvo_id: uuid.UUID) -> Response:
    corpo = dict(PerfilSerializer(perfil.perfil(ator_id, alvo_id)).data)
    if corpo.get("notificacoes") is None:
        corpo.pop("notificacoes", None)
    return Response(corpo)


class MeuPerfilView(APIView):
    permission_classes = (UsuarioAtivo,)

    @extend_schema(summary="O próprio perfil", responses=PerfilSerializer)
    def get(self, request: Request) -> Response:
        ator_id = _ator_id(request)
        return _perfil(ator_id, ator_id)


class PerfilView(APIView):
    permission_classes = (UsuarioAtivo,)

    @extend_schema(summary="O perfil do dono ou, para o admin, de outro usuário", responses=PerfilSerializer)
    def get(self, request: Request, usuario_id: uuid.UUID) -> Response:
        return _perfil(_ator_id(request), usuario_id)


class MinhasCobrancasView(APIView):
    permission_classes = (UsuarioAtivo,)

    @extend_schema(
        summary="Próxima página das próprias cobranças",
        parameters=_PARAMETROS,
        responses=PaginaDeCobrancasSerializer,
    )
    def get(self, request: Request) -> Response:
        ator_id = _ator_id(request)
        pagina = perfil.cobrancas(ator_id, ator_id, **_pagina(request))
        return Response(PaginaDeCobrancasSerializer(pagina).data)


class CobrancasDoUsuarioView(APIView):
    permission_classes = (UsuarioAtivo,)

    @extend_schema(
        summary="Página das cobranças de um usuário",
        parameters=_PARAMETROS,
        responses=PaginaDeCobrancasSerializer,
    )
    def get(self, request: Request, usuario_id: uuid.UUID) -> Response:
        pagina = perfil.cobrancas(_ator_id(request), usuario_id, **_pagina(request))
        return Response(PaginaDeCobrancasSerializer(pagina).data)


class MeusEventosView(APIView):
    permission_classes = (UsuarioAtivo,)

    @extend_schema(
        summary="Próxima página dos próprios eventos",
        parameters=_PARAMETROS,
        responses=PaginaDeEventosSerializer,
    )
    def get(self, request: Request) -> Response:
        ator_id = _ator_id(request)
        pagina = perfil.eventos(ator_id, ator_id, **_pagina(request))
        return Response(PaginaDeEventosSerializer(pagina).data)


class EventosDoUsuarioView(APIView):
    permission_classes = (UsuarioAtivo,)

    @extend_schema(
        summary="Página dos eventos de um usuário",
        parameters=_PARAMETROS,
        responses=PaginaDeEventosSerializer,
    )
    def get(self, request: Request, usuario_id: uuid.UUID) -> Response:
        pagina = perfil.eventos(_ator_id(request), usuario_id, **_pagina(request))
        return Response(PaginaDeEventosSerializer(pagina).data)


def _mes(dia: Any) -> str:
    return f"{dia.year:04d}-{dia.month:02d}"


def _dashboard(resultado: dashboard.DashboardCompleto | dashboard.DashboardBasico) -> dict[str, Any]:
    if isinstance(resultado, dashboard.DashboardBasico):
        basico = {
            "tipo": "BASICO",
            "classificacao_pendente": True,
            "minhas_cobrancas": resultado.minhas_cobrancas,
            "notificacoes_nao_lidas": resultado.notificacoes_nao_lidas,
        }
        return dict(DashboardBasicoSerializer(basico).data)
    completo = {
        "tipo": "COMPLETO",
        "mes": _mes(resultado.mes),
        "meses": {"de": _mes(resultado.primeiro_mes), "ate": _mes(resultado.ultimo_mes)},
        "do_mes": resultado.do_mes,
        "hoje": resultado.hoje,
        "proximos_eventos": resultado.proximos_eventos,
        "ultimos_comunicados": resultado.ultimos_comunicados,
        "minhas_cobrancas": resultado.minhas_cobrancas,
    }
    return dict(DashboardCompletoSerializer(completo).data)


class DashboardView(APIView):
    """O completo para quem lê os dados de gestão; o básico para o ativo sem cargo (RF-102, RF-103)."""

    permission_classes = (UsuarioAtivo,)

    @extend_schema(
        summary="O dashboard: completo ou básico, conforme quem pede",
        parameters=[OpenApiParameter("mes", OpenApiTypes.STR, description="AAAA-MM; padrão, o corrente")],
        responses=PolymorphicProxySerializer(
            component_name="Dashboard",
            serializers=[DashboardCompletoSerializer, DashboardBasicoSerializer],
            resource_type_field_name="tipo",
        ),
    )
    def get(self, request: Request) -> Response:
        return Response(_dashboard(dashboard.dashboard(_ator_id(request), request.query_params.get("mes"))))
