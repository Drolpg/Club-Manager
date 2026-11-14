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
    CancelamentoSerializer,
    ConsultaDaListaSerializer,
    ConsultaDeMotivosSerializer,
    ContestacaoSerializer,
    ConteudoSerializer,
    DecisaoSerializer,
    DetalheSerializer,
    EdicaoSerializer,
    EnvioSerializer,
    HistoricoSerializer,
    ItemDaListaSerializer,
    MotivoSerializer,
    NovoMotivoSerializer,
    PaginaSerializer,
    ReaberturaSerializer,
    SolicitacaoSerializer,
    TextoDoMotivoSerializer,
    TipoDeDecisaoSerializer,
    TipoDeSolicitacaoSerializer,
)
from aprovacoes.services import consulta, decisoes, motivos, solicitacoes


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


class TiposView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Tipos de solicitação registrados", responses=TipoDeSolicitacaoSerializer(many=True)
    )
    def get(self, request: Request) -> Response:
        return Response(TipoDeSolicitacaoSerializer(consulta.listar_tipos(_ator_id(request)), many=True).data)


class SolicitacoesView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Lista de solicitações",
        description="Da mais recente para a mais antiga. `antes` é o ID da última recebida; `limite` vai "
        "de 1 a 50 (padrão 20). `minhas=1` traz só as que quem pergunta enviou.",
        parameters=[ConsultaDaListaSerializer],
        responses=PaginaSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaDaListaSerializer, request.query_params)
        pagina = consulta.listar(
            _ator_id(request),
            tipo=filtros.get("tipo"),
            situacao=filtros.get("situacao"),
            minhas=filtros["minhas"],
            antes=filtros.get("antes"),
            limite=filtros["limite"],
        )
        return Response(PaginaSerializer(pagina).data)

    @extend_schema(
        summary="Enviar solicitação",
        description="Cria a solicitação em análise, com a versão 1. O conteúdo é validado pelo módulo dono "
        "do tipo. Quem pode aprovar o tipo e não tem auto-aprovação indica outro aprovador.",
        request=EnvioSerializer,
        responses={201: SolicitacaoSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(EnvioSerializer, request.data)
        solicitacao = solicitacoes.enviar(
            ator_id=_ator_id(request),
            tipo=dados["tipo"],
            conteudo=dados["conteudo"],
            aprovador_indicado_id=dados["aprovador_indicado_id"],
        )
        return Response(SolicitacaoSerializer(solicitacao).data, status=201)


def _retirar(request: Request, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Any:
    return solicitacoes.retirar(ator_id=ator_id, solicitacao_id=solicitacao_id)


def _reenviar(request: Request, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Any:
    dados = _validar(ConteudoSerializer, request.data)
    return solicitacoes.reenviar(ator_id=ator_id, solicitacao_id=solicitacao_id, conteudo=dados["conteudo"])


def _reabrir(request: Request, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Any:
    dados = _validar(ReaberturaSerializer, request.data)
    return solicitacoes.reabrir(
        ator_id=ator_id,
        solicitacao_id=solicitacao_id,
        justificativa=dados["justificativa"],
        conteudo=dados["conteudo"],
    )


def _editar(request: Request, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Any:
    dados = _validar(EdicaoSerializer, request.data)
    return solicitacoes.editar(
        ator_id=ator_id,
        solicitacao_id=solicitacao_id,
        conteudo=dados["conteudo"],
        justificativa=dados["justificativa"],
    )


def _cancelar(request: Request, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Any:
    dados = _validar(CancelamentoSerializer, request.data)
    return solicitacoes.cancelar(ator_id=ator_id, solicitacao_id=solicitacao_id, motivo=dados["motivo"])


def _aprovar(request: Request, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Any:
    dados = _validar(DecisaoSerializer, request.data)
    return decisoes.aprovar(
        ator_id=ator_id, solicitacao_id=solicitacao_id, motivo_id=dados["motivo_id"], texto=dados["texto"]
    )


def _contestar(request: Request, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Any:
    dados = _validar(ContestacaoSerializer, request.data)
    return decisoes.contestar(
        ator_id=ator_id,
        solicitacao_id=solicitacao_id,
        motivo_id=dados["motivo_id"],
        texto=dados["texto"],
        mensagem=dados["mensagem"],
        teto_sugerido=dados["teto_sugerido"],
    )


def _recusar(request: Request, ator_id: uuid.UUID, solicitacao_id: uuid.UUID) -> Any:
    dados = _validar(DecisaoSerializer, request.data)
    return decisoes.recusar(
        ator_id=ator_id, solicitacao_id=solicitacao_id, motivo_id=dados["motivo_id"], texto=dados["texto"]
    )


def _view_de_acao(acao: str, executar: Any, entrada: type[Any] | None, resumo: str) -> type[APIView]:
    """Uma view por comando, para o contrato mostrar a entrada de cada um. Quem pode, o serviço confere."""

    class AcaoView(APIView):
        permission_classes = (LeGestao,)

        @extend_schema(summary=resumo, request=entrada, responses=SolicitacaoSerializer)
        def post(self, request: Request, solicitacao_id: uuid.UUID) -> Response:
            solicitacao = executar(request, _ator_id(request), solicitacao_id)
            return Response(SolicitacaoSerializer(solicitacao).data)

    AcaoView.__name__ = AcaoView.__qualname__ = f"{acao.capitalize()}View"
    return AcaoView


VIEWS_DO_SOLICITANTE: dict[str, type[APIView]] = {
    "retirar": _view_de_acao("retirar", _retirar, None, "Retirar da análise"),
    "reenviar": _view_de_acao("reenviar", _reenviar, ConteudoSerializer, "Reenviar com o conteúdo corrigido"),
    "reabrir": _view_de_acao("reabrir", _reabrir, ReaberturaSerializer, "Reabrir a solicitação recusada"),
    "editar": _view_de_acao("editar", _editar, EdicaoSerializer, "Editar a solicitação aprovada"),
    "cancelar": _view_de_acao("cancelar", _cancelar, CancelamentoSerializer, "Cancelar a solicitação"),
    "aprovar": _view_de_acao("aprovar", _aprovar, DecisaoSerializer, "Aprovar a solicitação"),
    "contestar": _view_de_acao("contestar", _contestar, ContestacaoSerializer, "Contestar a solicitação"),
    "recusar": _view_de_acao("recusar", _recusar, DecisaoSerializer, "Recusar a solicitação"),
}


class DetalheView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Detalhe da solicitação", responses=DetalheSerializer)
    def get(self, request: Request, solicitacao_id: uuid.UUID) -> Response:
        return Response(DetalheSerializer(consulta.detalhe(_ator_id(request), solicitacao_id)).data)


class HistoricoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Histórico da solicitação", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, solicitacao_id: uuid.UUID) -> Response:
        registros = consulta.historico(_ator_id(request), solicitacao_id)
        return Response(HistoricoSerializer(registros, many=True).data)


class FilaView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Fila de pendências",
        description="As solicitações em análise que quem pergunta pode decidir, da que espera há mais tempo.",
        responses=ItemDaListaSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        return Response(ItemDaListaSerializer(consulta.fila(_ator_id(request)), many=True).data)
