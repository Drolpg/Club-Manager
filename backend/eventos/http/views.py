"""Rotas HTTP de `eventos` (`/api/v1/eventos/...`). Sem regra de negócio: validam a entrada, chamam um
serviço e formatam a saída (ADR-004). Toda rota declara a classe de permissão.
"""

import uuid
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from eventos.domain.autorizacao import PERM_APROVAR, PERM_PROPOR
from eventos.http.permissoes import EhAdmin, LeGestao, exige_permissao
from eventos.http.serializers import (
    CalendarioItemSerializer,
    CancelarSerializer,
    CategoriaSerializer,
    ConsultaCalendarioSerializer,
    ConsultaCategoriasSerializer,
    ConsultaHistoricoSerializer,
    DetalheSerializer,
    EdicaoSerializer,
    HistoricoSerializer,
    JustificativaSerializer,
    NomeCategoriaSerializer,
    OrcamentoEntradaSerializer,
    PaginaEventosSerializer,
    PresencaEntradaSerializer,
    PresencasSerializer,
    PropostaSerializer,
    RealizarSerializer,
    ReferenciasSerializer,
)
from eventos.services import categorias, consulta, eventos, presencas


def _ator_id(request: Request) -> uuid.UUID:
    raw_id = getattr(request.user, "id", None)
    if raw_id is None:
        raise NotAuthenticated
    return uuid.UUID(str(raw_id))


def _validar(serializer: type[Any], dados: Any) -> dict[str, Any]:
    entrada = serializer(data=dados)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


def _detalhe(ator_id: uuid.UUID, evento_id: uuid.UUID, codigo: int = status.HTTP_200_OK) -> Response:
    return Response(DetalheSerializer(consulta.detalhe(ator_id, evento_id)).data, status=codigo)


class ReferenciasView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Referências para os formulários de evento", responses=ReferenciasSerializer)
    def get(self, request: Request) -> Response:
        return Response(ReferenciasSerializer(consulta.referencias(_ator_id(request))).data)


class CalendarioView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Calendário do mês: publicados e realizados",
        parameters=[ConsultaCalendarioSerializer],
        responses=CalendarioItemSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        ano, mes = _validar(ConsultaCalendarioSerializer, request.query_params)["mes"]
        itens = consulta.calendario(_ator_id(request), ano=ano, mes=mes)
        return Response(CalendarioItemSerializer(itens, many=True).data)


class EventosView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        return [LeGestao()] if self.request.method == "GET" else [exige_permissao(PERM_PROPOR)()]

    @extend_schema(
        summary="Histórico de eventos, com filtros",
        parameters=[ConsultaHistoricoSerializer],
        responses=PaginaEventosSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaHistoricoSerializer, request.query_params)
        pagina = consulta.historico(_ator_id(request), **filtros)
        return Response(PaginaEventosSerializer(pagina).data)

    @extend_schema(summary="Propor um evento", request=PropostaSerializer, responses={201: DetalheSerializer})
    def post(self, request: Request) -> Response:
        dados = _validar(PropostaSerializer, request.data)
        ator_id = _ator_id(request)
        evento = eventos.propor(ator_id, **dados)
        return _detalhe(ator_id, evento.id, status.HTTP_201_CREATED)


class DetalheView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Detalhe do evento", responses=DetalheSerializer)
    def get(self, request: Request, evento_id: uuid.UUID) -> Response:
        return _detalhe(_ator_id(request), evento_id)


class HistoricoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Histórico de auditoria do evento", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, evento_id: uuid.UUID) -> Response:
        registros = consulta.historico_de_auditoria(_ator_id(request), evento_id)
        return Response(HistoricoSerializer(registros, many=True).data)


class EditarView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Editar o evento", request=EdicaoSerializer, responses=DetalheSerializer)
    def post(self, request: Request, evento_id: uuid.UUID) -> Response:
        dados = _validar(EdicaoSerializer, request.data)
        ator_id = _ator_id(request)
        eventos.editar(ator_id, evento_id, **dados)
        return _detalhe(ator_id, evento_id)


class ReabrirView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Reabrir o evento recusado", request=JustificativaSerializer, responses=DetalheSerializer
    )
    def post(self, request: Request, evento_id: uuid.UUID) -> Response:
        dados = _validar(JustificativaSerializer, request.data)
        ator_id = _ator_id(request)
        eventos.reabrir(ator_id, evento_id, justificativa=dados["justificativa"])
        return _detalhe(ator_id, evento_id)


class OrcamentoView(APIView):
    permission_classes = (exige_permissao(PERM_APROVAR),)

    @extend_schema(
        summary="Abrir o orçamento do evento",
        request=OrcamentoEntradaSerializer,
        responses={201: DetalheSerializer},
    )
    def post(self, request: Request, evento_id: uuid.UUID) -> Response:
        dados = _validar(OrcamentoEntradaSerializer, request.data)
        dados["itens"] = [dict(item) for item in dados["itens"]]
        ator_id = _ator_id(request)
        eventos.abrir_orcamento(ator_id, evento_id, **dados)
        return _detalhe(ator_id, evento_id, status.HTTP_201_CREATED)


class PresencaView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Responder vou ou não vou", request=PresencaEntradaSerializer, responses=PresencasSerializer
    )
    def post(self, request: Request, evento_id: uuid.UUID) -> Response:
        dados = _validar(PresencaEntradaSerializer, request.data)
        quadro = presencas.responder(_ator_id(request), evento_id, dados["resposta"])
        return Response(PresencasSerializer(quadro).data)


class RealizarView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Confirmar que o evento aconteceu", request=RealizarSerializer, responses=DetalheSerializer
    )
    def post(self, request: Request, evento_id: uuid.UUID) -> Response:
        dados = _validar(RealizarSerializer, request.data)
        ator_id = _ator_id(request)
        eventos.realizar(ator_id, evento_id, data=dados["data"], motivo=dados["motivo"])
        return _detalhe(ator_id, evento_id)


class CancelarView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Cancelar o evento", request=CancelarSerializer, responses=DetalheSerializer)
    def post(self, request: Request, evento_id: uuid.UUID) -> Response:
        dados = _validar(CancelarSerializer, request.data)
        ator_id = _ator_id(request)
        eventos.cancelar(ator_id, evento_id, motivo=dados["motivo"])
        return _detalhe(ator_id, evento_id)


class CategoriasView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        return [LeGestao()] if self.request.method == "GET" else [EhAdmin()]

    @extend_schema(
        summary="Categorias de evento",
        parameters=[ConsultaCategoriasSerializer],
        responses=CategoriaSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaCategoriasSerializer, request.query_params)
        itens = categorias.listar(_ator_id(request), todas=filtros["todas"])
        return Response(CategoriaSerializer(itens, many=True).data)

    @extend_schema(
        summary="Criar categoria de evento",
        request=NomeCategoriaSerializer,
        responses={201: CategoriaSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NomeCategoriaSerializer, request.data)
        categoria = categorias.criar(_ator_id(request), dados["nome"])
        return Response(CategoriaSerializer(categoria).data, status=status.HTTP_201_CREATED)


class EditarCategoriaView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(
        summary="Renomear categoria de evento", request=NomeCategoriaSerializer, responses=CategoriaSerializer
    )
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        dados = _validar(NomeCategoriaSerializer, request.data)
        categoria = categorias.editar(_ator_id(request), categoria_id, dados["nome"])
        return Response(CategoriaSerializer(categoria).data)


class DesativarCategoriaView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Desativar categoria de evento", request=None, responses=CategoriaSerializer)
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        categoria = categorias.desativar(_ator_id(request), categoria_id)
        return Response(CategoriaSerializer(categoria).data)


class ReativarCategoriaView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Reativar categoria de evento", request=None, responses=CategoriaSerializer)
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        categoria = categorias.reativar(_ator_id(request), categoria_id)
        return Response(CategoriaSerializer(categoria).data)
