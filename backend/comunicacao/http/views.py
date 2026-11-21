"""Rotas HTTP de `comunicacao` (`/api/v1/comunicacao/...`).

Sem regra de negócio: validam a entrada, chamam um serviço e formatam a saída (ADR-004). Toda rota declara a
classe de permissão; quem confere a autoria e a situação é o serviço. A ordem é leitura de gestão (403) →
entrada (400) → existência e visibilidade (404) → quem pode (403) → situação (422).
"""

import uuid
from typing import Any

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from comunicacao.domain.autorizacao import (
    PERM_ENVIAR_DOCUMENTOS,
    PERM_GERENCIAR,
    PERM_PUBLICAR,
    PERM_REGISTRAR_ATAS,
)
from comunicacao.http.permissoes import EhAdmin, LeGestao, exige_permissao
from comunicacao.http.serializers import (
    AtaEntradaSerializer,
    CategoriaSerializer,
    ComentarioSerializer,
    ComunicadoEntradaSerializer,
    ComunicadoSerializer,
    ConsultaDeCategoriasSerializer,
    ConsultaDeComentariosSerializer,
    ConsultaDeDocumentosSerializer,
    ConsultaDoFeedSerializer,
    DetalheDoDocumentoSerializer,
    DocumentoEntradaSerializer,
    EdicaoDoComunicadoSerializer,
    MotivoOpcionalSerializer,
    MotivoSerializer,
    NomeDaCategoriaSerializer,
    NovaVersaoEntradaSerializer,
    PaginaDeComentariosSerializer,
    PaginaDeComunicadosSerializer,
    PaginaDeDocumentosSerializer,
    PaginaDoFeedSerializer,
    ReacaoEntradaSerializer,
    ReacoesSerializer,
    ReferenciasSerializer,
    TextoSerializer,
)
from comunicacao.services import categorias, comentarios, comunicados, consulta, documentos, reacoes


def _ator_id(request: Request) -> uuid.UUID:
    raw_id = getattr(request.user, "id", None)
    if raw_id is None:
        raise NotAuthenticated
    return uuid.UUID(str(raw_id))


def _validar(serializer: type[Any], dados: Any) -> dict[str, Any]:
    entrada = serializer(data=dados)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


def _comunicado(ator_id: uuid.UUID, comunicado_id: uuid.UUID, codigo: int = status.HTTP_200_OK) -> Response:
    return Response(ComunicadoSerializer(consulta.detalhe(ator_id, comunicado_id)).data, status=codigo)


def _comentario(ator_id: uuid.UUID, comentario_id: uuid.UUID, codigo: int = status.HTTP_200_OK) -> Response:
    return Response(ComentarioSerializer(consulta.um_comentario(ator_id, comentario_id)).data, status=codigo)


def _documento(ator_id: uuid.UUID, documento_id: uuid.UUID, codigo: int = status.HTTP_200_OK) -> Response:
    detalhe = consulta.detalhe_do_documento(ator_id, documento_id)
    return Response(DetalheDoDocumentoSerializer(detalhe).data, status=codigo)


# --- referências ---------------------------------------------------------------------------------------


class ReferenciasView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Referências para os formulários da comunicação", responses=ReferenciasSerializer)
    def get(self, request: Request) -> Response:
        return Response(ReferenciasSerializer(consulta.referencias(_ator_id(request))).data)


# --- comunicados ---------------------------------------------------------------------------------------


class ComunicadosView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        return [LeGestao()] if self.request.method == "GET" else [exige_permissao(PERM_PUBLICAR)()]

    @extend_schema(
        summary="O feed: fixados (só na primeira página) e os demais",
        parameters=[ConsultaDoFeedSerializer],
        responses=PaginaDoFeedSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaDoFeedSerializer, request.query_params)
        return Response(PaginaDoFeedSerializer(consulta.feed(_ator_id(request), **filtros)).data)

    @extend_schema(
        summary="Publicar comunicado ou pauta",
        request=ComunicadoEntradaSerializer,
        responses={201: ComunicadoSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(ComunicadoEntradaSerializer, request.data)
        ator_id = _ator_id(request)
        comunicado = comunicados.publicar(ator_id, **dados)
        return _comunicado(ator_id, comunicado.id, status.HTTP_201_CREATED)


class DespublicadosView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Comunicados despublicados que o ator pode ver",
        parameters=[ConsultaDoFeedSerializer],
        responses=PaginaDeComunicadosSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaDoFeedSerializer, request.query_params)
        pagina = consulta.despublicados(_ator_id(request), **filtros)
        return Response(PaginaDeComunicadosSerializer(pagina).data)


class ComunicadoDetalheView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Detalhe do comunicado", responses=ComunicadoSerializer)
    def get(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        return _comunicado(_ator_id(request), comunicado_id)


class EditarComunicadoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Editar o comunicado", request=EdicaoDoComunicadoSerializer, responses=ComunicadoSerializer
    )
    def post(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        dados = _validar(EdicaoDoComunicadoSerializer, request.data)
        ator_id = _ator_id(request)
        comunicados.editar(ator_id, comunicado_id, **dados)
        return _comunicado(ator_id, comunicado_id)


class DespublicarView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Despublicar o comunicado", request=MotivoSerializer, responses=ComunicadoSerializer
    )
    def post(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        dados = _validar(MotivoSerializer, request.data)
        ator_id = _ator_id(request)
        comunicados.despublicar(ator_id, comunicado_id, motivo=dados["motivo"])
        return _comunicado(ator_id, comunicado_id)


class RepublicarView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Republicar o comunicado", request=None, responses=ComunicadoSerializer)
    def post(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        comunicados.republicar(ator_id, comunicado_id)
        return _comunicado(ator_id, comunicado_id)


class FixarView(APIView):
    permission_classes = (exige_permissao(PERM_GERENCIAR),)

    @extend_schema(summary="Fixar o comunicado", request=None, responses=ComunicadoSerializer)
    def post(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        comunicados.fixar(ator_id, comunicado_id)
        return _comunicado(ator_id, comunicado_id)


class DesafixarView(APIView):
    permission_classes = (exige_permissao(PERM_GERENCIAR),)

    @extend_schema(summary="Desafixar o comunicado", request=None, responses=ComunicadoSerializer)
    def post(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        comunicados.desafixar(ator_id, comunicado_id)
        return _comunicado(ator_id, comunicado_id)


# --- reações e comentários -----------------------------------------------------------------------------


class ReacaoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Reagir, trocar ou (repetindo o tipo) retirar a reação",
        request=ReacaoEntradaSerializer,
        responses=ReacoesSerializer,
    )
    def post(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        dados = _validar(ReacaoEntradaSerializer, request.data)
        quadro = reacoes.reagir(_ator_id(request), comunicado_id, dados["tipo"])
        return Response(ReacoesSerializer(quadro).data)


class RetirarReacaoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Retirar a reação", request=None, responses=ReacoesSerializer)
    def post(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        return Response(ReacoesSerializer(reacoes.retirar(_ator_id(request), comunicado_id)).data)


class ComentariosView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Comentários do comunicado, do mais antigo ao mais novo",
        parameters=[ConsultaDeComentariosSerializer],
        responses=PaginaDeComentariosSerializer,
    )
    def get(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        filtros = _validar(ConsultaDeComentariosSerializer, request.query_params)
        pagina = consulta.comentarios(_ator_id(request), comunicado_id, **filtros)
        return Response(PaginaDeComentariosSerializer(pagina).data)

    @extend_schema(summary="Comentar", request=TextoSerializer, responses={201: ComentarioSerializer})
    def post(self, request: Request, comunicado_id: uuid.UUID) -> Response:
        dados = _validar(TextoSerializer, request.data)
        ator_id = _ator_id(request)
        comentario = comentarios.comentar(ator_id, comunicado_id, dados["texto"])
        return _comentario(ator_id, comentario.id, status.HTTP_201_CREATED)


class EditarComentarioView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Editar o próprio comentário", request=TextoSerializer, responses=ComentarioSerializer
    )
    def post(self, request: Request, comentario_id: uuid.UUID) -> Response:
        dados = _validar(TextoSerializer, request.data)
        ator_id = _ator_id(request)
        comentarios.editar(ator_id, comentario_id, dados["texto"])
        return _comentario(ator_id, comentario_id)


class OcultarComentarioView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Ocultar o comentário (o autor, sem motivo; a gerência, com motivo)",
        request=MotivoOpcionalSerializer,
        responses=ComentarioSerializer,
    )
    def post(self, request: Request, comentario_id: uuid.UUID) -> Response:
        dados = _validar(MotivoOpcionalSerializer, request.data)
        ator_id = _ator_id(request)
        comentarios.ocultar(ator_id, comentario_id, dados["motivo"])
        return _comentario(ator_id, comentario_id)


class ReexibirComentarioView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Reexibir o comentário", request=None, responses=ComentarioSerializer)
    def post(self, request: Request, comentario_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        comentarios.reexibir(ator_id, comentario_id)
        return _comentario(ator_id, comentario_id)


# --- documentos e atas ---------------------------------------------------------------------------------


class DocumentosView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [LeGestao()]
        return [exige_permissao(PERM_ENVIAR_DOCUMENTOS)()]

    @extend_schema(
        summary="A aba de documentos, com filtros",
        parameters=[ConsultaDeDocumentosSerializer],
        responses=PaginaDeDocumentosSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaDeDocumentosSerializer, request.query_params)
        return Response(PaginaDeDocumentosSerializer(consulta.documentos(_ator_id(request), **filtros)).data)

    @extend_schema(
        summary="Enviar documento",
        request={"multipart/form-data": DocumentoEntradaSerializer},
        responses={201: DetalheDoDocumentoSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(DocumentoEntradaSerializer, request.data)
        ator_id = _ator_id(request)
        documento = documentos.enviar_documento(ator_id, **dados)
        return _documento(ator_id, documento.id, status.HTTP_201_CREATED)


class AtasView(APIView):
    permission_classes = (exige_permissao(PERM_REGISTRAR_ATAS),)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        summary="Registrar ata",
        request={"multipart/form-data": AtaEntradaSerializer},
        responses={201: DetalheDoDocumentoSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(AtaEntradaSerializer, request.data)
        ator_id = _ator_id(request)
        ata = documentos.registrar_ata(ator_id, **dados)
        return _documento(ator_id, ata.id, status.HTTP_201_CREATED)


class DocumentoDetalheView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Detalhe do documento", responses=DetalheDoDocumentoSerializer)
    def get(self, request: Request, documento_id: uuid.UUID) -> Response:
        return _documento(_ator_id(request), documento_id)


_RESPOSTA_DO_ARQUIVO = {(200, "application/octet-stream"): OpenApiTypes.BINARY}


class ArquivoVigenteView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="O arquivo da versão vigente", responses=_RESPOSTA_DO_ARQUIVO)
    def get(self, request: Request, documento_id: uuid.UUID) -> HttpResponse:
        return consulta.download(_ator_id(request), documento_id)


class ArquivoDaVersaoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="O arquivo de uma versão", responses=_RESPOSTA_DO_ARQUIVO)
    def get(self, request: Request, documento_id: uuid.UUID, numero: int) -> HttpResponse:
        return consulta.download(_ator_id(request), documento_id, numero=numero)


class NovaVersaoView(APIView):
    permission_classes = (LeGestao,)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        summary="Enviar nova versão do documento",
        request={"multipart/form-data": NovaVersaoEntradaSerializer},
        responses={201: DetalheDoDocumentoSerializer},
    )
    def post(self, request: Request, documento_id: uuid.UUID) -> Response:
        dados = _validar(NovaVersaoEntradaSerializer, request.data)
        ator_id = _ator_id(request)
        documentos.nova_versao(ator_id, documento_id, **dados)
        return _documento(ator_id, documento_id, status.HTTP_201_CREATED)


class ArquivarView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Arquivar o documento", request=None, responses=DetalheDoDocumentoSerializer)
    def post(self, request: Request, documento_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        documentos.arquivar(ator_id, documento_id)
        return _documento(ator_id, documento_id)


class DesarquivarView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Desarquivar o documento", request=None, responses=DetalheDoDocumentoSerializer)
    def post(self, request: Request, documento_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        documentos.desarquivar(ator_id, documento_id)
        return _documento(ator_id, documento_id)


# --- categorias de documento ---------------------------------------------------------------------------


class CategoriasView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        return [LeGestao()] if self.request.method == "GET" else [EhAdmin()]

    @extend_schema(
        summary="Categorias de documento",
        parameters=[ConsultaDeCategoriasSerializer],
        responses=CategoriaSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaDeCategoriasSerializer, request.query_params)
        itens = categorias.listar(_ator_id(request), todas=filtros["todas"])
        return Response(CategoriaSerializer(itens, many=True).data)

    @extend_schema(
        summary="Criar categoria de documento",
        request=NomeDaCategoriaSerializer,
        responses={201: CategoriaSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NomeDaCategoriaSerializer, request.data)
        categoria = categorias.criar(_ator_id(request), dados["nome"])
        return Response(CategoriaSerializer(categoria).data, status=status.HTTP_201_CREATED)


class EditarCategoriaView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(
        summary="Renomear categoria de documento",
        request=NomeDaCategoriaSerializer,
        responses=CategoriaSerializer,
    )
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        dados = _validar(NomeDaCategoriaSerializer, request.data)
        categoria = categorias.editar(_ator_id(request), categoria_id, dados["nome"])
        return Response(CategoriaSerializer(categoria).data)


class DesativarCategoriaView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Desativar categoria de documento", request=None, responses=CategoriaSerializer)
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        return Response(CategoriaSerializer(categorias.desativar(_ator_id(request), categoria_id)).data)


class ReativarCategoriaView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Reativar categoria de documento", request=None, responses=CategoriaSerializer)
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        return Response(CategoriaSerializer(categorias.reativar(_ator_id(request), categoria_id)).data)
