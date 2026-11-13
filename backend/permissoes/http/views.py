import uuid
from typing import Any, ClassVar

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from permissoes import catalogo
from permissoes.http.permissions import EhAdmin, LeGestao
from permissoes.http.serializers import (
    CargoOuSetorSerializer,
    CatalogoSerializer,
    ClassificacaoEntradaSerializer,
    ConcessaoEntradaSerializer,
    ConcessaoSerializer,
    DetalheDoUsuarioSerializer,
    NomeSerializer,
)
from permissoes.models import Cargo, Setor
from permissoes.services import cargos_e_setores, classificacao, concessoes, consulta


def _ator_id(request: Request) -> uuid.UUID:
    """O ID de quem está logado. As permissões da view já garantiram que há um."""
    usuario_id = getattr(request.user, "id", None)
    if usuario_id is None:
        raise NotAuthenticated
    return uuid.UUID(str(usuario_id))


def _validar(request: Request, serializer: type[Any]) -> dict[str, Any]:
    entrada = serializer(data=request.data)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


class ItensView(APIView):
    """Lista e cria cargos ou setores; `modelo` vem da rota."""

    modelo: ClassVar[type[Cargo] | type[Setor]] = Cargo

    def get_permissions(self) -> list[BasePermission]:
        return [LeGestao()] if self.request.method == "GET" else [EhAdmin()]

    @extend_schema(responses=CargoOuSetorSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(CargoOuSetorSerializer(cargos_e_setores.listar(self.modelo), many=True).data)

    @extend_schema(request=NomeSerializer, responses={201: CargoOuSetorSerializer})
    def post(self, request: Request) -> Response:
        nome = _validar(request, NomeSerializer)["nome"]
        item = cargos_e_setores.criar(self.modelo, ator_id=_ator_id(request), nome=nome)
        return Response(CargoOuSetorSerializer(item).data, status=201)


class AcaoDeItemView(APIView):
    """Renomear, desativar e reativar um cargo ou setor; `modelo` e `acao` vêm da rota."""

    permission_classes = (EhAdmin,)
    modelo: ClassVar[type[Cargo] | type[Setor]] = Cargo
    acao: ClassVar[str] = ""

    @extend_schema(request=NomeSerializer, responses=CargoOuSetorSerializer)
    def post(self, request: Request, item_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        if self.acao == "renomear":
            nome = _validar(request, NomeSerializer)["nome"]
            item = cargos_e_setores.renomear(self.modelo, ator_id=ator_id, item_id=item_id, nome=nome)
        elif self.acao == "desativar":
            item = cargos_e_setores.desativar(self.modelo, ator_id=ator_id, item_id=item_id)
        else:
            item = cargos_e_setores.reativar(self.modelo, ator_id=ator_id, item_id=item_id)
        return Response(CargoOuSetorSerializer(item).data)


class CatalogoView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Catálogo de permissões", responses=CatalogoSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(CatalogoSerializer(catalogo.listar(), many=True).data)


class ConcessoesView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Concessões ativas", responses=ConcessaoSerializer(many=True))
    def get(self, request: Request) -> Response:
        ativas = concessoes.listar_ativas(_ator_id(request))
        return Response(ConcessaoSerializer(concessoes.descrever(ativas), many=True).data)

    @extend_schema(
        summary="Conceder permissão",
        description="Responde 201 se criou e 200 se o alvo já tinha a permissão.",
        request=ConcessaoEntradaSerializer,
        responses={200: ConcessaoSerializer, 201: ConcessaoSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(request, ConcessaoEntradaSerializer)
        concessao, criada = concessoes.conceder(
            _ator_id(request), dados["permissao"], dados["alvo_tipo"], dados["alvo_id"]
        )
        (info,) = concessoes.descrever([concessao])
        return Response(ConcessaoSerializer(info).data, status=201 if criada else 200)


class RevogarConcessaoView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Revogar concessão", request=None, responses=ConcessaoSerializer)
    def post(self, request: Request, concessao_id: uuid.UUID) -> Response:
        concessao = concessoes.revogar(_ator_id(request), concessao_id)
        (info,) = concessoes.descrever([concessao])
        return Response(ConcessaoSerializer(info).data)


class DetalheDoUsuarioView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Classificação e permissões de um usuário", responses=DetalheDoUsuarioSerializer)
    def get(self, request: Request, usuario_id: uuid.UUID) -> Response:
        detalhe = consulta.detalhe_para_admin(_ator_id(request), usuario_id)
        return Response(DetalheDoUsuarioSerializer(detalhe).data)


class ClassificacaoView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(
        summary="Classificar um diretor",
        description="`cargo_id` nulo tira o cargo, e os setores junto. Responde com o detalhe do usuário.",
        request=ClassificacaoEntradaSerializer,
        responses=DetalheDoUsuarioSerializer,
    )
    def put(self, request: Request, usuario_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(request, ClassificacaoEntradaSerializer)
        classificacao.classificar(ator_id, usuario_id, dados["cargo_id"], dados["setor_ids"])
        detalhe = consulta.detalhe_para_admin(ator_id, usuario_id)
        return Response(DetalheDoUsuarioSerializer(detalhe).data)


class MinhasView(APIView):
    """O cargo, os setores e as permissões de quem pergunta. Nunca os de outra pessoa (CA-26)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(summary="Minhas permissões", responses=DetalheDoUsuarioSerializer)
    def get(self, request: Request) -> Response:
        return Response(DetalheDoUsuarioSerializer(consulta.detalhe_de(_ator_id(request))).data)
