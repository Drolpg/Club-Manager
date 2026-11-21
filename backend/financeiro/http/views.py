"""Rotas HTTP da API financeira (`/api/v1/financeiro/...`). Sem regra de negócio."""

import uuid
from collections.abc import Callable
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
    PERM_ENTRADAS_REGISTRAR,
    PERM_ENTRADAS_VALIDAR,
    PERM_FINANCEIRO_ESTORNAR,
    PERM_PAGAMENTOS_VALIDAR,
    PERM_QUESTIONAMENTOS_DECIDIR,
    PERM_SAIDAS_ENVIAR,
    PERM_SAIDAS_LIQUIDAR,
)
from financeiro.erros import erro
from financeiro.http.permissions import DiretorAtivo, EhAdmin, LeGestao, exige_permissao
from financeiro.http.serializers import (
    CancelarCobrancaSerializer,
    CategoriaSerializer,
    ChavePixSerializer,
    CobrancaDetalheSerializer,
    CobrancaItemSerializer,
    ComplementoCriadoSerializer,
    ConsultaCategoriasSerializer,
    ConsultaChavesPixSerializer,
    ConsultaCobrancasSerializer,
    ConsultaEntradasSerializer,
    ConsultaEstornosSerializer,
    ConsultaMinhasCobrancasSerializer,
    ConsultaRecorrenciasSerializer,
    ConsultaResumoEntradasSerializer,
    ConsultaSaidasSerializer,
    ConsultaSuspensoesSerializer,
    CotacaoSerializer,
    DecidirDividaSerializer,
    DecidirEntradaSerializer,
    DecidirPagamentoSerializer,
    DecidirQuestionamentoSerializer,
    DevolverPrestacaoSerializer,
    EditarChavePixSerializer,
    EditarRecorrenciaSerializer,
    EntradaSerializer,
    EstornoCobrancaRespostaSerializer,
    EstornoEntradaRespostaSerializer,
    EstornoSaidaRespostaSerializer,
    HistoricoSerializer,
    IsentarCobrancaSerializer,
    JustificarDividaSerializer,
    LiquidarSaidaSerializer,
    NomeCategoriaSerializer,
    NovaCategoriaSerializer,
    NovaChavePixSerializer,
    NovaCobrancaSerializer,
    NovaEntradaSerializer,
    NovaRecorrenciaSerializer,
    NovaSolicitacaoGastoSerializer,
    NovaSuspensaoSerializer,
    NovoLoteCobrancasSerializer,
    PaginaCobrancasSerializer,
    PaginaEntradasSerializer,
    PaginaEstornosSerializer,
    PaginaSaidasSerializer,
    PedirComplementoSerializer,
    QuestionarCobrancaSerializer,
    RecorrenciaSerializer,
    ReferenciasGastosSerializer,
    RegistrarDevolucaoSaidaSerializer,
    RegistrarEnvioSaidaSerializer,
    RegistrarEstornoSerializer,
    RegistrarPagamentoSerializer,
    RegistrarPrestacaoSerializer,
    RenegociarDividaSerializer,
    ResumoEntradasSerializer,
    SaidaDetalheSerializer,
    SolicitacaoGastoCriadaSerializer,
    SuspensaoSerializer,
    UploadCotacaoSerializer,
    VisaoDoCaixaSerializer,
)
from financeiro.services import (
    categorias,
    chaves_pix,
    cobrancas,
    consulta,
    entradas,
    estornos,
    gastos,
    inadimplencia,
    pagamentos,
    questionamentos,
    recorrencias,
    saidas,
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


# --- Entradas sem devedor ---


class EntradasView(APIView):
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "GET":
            return [LeGestao()]
        return [exige_permissao(PERM_ENTRADAS_REGISTRAR)()]

    @extend_schema(
        summary="Listar entradas sem devedor e devoluções",
        parameters=[ConsultaEntradasSerializer],
        responses=PaginaEntradasSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaEntradasSerializer, request.query_params)
        pagina = entradas.listar(
            _ator_id(request),
            situacao=filtros.get("situacao"),
            categoria_id=filtros.get("categoria_id"),
            de=filtros.get("de"),
            ate=filtros.get("ate"),
            antes=filtros.get("antes"),
            limite=filtros["limite"],
        )
        return Response(PaginaEntradasSerializer(pagina).data)

    @extend_schema(
        summary="Registrar entrada sem devedor",
        request=NovaEntradaSerializer,
        responses={201: EntradaSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NovaEntradaSerializer, request.data)
        item = entradas.registrar(
            _ator_id(request),
            categoria_id=dados["categoria_id"],
            valor=_dinheiro_positivo(dados["valor"]),
            data=dados["data"],
            origem=dados["origem"],
            evidencia_texto=dados["evidencia_texto"],
            arquivo=dados.get("comprovante"),
        )
        return Response(EntradaSerializer(item).data, status=status.HTTP_201_CREATED)


class EntradaResumoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Resumo consolidado das entradas validadas",
        parameters=[ConsultaResumoEntradasSerializer],
        responses=ResumoEntradasSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaResumoEntradasSerializer, request.query_params)
        resumo = entradas.resumo(
            _ator_id(request),
            de=filtros.get("de"),
            ate=filtros.get("ate"),
            categoria_id=filtros.get("categoria_id"),
        )
        return Response(ResumoEntradasSerializer(resumo).data)


class EntradaDetalheView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Detalhar entrada", responses=EntradaSerializer)
    def get(self, request: Request, entrada_id: uuid.UUID) -> Response:
        item = entradas.detalhe(_ator_id(request), entrada_id)
        return Response(EntradaSerializer(item).data)


class EntradaHistoricoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Histórico da entrada", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, entrada_id: uuid.UUID) -> Response:
        registros = entradas.historico(_ator_id(request), entrada_id)
        return Response(HistoricoSerializer(registros, many=True).data)


class EntradaComprovanteView(APIView):
    permission_classes = (DiretorAtivo,)

    @extend_schema(summary="Baixar comprovante privado da entrada", responses={200: OpenApiTypes.BINARY})
    def get(self, request: Request, entrada_id: uuid.UUID) -> HttpResponse:
        return entradas.baixar_comprovante(_ator_id(request), entrada_id)


class EntradaValidarView(APIView):
    permission_classes = (exige_permissao(PERM_ENTRADAS_VALIDAR),)

    @extend_schema(
        summary="Validar entrada",
        request=DecidirEntradaSerializer,
        responses=EntradaSerializer,
    )
    def post(self, request: Request, entrada_id: uuid.UUID) -> Response:
        dados = _validar(DecidirEntradaSerializer, request.data)
        item = entradas.validar(
            _ator_id(request),
            entrada_id,
            motivo_id=dados["motivo_id"],
            texto=dados["texto"],
        )
        return Response(EntradaSerializer(item).data)


class EntradaRejeitarView(APIView):
    permission_classes = (exige_permissao(PERM_ENTRADAS_VALIDAR),)

    @extend_schema(
        summary="Rejeitar entrada",
        request=DecidirEntradaSerializer,
        responses=EntradaSerializer,
    )
    def post(self, request: Request, entrada_id: uuid.UUID) -> Response:
        dados = _validar(DecidirEntradaSerializer, request.data)
        item = entradas.rejeitar(
            _ator_id(request),
            entrada_id,
            motivo_id=dados["motivo_id"],
            texto=dados["texto"],
        )
        return Response(EntradaSerializer(item).data)


# --- Caixa, Gastos, Saídas e Estornos ---


def _executar_estorno(
    request: Request,
    alvo_id: uuid.UUID,
    servico: Callable[..., dict[str, Any]],
    serializer_cls: type[Any],
) -> Response:
    dados = _validar(RegistrarEstornoSerializer, request.data)
    resultado = servico(
        _ator_id(request),
        alvo_id,
        motivo_id=dados["motivo_id"],
        justificativa=dados["justificativa"],
    )
    return Response(serializer_cls(resultado).data, status=status.HTTP_201_CREATED)


class CaixaView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Visão consolidada do caixa", responses=VisaoDoCaixaSerializer)
    def get(self, request: Request) -> Response:
        visao = consulta.obter_visao_do_caixa(_ator_id(request))
        return Response(VisaoDoCaixaSerializer(visao).data)


class ReferenciasGastosView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Categorias, setores e pessoas para gastos e saídas",
        responses=ReferenciasGastosSerializer,
    )
    def get(self, request: Request) -> Response:
        dados = gastos.referencias(_ator_id(request))
        return Response(ReferenciasGastosSerializer(dados).data)


class CotacoesView(APIView):
    permission_classes = (LeGestao,)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        summary="Enviar arquivo de cotação",
        request=UploadCotacaoSerializer,
        responses={201: CotacaoSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(UploadCotacaoSerializer, request.data)
        cot = gastos.upload_cotacao(_ator_id(request), dados["arquivo"])
        return Response(
            CotacaoSerializer(
                {
                    "id": cot.id,
                    "nome": cot.nome,
                    "mime": cot.mime,
                    "tamanho": cot.tamanho,
                    "criada_em": cot.criada_em,
                }
            ).data,
            status=status.HTTP_201_CREATED,
        )


class CotacaoDownloadView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Baixar cotação", responses={200: OpenApiTypes.BINARY})
    def get(self, request: Request, cotacao_id: uuid.UUID) -> HttpResponse:
        return gastos.baixar_cotacao(_ator_id(request), cotacao_id)


class GastosView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Abrir solicitação estruturada de gasto",
        request=NovaSolicitacaoGastoSerializer,
        responses={201: SolicitacaoGastoCriadaSerializer},
    )
    def post(self, request: Request) -> Response:
        dados = _validar(NovaSolicitacaoGastoSerializer, request.data)
        itens = [{"descricao": i["descricao"], "valor": str(i["valor"])} for i in dados["itens"]]
        info = gastos.abrir_solicitacao(
            _ator_id(request),
            descricao=dados["descricao"],
            categoria_id=dados["categoria_id"],
            setor_id=dados["setor_id"],
            itens=itens,
            cotacao_id=dados.get("cotacao_id"),
            aprovador_indicado_id=dados.get("aprovador_indicado_id"),
        )
        payload = {
            "id": info.id,
            "tipo": info.tipo,
            "situacao": info.situacao.value,
            "solicitante_id": info.solicitante_id,
            "aprovador_indicado_id": info.aprovador_indicado_id,
            "versao_atual": info.versao_atual,
            "valor": info.valor,
            "resumo": info.resumo,
            "conteudo": info.conteudo,
        }
        return Response(SolicitacaoGastoCriadaSerializer(payload).data, status=status.HTTP_201_CREATED)


class SaidasView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Listar saídas e filas operacionais",
        parameters=[ConsultaSaidasSerializer],
        responses=PaginaSaidasSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaSaidasSerializer, request.query_params)
        pagina = consulta.listar_saidas(
            _ator_id(request),
            situacao=filtros.get("situacao"),
            categoria_id=filtros.get("categoria_id"),
            setor_id=filtros.get("setor_id"),
            solicitante_id=filtros.get("solicitante_id"),
            evento_id=filtros.get("evento_id"),
            de=filtros.get("de"),
            ate=filtros.get("ate"),
            pendentes_envio=filtros["pendentes_envio"],
            pendentes_prestacao=filtros["pendentes_prestacao"],
            atrasadas=filtros["atrasadas"],
            antes=filtros.get("antes"),
            limite=filtros["limite"],
        )
        return Response(PaginaSaidasSerializer(pagina).data)


class SaidaDetalheView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Detalhar saída", responses=SaidaDetalheSerializer)
    def get(self, request: Request, saida_id: uuid.UUID) -> Response:
        item = consulta.detalhe_saida(_ator_id(request), saida_id)
        return Response(SaidaDetalheSerializer(item).data)


class SaidaHistoricoView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Histórico da saída", responses=HistoricoSerializer(many=True))
    def get(self, request: Request, saida_id: uuid.UUID) -> Response:
        registros = consulta.historico_saida(_ator_id(request), saida_id)
        return Response(HistoricoSerializer(registros, many=True).data)


class SaidaEnviosView(APIView):
    permission_classes = (exige_permissao(PERM_SAIDAS_ENVIAR),)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(
        summary="Registrar envio de recurso para a saída",
        request=RegistrarEnvioSaidaSerializer,
        responses={201: SaidaDetalheSerializer},
    )
    def post(self, request: Request, saida_id: uuid.UUID) -> Response:
        dados = _validar(RegistrarEnvioSaidaSerializer, request.data)
        item = saidas.enviar_recurso(
            _ator_id(request),
            saida_id,
            valor=_dinheiro_positivo(dados["valor"]),
            arquivo=dados.get("comprovante"),
            enviado_em=dados.get("enviado_em"),
            complemento_id=dados.get("complemento_id"),
        )
        return Response(SaidaDetalheSerializer(item).data, status=status.HTTP_201_CREATED)


class SaidaEnvioComprovanteView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Baixar comprovante de envio", responses={200: OpenApiTypes.BINARY})
    def get(self, request: Request, saida_id: uuid.UUID, envio_id: uuid.UUID) -> HttpResponse:
        return saidas.baixar_comprovante_envio(_ator_id(request), saida_id, envio_id)


class SaidaPrestacoesView(APIView):
    permission_classes = (LeGestao,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(
        summary="Enviar prestação de contas da saída",
        request=RegistrarPrestacaoSerializer,
        responses={201: SaidaDetalheSerializer},
    )
    def post(self, request: Request, saida_id: uuid.UUID) -> Response:
        dados = _validar(RegistrarPrestacaoSerializer, request.data)
        item = saidas.prestar_contas(
            _ator_id(request),
            saida_id,
            valor=_dinheiro_positivo(dados["valor"]),
            descricao=dados["descricao"],
            arquivo=dados.get("comprovante"),
        )
        return Response(SaidaDetalheSerializer(item).data, status=status.HTTP_201_CREATED)


class SaidaPrestacaoComprovanteView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(summary="Baixar comprovante de prestação", responses={200: OpenApiTypes.BINARY})
    def get(self, request: Request, saida_id: uuid.UUID, prestacao_id: uuid.UUID) -> HttpResponse:
        return saidas.baixar_comprovante_prestacao(_ator_id(request), saida_id, prestacao_id)


class SaidaDevolverPrestacaoView(APIView):
    permission_classes = (exige_permissao(PERM_SAIDAS_LIQUIDAR),)

    @extend_schema(
        summary="Devolver prestação de contas para ajuste",
        request=DevolverPrestacaoSerializer,
        responses=SaidaDetalheSerializer,
    )
    def post(self, request: Request, saida_id: uuid.UUID) -> Response:
        dados = _validar(DevolverPrestacaoSerializer, request.data)
        item = saidas.devolver_prestacao(
            _ator_id(request),
            saida_id,
            motivo_id=dados["motivo_id"],
            texto=dados["texto"],
        )
        return Response(SaidaDetalheSerializer(item).data)


class SaidaDevolucoesView(APIView):
    permission_classes = (LeGestao,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(
        summary="Registrar devolução de sobra vinculada à saída",
        request=RegistrarDevolucaoSaidaSerializer,
        responses={201: EntradaSerializer},
    )
    def post(self, request: Request, saida_id: uuid.UUID) -> Response:
        dados = _validar(RegistrarDevolucaoSaidaSerializer, request.data)
        item = saidas.devolver_sobra(
            _ator_id(request),
            saida_id,
            valor=_dinheiro_positivo(dados["valor"]),
            data_devolucao=dados.get("data"),
            categoria_id=dados.get("categoria_id"),
            origem=dados["origem"],
            evidencia_texto=dados["evidencia_texto"],
            arquivo=dados.get("comprovante"),
        )
        return Response(EntradaSerializer(item).data, status=status.HTTP_201_CREATED)


class SaidaComplementosView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Solicitar complemento de recurso para saída em conferência",
        request=PedirComplementoSerializer,
        responses={201: ComplementoCriadoSerializer},
    )
    def post(self, request: Request, saida_id: uuid.UUID) -> Response:
        dados = _validar(PedirComplementoSerializer, request.data)
        itens = [{"descricao": i["descricao"], "valor": str(i["valor"])} for i in dados["itens"]]
        item = saidas.pedir_complemento(
            _ator_id(request),
            saida_id,
            itens=itens,
            descricao=dados["descricao"],
            cotacao_id=dados.get("cotacao_id"),
            aprovador_indicado_id=dados.get("aprovador_indicado_id"),
        )
        return Response(ComplementoCriadoSerializer(item).data, status=status.HTTP_201_CREATED)


class SaidaLiquidarView(APIView):
    permission_classes = (exige_permissao(PERM_SAIDAS_LIQUIDAR),)

    @extend_schema(
        summary="Liquidar saída após fechamento de contas",
        request=LiquidarSaidaSerializer,
        responses=SaidaDetalheSerializer,
    )
    def post(self, request: Request, saida_id: uuid.UUID) -> Response:
        dados = _validar(LiquidarSaidaSerializer, request.data)
        item = saidas.liquidar(_ator_id(request), saida_id, justificativa=dados["justificativa"])
        return Response(SaidaDetalheSerializer(item).data)


class SaidaEstornarView(APIView):
    permission_classes = (exige_permissao(PERM_FINANCEIRO_ESTORNAR),)

    @extend_schema(
        summary="Estornar saída liquidada",
        request=RegistrarEstornoSerializer,
        responses={201: EstornoSaidaRespostaSerializer},
    )
    def post(self, request: Request, saida_id: uuid.UUID) -> Response:
        return _executar_estorno(request, saida_id, estornos.estornar_saida, EstornoSaidaRespostaSerializer)


class EntradaEstornarView(APIView):
    permission_classes = (exige_permissao(PERM_FINANCEIRO_ESTORNAR),)

    @extend_schema(
        summary="Estornar entrada validada",
        request=RegistrarEstornoSerializer,
        responses={201: EstornoEntradaRespostaSerializer},
    )
    def post(self, request: Request, entrada_id: uuid.UUID) -> Response:
        return _executar_estorno(
            request, entrada_id, estornos.estornar_entrada, EstornoEntradaRespostaSerializer
        )


class CobrancaEstornarView(APIView):
    permission_classes = (exige_permissao(PERM_FINANCEIRO_ESTORNAR),)

    @extend_schema(
        summary="Estornar cobrança paga",
        request=RegistrarEstornoSerializer,
        responses={201: EstornoCobrancaRespostaSerializer},
    )
    def post(self, request: Request, cobranca_id: uuid.UUID) -> Response:
        return _executar_estorno(
            request, cobranca_id, estornos.estornar_cobranca, EstornoCobrancaRespostaSerializer
        )


class EstornosView(APIView):
    permission_classes = (LeGestao,)

    @extend_schema(
        summary="Listar lançamentos de estorno",
        parameters=[ConsultaEstornosSerializer],
        responses=PaginaEstornosSerializer,
    )
    def get(self, request: Request) -> Response:
        filtros = _validar(ConsultaEstornosSerializer, request.query_params)
        pagina = estornos.listar(
            _ator_id(request),
            alvo_tipo=filtros.get("alvo_tipo"),
            antes=filtros.get("antes"),
            limite=filtros["limite"],
        )
        return Response(PaginaEstornosSerializer(pagina).data)
