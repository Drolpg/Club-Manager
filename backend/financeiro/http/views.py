"""Rotas HTTP da API financeira (`/api/v1/financeiro/...`). Sem regra de negócio."""

import uuid
from typing import Any

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from financeiro.domain.autorizacao import (
    PERM_COBRANCAS_CANCELAR,
    PERM_COBRANCAS_CRIAR,
    PERM_COBRANCAS_ISENTAR,
    PERM_COBRANCAS_SUSPENDER,
    PERM_DIVIDAS_DECIDIR,
    PERM_PAGAMENTOS_VALIDAR,
    PERM_QUESTIONAMENTOS_DECIDIR,
)
from financeiro.erros import erro
from financeiro.http.permissions import DiretorAtivo, EhAdmin, LeGestao, exige_permissao
from financeiro.http.serializers import (
    CancelarCobrancaSerializer,
    CategoriaSerializer,
    ChavePixSerializer,
    CobrancaDetalheSerializer,
    CobrancaItemSerializer,
    ConsultaCategoriasSerializer,
    ConsultaChavesPixSerializer,
    ConsultaCobrancasSerializer,
    ConsultaMinhasCobrancasSerializer,
    ConsultaRecorrenciasSerializer,
    ConsultaSuspensoesSerializer,
    DecidirDividaSerializer,
    DecidirPagamentoSerializer,
    DecidirQuestionamentoSerializer,
    EditarChavePixSerializer,
    EditarRecorrenciaSerializer,
    HistoricoSerializer,
    IsentarCobrancaSerializer,
    JustificarDividaSerializer,
    NomeCategoriaSerializer,
    NovaCategoriaSerializer,
    NovaChavePixSerializer,
    NovaCobrancaSerializer,
    NovaRecorrenciaSerializer,
    NovaSuspensaoSerializer,
    NovoLoteCobrancasSerializer,
    PaginaCobrancasSerializer,
    QuestionarCobrancaSerializer,
    RecorrenciaSerializer,
    RegistrarPagamentoSerializer,
    RenegociarDividaSerializer,
    SuspensaoSerializer,
)
from financeiro.services import (
    categorias,
    chaves_pix,
    cobrancas,
    consulta,
    inadimplencia,
    pagamentos,
    questionamentos,
    recorrencias,
    suspensoes,
)
from kernel.dinheiro import Dinheiro


def _ator_id(request: Request) -> uuid.UUID:
    raw_id = getattr(request.user, "id", None)
    if raw_id is None:
        raise NotAuthenticated
    return uuid.UUID(str(raw_id))


def _validar(serializer: type[Any], dados: Any) -> dict[str, Any]:
    entrada = serializer(data=dados)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


def _dinheiro_positivo(valor: Any) -> Dinheiro:
    try:
        dinheiro = Dinheiro(valor)
    except ValueError:
        raise erro("VALOR_INVALIDO") from None
    if dinheiro.quantia <= 0:
        raise erro("VALOR_INVALIDO")
    return dinheiro


# --- Categorias ---


class CategoriasView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        return [LeGestao()] if self.request.method == "GET" else [EhAdmin()]

    @extend_schema(
        summary="Listar categorias financeiras",
        parameters=[ConsultaCategoriasSerializer],
        responses=CategoriaSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaCategoriasSerializer, request.query_params)
        itens = categorias.listar(
            _ator_id(request),
            natureza=filtros.get("natureza"),
            incluir_inativas=filtros["todas"],
        )
        return Response(CategoriaSerializer(itens, many=True).data)

    @extend_schema(
        summary="Criar categoria financeira",
        request=NovaCategoriaSerializer,
        responses={201: CategoriaSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NovaCategoriaSerializer, request.data)
        categoria = categorias.criar(
            ator_id=_ator_id(request), nome=dados["nome"], natureza=dados["natureza"]
        )
        return Response(CategoriaSerializer(categoria).data, status=status.HTTP_201_CREATED)


class CategoriaRenomearView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(
        summary="Renomear categoria financeira",
        request=NomeCategoriaSerializer,
        responses=CategoriaSerializer,
    )
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        dados = _validar(NomeCategoriaSerializer, request.data)
        categoria = categorias.renomear(
            ator_id=_ator_id(request), categoria_id=categoria_id, nome=dados["nome"]
        )
        return Response(CategoriaSerializer(categoria).data)


class CategoriaDesativarView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Desativar categoria financeira", request=None, responses=CategoriaSerializer)
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        categoria = categorias.desativar(ator_id=_ator_id(request), categoria_id=categoria_id)
        return Response(CategoriaSerializer(categoria).data)


class CategoriaReativarView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Reativar categoria financeira", request=None, responses=CategoriaSerializer)
    def post(self, request: Request, categoria_id: uuid.UUID) -> Response:
        categoria = categorias.reativar(ator_id=_ator_id(request), categoria_id=categoria_id)
        return Response(CategoriaSerializer(categoria).data)


class CategoriaHistoricoView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Histórico da categoria financeira", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, categoria_id: uuid.UUID) -> Response:
        registros = categorias.historico(ator_id=_ator_id(request), categoria_id=categoria_id)
        return Response(HistoricoSerializer(consulta.serializar_historico(registros), many=True).data)


# --- Chaves Pix ---


class ChavesPixView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        return [LeGestao()] if self.request.method == "GET" else [EhAdmin()]

    @extend_schema(
        summary="Listar chaves Pix",
        parameters=[ConsultaChavesPixSerializer],
        responses=ChavePixSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaChavesPixSerializer, request.query_params)
        itens = chaves_pix.listar(_ator_id(request), incluir_inativas=filtros["todas"])
        return Response(ChavePixSerializer(itens, many=True).data)

    @extend_schema(
        summary="Cadastrar chave Pix",
        request=NovaChavePixSerializer,
        responses={201: ChavePixSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NovaChavePixSerializer, request.data)
        chave = chaves_pix.cadastrar(
            ator_id=_ator_id(request),
            tipo=dados["tipo"],
            chave=dados["chave"],
            nome_recebedor=dados["nome_recebedor"],
            cidade=dados["cidade"],
            padrao=dados["padrao"],
        )
        return Response(ChavePixSerializer(chave).data, status=status.HTTP_201_CREATED)


class ChavePixEditarView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(
        summary="Editar chave Pix",
        request=EditarChavePixSerializer,
        responses=ChavePixSerializer,
    )
    def post(self, request: Request, chave_id: uuid.UUID) -> Response:
        dados = _validar(EditarChavePixSerializer, request.data)
        chave = chaves_pix.editar(
            ator_id=_ator_id(request),
            chave_id=chave_id,
            tipo=dados["tipo"],
            chave=dados["chave"],
            nome_recebedor=dados["nome_recebedor"],
            cidade=dados["cidade"],
        )
        return Response(ChavePixSerializer(chave).data)


class ChavePixPadraoView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Marcar chave Pix como padrão", request=None, responses=ChavePixSerializer)
    def post(self, request: Request, chave_id: uuid.UUID) -> Response:
        chave = chaves_pix.marcar_padrao(ator_id=_ator_id(request), chave_id=chave_id)
        return Response(ChavePixSerializer(chave).data)


class ChavePixDesativarView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Desativar chave Pix", request=None, responses=ChavePixSerializer)
    def post(self, request: Request, chave_id: uuid.UUID) -> Response:
        chave = chaves_pix.desativar(ator_id=_ator_id(request), chave_id=chave_id)
        return Response(ChavePixSerializer(chave).data)


class ChavePixReativarView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Reativar chave Pix", request=None, responses=ChavePixSerializer)
    def post(self, request: Request, chave_id: uuid.UUID) -> Response:
        chave = chaves_pix.reativar(ator_id=_ator_id(request), chave_id=chave_id)
        return Response(ChavePixSerializer(chave).data)


class ChavePixHistoricoView(APIView):
    permission_classes = (EhAdmin,)

    @extend_schema(summary="Histórico da chave Pix", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, chave_id: uuid.UUID) -> Response:
        registros = chaves_pix.historico(ator_id=_ator_id(request), chave_id=chave_id)
        return Response(HistoricoSerializer(consulta.serializar_historico(registros), many=True).data)


# --- Cobranças ---


class MinhasCobrancasView(APIView):
    permission_classes = (DiretorAtivo,)

    @extend_schema(
        summary="Listar cobranças do próprio usuário",
        parameters=[ConsultaMinhasCobrancasSerializer],
        responses=PaginaCobrancasSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaMinhasCobrancasSerializer, request.query_params)
        pagina = consulta.minhas_cobrancas(
            _ator_id(request),
            situacao=filtros.get("situacao"),
            antes=filtros.get("antes"),
            limite=filtros["limite"],
        )
        return Response(PaginaCobrancasSerializer(pagina).data)


class CobrancasView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [LeGestao()]
        return [exige_permissao(PERM_COBRANCAS_CRIAR)()]

    @extend_schema(
        summary="Listar todas as cobranças (gestão)",
        parameters=[ConsultaCobrancasSerializer],
        responses=PaginaCobrancasSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaCobrancasSerializer, request.query_params)
        pagina = consulta.listar(
            _ator_id(request),
            situacao=filtros.get("situacao"),
            categoria_id=filtros.get("categoria_id"),
            devedor_id=filtros.get("devedor_id"),
            de=filtros.get("de"),
            ate=filtros.get("ate"),
            inadimplentes=filtros["inadimplentes"],
            antes=filtros.get("antes"),
            limite=filtros["limite"],
        )
        return Response(PaginaCobrancasSerializer(pagina).data)

    @extend_schema(
        summary="Criar cobrança avulsa",
        request=NovaCobrancaSerializer,
        responses={201: CobrancaDetalheSerializer},
    )
    def post(self, request: Request) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(NovaCobrancaSerializer, request.data)
        cobranca = cobrancas.criar_avulsa(
            ator_id=ator_id,
            devedor_id=dados["devedor_id"],
            categoria_id=dados["categoria_id"],
            descricao=dados["descricao"],
            valor=_dinheiro_positivo(dados["valor"]),
            vencimento=dados["vencimento"],
            limite_de_inadimplencia=dados["limite_de_inadimplencia"],
            chave_pix_id=dados.get("chave_pix_id"),
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data, status=status.HTTP_201_CREATED)


class CobrancaLoteView(APIView):
    permission_classes = (exige_permissao(PERM_COBRANCAS_CRIAR),)

    @extend_schema(
        summary="Criar cobranças em lote",
        request=NovoLoteCobrancasSerializer,
        responses={201: CobrancaItemSerializer(many=True)},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NovoLoteCobrancasSerializer, request.data)
        criadas = cobrancas.criar_lote(
            ator_id=_ator_id(request),
            devedor_ids=dados["devedor_ids"],
            todos_ativos_com_cargo=dados["todos_ativos_com_cargo"],
            categoria_id=dados["categoria_id"],
            descricao=dados["descricao"],
            valor=_dinheiro_positivo(dados["valor"]),
            vencimento=dados["vencimento"],
            limite_de_inadimplencia=dados["limite_de_inadimplencia"],
            chave_pix_id=dados.get("chave_pix_id"),
        )
        itens = [consulta.serializar_item(c) for c in criadas]
        return Response(CobrancaItemSerializer(itens, many=True).data, status=status.HTTP_201_CREATED)


class CobrancaDetalheView(APIView):
    permission_classes = (DiretorAtivo,)

    @extend_schema(summary="Detalhar cobrança", responses=CobrancaDetalheSerializer)
    def get(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        detalhe = consulta.detalhe(_ator_id(request), cobranca_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaHistoricoView(APIView):
    permission_classes = (DiretorAtivo,)

    @extend_schema(summary="Histórico da cobrança", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        registros = consulta.historico(_ator_id(request), cobranca_id)
        return Response(HistoricoSerializer(registros, many=True).data)


class CobrancaCancelarView(APIView):
    permission_classes = (exige_permissao(PERM_COBRANCAS_CANCELAR),)

    @extend_schema(
        summary="Cancelar cobrança",
        request=CancelarCobrancaSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(CancelarCobrancaSerializer, request.data)
        cobranca = cobrancas.cancelar(
            ator_id=ator_id,
            cobranca_id=cobranca_id,
            motivo_id=dados["motivo_id"],
            texto=dados["texto"],
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaIsentarView(APIView):
    permission_classes = (exige_permissao(PERM_COBRANCAS_ISENTAR),)

    @extend_schema(
        summary="Isentar cobrança",
        request=IsentarCobrancaSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(IsentarCobrancaSerializer, request.data)
        cobranca = cobrancas.isentar(
            ator_id=ator_id,
            cobranca_id=cobranca_id,
            justificativa=dados["justificativa"],
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaQuestionarView(APIView):
    permission_classes = (DiretorAtivo,)

    @extend_schema(
        summary="Questionar cobrança (devedor)",
        request=QuestionarCobrancaSerializer,
        responses={201: CobrancaDetalheSerializer},
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(QuestionarCobrancaSerializer, request.data)
        cobranca = questionamentos.questionar(
            ator_id=ator_id,
            cobranca_id=cobranca_id,
            texto=dados["texto"],
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data, status=status.HTTP_201_CREATED)


class CobrancaDecidirQuestionamentoView(APIView):
    permission_classes = (exige_permissao(PERM_QUESTIONAMENTOS_DECIDIR),)

    @extend_schema(
        summary="Decidir questionamento aberto",
        request=DecidirQuestionamentoSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(DecidirQuestionamentoSerializer, request.data)
        cobranca = questionamentos.decidir(
            ator_id=ator_id,
            cobranca_id=cobranca_id,
            decisao=dados["decisao"],
            motivo_id=dados["motivo_id"],
            texto=dados["texto"],
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaJustificarDividaView(APIView):
    permission_classes = (DiretorAtivo,)

    @extend_schema(
        summary="Justificar dívida após convocação (devedor)",
        request=JustificarDividaSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(JustificarDividaSerializer, request.data)
        cobranca = inadimplencia.justificar_divida(
            ator_id=ator_id,
            cobranca_id=cobranca_id,
            texto=dados["texto"],
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaPerdoarView(APIView):
    permission_classes = (exige_permissao(PERM_DIVIDAS_DECIDIR),)

    @extend_schema(
        summary="Perdoar cobrança atrasada",
        request=DecidirDividaSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(DecidirDividaSerializer, request.data)
        cobranca = inadimplencia.perdoar(
            ator_id=ator_id,
            cobranca_id=cobranca_id,
            motivo_id=dados["motivo_id"],
            texto=dados["texto"],
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaRenegociarView(APIView):
    permission_classes = (exige_permissao(PERM_DIVIDAS_DECIDIR),)

    @extend_schema(
        summary="Renegociar cobrança atrasada em parcelas",
        request=RenegociarDividaSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(RenegociarDividaSerializer, request.data)
        cobranca = inadimplencia.renegociar(
            ator_id=ator_id,
            cobranca_id=cobranca_id,
            motivo_id=dados["motivo_id"],
            texto=dados["texto"],
            parcelas=dados["parcelas"],
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaManterDividaView(APIView):
    permission_classes = (exige_permissao(PERM_DIVIDAS_DECIDIR),)

    @extend_schema(
        summary="Manter dívida após convocação",
        request=DecidirDividaSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(DecidirDividaSerializer, request.data)
        cobranca = inadimplencia.manter_divida(
            ator_id=ator_id,
            cobranca_id=cobranca_id,
            motivo_id=dados["motivo_id"],
            texto=dados["texto"],
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaPagamentosView(APIView):
    permission_classes = (DiretorAtivo,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(
        summary="Registrar pagamento de cobrança",
        request=RegistrarPagamentoSerializer,
        responses={201: CobrancaDetalheSerializer},
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(RegistrarPagamentoSerializer, request.data)
        cobranca = pagamentos.registrar(
            ator_id,
            cobranca_id,
            forma=dados["forma"],
            data_pagamento=dados["data_pagamento"],
            recebedor_id=dados.get("recebedor_id"),
            arquivo=dados.get("comprovante"),
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data, status=status.HTTP_201_CREATED)


class CobrancaComprovanteView(APIView):
    permission_classes = (DiretorAtivo,)

    @extend_schema(summary="Baixar comprovante privado", responses={200: OpenApiTypes.BINARY})
    def get(self, request: Request, cobranca_id: uuid.UUID, pagamento_id: uuid.UUID) -> HttpResponse:
        return pagamentos.baixar_comprovante(_ator_id(request), cobranca_id, pagamento_id)


class CobrancaValidarPagamentoView(APIView):
    permission_classes = (exige_permissao(PERM_PAGAMENTOS_VALIDAR),)

    @extend_schema(
        summary="Validar pagamento",
        request=DecidirPagamentoSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(DecidirPagamentoSerializer, request.data)
        cobranca = pagamentos.validar(
            ator_id, cobranca_id, motivo_id=dados["motivo_id"], texto=dados["texto"]
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaRejeitarPagamentoView(APIView):
    permission_classes = (exige_permissao(PERM_PAGAMENTOS_VALIDAR),)

    @extend_schema(
        summary="Rejeitar pagamento",
        request=DecidirPagamentoSerializer,
        responses=CobrancaDetalheSerializer,
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        ator_id = _ator_id(request)
        dados = _validar(DecidirPagamentoSerializer, request.data)
        cobranca = pagamentos.rejeitar(
            ator_id, cobranca_id, motivo_id=dados["motivo_id"], texto=dados["texto"]
        )
        detalhe = consulta.serializar_detalhe(cobranca, ator_id=ator_id)
        return Response(CobrancaDetalheSerializer(detalhe).data)


class CobrancaReciboView(APIView):
    permission_classes = (DiretorAtivo,)

    @extend_schema(summary="Emitir recibo PDF da cobrança paga", responses={200: OpenApiTypes.BINARY})
    def get(self, request: Request, cobranca_id: uuid.UUID) -> HttpResponse:
        return pagamentos.emitir_recibo(_ator_id(request), cobranca_id)


# --- Recorrências e Suspensões ---


class RecorrenciasView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [LeGestao()]
        return [exige_permissao(PERM_COBRANCAS_CRIAR)()]

    @extend_schema(
        summary="Listar recorrências financeiras",
        parameters=[ConsultaRecorrenciasSerializer],
        responses=RecorrenciaSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaRecorrenciasSerializer, request.query_params)
        itens = recorrencias.listar(
            _ator_id(request),
            devedor_id=filtros.get("devedor_id"),
            incluir_inativas=filtros["todas"],
        )
        return Response(RecorrenciaSerializer(itens, many=True).data)

    @extend_schema(
        summary="Criar recorrência financeira",
        request=NovaRecorrenciaSerializer,
        responses={201: RecorrenciaSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NovaRecorrenciaSerializer, request.data)
        item = recorrencias.criar(
            _ator_id(request),
            devedor_id=dados["devedor_id"],
            categoria_id=dados["categoria_id"],
            descricao=dados["descricao"],
            valor=_dinheiro_positivo(dados["valor"]),
            periodicidade=dados["periodicidade"],
            dia_vencimento=dados["dia_vencimento"],
            mes_vencimento=dados.get("mes_vencimento"),
            antecedencia_dias=dados["antecedencia_dias"],
            limite_de_inadimplencia=dados["limite_de_inadimplencia"],
            chave_pix_id=dados.get("chave_pix_id"),
            a_partir_de=dados.get("a_partir_de"),
        )
        return Response(RecorrenciaSerializer(item).data, status=status.HTTP_201_CREATED)


class RecorrenciaEditarView(APIView):
    permission_classes = (exige_permissao(PERM_COBRANCAS_CRIAR),)

    @extend_schema(
        summary="Editar recorrência financeira",
        request=EditarRecorrenciaSerializer,
        responses=RecorrenciaSerializer,
    )
    def post(self, request: Request, recorrencia_id: uuid.UUID) -> Response:
        dados = _validar(EditarRecorrenciaSerializer, request.data)
        item = recorrencias.editar(
            _ator_id(request),
            recorrencia_id,
            categoria_id=dados["categoria_id"],
            descricao=dados["descricao"],
            valor=_dinheiro_positivo(dados["valor"]),
            dia_vencimento=dados["dia_vencimento"],
            mes_vencimento=dados.get("mes_vencimento"),
            antecedencia_dias=dados["antecedencia_dias"],
            limite_de_inadimplencia=dados["limite_de_inadimplencia"],
            chave_pix_id=dados.get("chave_pix_id"),
        )
        return Response(RecorrenciaSerializer(item).data)


class RecorrenciaDesativarView(APIView):
    permission_classes = (exige_permissao(PERM_COBRANCAS_CRIAR),)

    @extend_schema(summary="Desativar recorrência", request=None, responses=RecorrenciaSerializer)
    def post(self, request: Request, recorrencia_id: uuid.UUID) -> Response:
        item = recorrencias.desativar(_ator_id(request), recorrencia_id)
        return Response(RecorrenciaSerializer(item).data)


class RecorrenciaHistoricoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Histórico da recorrência", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, recorrencia_id: uuid.UUID) -> Response:
        registros = recorrencias.historico(_ator_id(request), recorrencia_id)
        return Response(HistoricoSerializer(consulta.serializar_historico(registros), many=True).data)


class SuspensoesView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [LeGestao()]
        return [exige_permissao(PERM_COBRANCAS_SUSPENDER)()]

    @extend_schema(
        summary="Listar suspensões de recorrência",
        parameters=[ConsultaSuspensoesSerializer],
        responses=SuspensaoSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaSuspensoesSerializer, request.query_params)
        itens = suspensoes.listar(
            _ator_id(request),
            diretor_id=filtros.get("diretor_id"),
            incluir_encerradas=filtros["todas"],
        )
        return Response(SuspensaoSerializer(itens, many=True).data)

    @extend_schema(
        summary="Criar suspensão temporária de cobrança recorrente",
        request=NovaSuspensaoSerializer,
        responses={201: SuspensaoSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NovaSuspensaoSerializer, request.data)
        item = suspensoes.criar(
            _ator_id(request),
            diretor_id=dados["diretor_id"],
            recorrencia_id=dados.get("recorrencia_id"),
            inicio=dados["inicio"],
            fim=dados.get("fim"),
            justificativa=dados["justificativa"],
        )
        return Response(SuspensaoSerializer(item).data, status=status.HTTP_201_CREATED)


class SuspensaoEncerrarView(APIView):
    permission_classes = (exige_permissao(PERM_COBRANCAS_SUSPENDER),)

    @extend_schema(summary="Encerrar suspensão vigente", request=None, responses=SuspensaoSerializer)
    def post(self, request: Request, suspensao_id: uuid.UUID) -> Response:
        item = suspensoes.encerrar(_ator_id(request), suspensao_id)
        return Response(SuspensaoSerializer(item).data)


class SuspensaoHistoricoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Histórico da suspensão", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, suspensao_id: uuid.UUID) -> Response:
        registros = suspensoes.historico(_ator_id(request), suspensao_id)
        return Response(HistoricoSerializer(consulta.serializar_historico(registros), many=True).data)
