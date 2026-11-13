import uuid
from typing import Any, ClassVar

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from permissoes.http.permissions import EhAdmin, LeGestao
from permissoes.http.serializers import CargoOuSetorSerializer, NomeSerializer
from permissoes.models import Cargo, Setor
from permissoes.services import cargos_e_setores


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
