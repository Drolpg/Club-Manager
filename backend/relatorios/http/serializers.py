"""Serializers do perfil: só de saída, com os campos declarados (ADR-004). O modelo nunca sai como está."""

from typing import Any

from rest_framework import serializers


class DadosSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    nome_de_usuario = serializers.CharField()
    email = serializers.CharField()
    telefone = serializers.CharField()
    ativo = serializers.BooleanField()
    admin = serializers.BooleanField()
    cadastrado_em = serializers.DateTimeField()
    cargo = serializers.CharField(allow_null=True)
    setores = serializers.ListField(child=serializers.CharField())


class PagamentoSerializer(serializers.Serializer[Any]):
    forma = serializers.CharField()
    data_pagamento = serializers.DateField()
    situacao = serializers.CharField()


class CobrancaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    descricao = serializers.CharField()
    categoria_nome = serializers.CharField()
    valor = serializers.CharField()
    vencimento = serializers.DateField()
    situacao = serializers.CharField()
    pagamentos = PagamentoSerializer(many=True)


class PaginaDeCobrancasSerializer(serializers.Serializer[Any]):
    itens = CobrancaSerializer(many=True)
    tem_mais = serializers.BooleanField()


class EventoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    titulo = serializers.CharField()
    inicio = serializers.DateTimeField()
    local = serializers.CharField()
    categoria_nome = serializers.CharField()
    situacao = serializers.CharField()
    papel = serializers.CharField()
    resposta = serializers.CharField(allow_null=True)


class PaginaDeEventosSerializer(serializers.Serializer[Any]):
    itens = EventoSerializer(many=True)
    tem_mais = serializers.BooleanField()


class NotificacoesSerializer(serializers.Serializer[Any]):
    nao_lidas = serializers.IntegerField()


class PerfilSerializer(serializers.Serializer[Any]):
    """As quatro seções; `notificacoes` só existe quando o alvo é quem consulta (a view a retira)."""

    dados = DadosSerializer()
    cobrancas = PaginaDeCobrancasSerializer()
    eventos = PaginaDeEventosSerializer()
    notificacoes = NotificacoesSerializer(required=False, allow_null=True)


# Dashboard (spec `relatorios/dashboard-e-lancamentos`): valores em texto e campos declarados.


def _dinheiro() -> serializers.DecimalField:
    return serializers.DecimalField(max_digits=14, decimal_places=2, coerce_to_string=True)


class QuantidadeETotalSerializer(serializers.Serializer[Any]):
    quantidade = serializers.IntegerField()
    total = _dinheiro()


class ProximaCobrancaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    descricao = serializers.CharField()
    valor = _dinheiro()
    vencimento = serializers.DateField()


class MinhasCobrancasSerializer(serializers.Serializer[Any]):
    em_aberto = QuantidadeETotalSerializer()
    atrasadas = QuantidadeETotalSerializer()
    em_validacao = QuantidadeETotalSerializer()
    proxima = ProximaCobrancaSerializer(allow_null=True)


class DoMesSerializer(serializers.Serializer[Any]):
    entradas = _dinheiro()
    saidas = _dinheiro()
    resultado = _dinheiro()
    saldo_acumulado = _dinheiro()
    a_receber = QuantidadeETotalSerializer()


class PendenciasDeValidacaoSerializer(serializers.Serializer[Any]):
    pagamentos = QuantidadeETotalSerializer()
    entradas = QuantidadeETotalSerializer()


class EmAnalisePorTipoSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField()
    nome = serializers.CharField()
    quantidade = serializers.IntegerField()


class PendenciasDeAprovacaoSerializer(serializers.Serializer[Any]):
    minha_fila = serializers.IntegerField()
    por_tipo = EmAnalisePorTipoSerializer(many=True)


class PrestacoesPendentesSerializer(serializers.Serializer[Any]):
    aguardando = serializers.IntegerField()
    em_atraso = serializers.IntegerField()
    em_conferencia = serializers.IntegerField()


class InadimplenciaSerializer(serializers.Serializer[Any]):
    cobrancas = serializers.IntegerField()
    devedores = serializers.IntegerField()
    total = _dinheiro()


class HojeSerializer(serializers.Serializer[Any]):
    comprometido = _dinheiro()
    saldo_livre = _dinheiro()
    pendencias_de_validacao = PendenciasDeValidacaoSerializer()
    pendencias_de_aprovacao = PendenciasDeAprovacaoSerializer()
    prestacoes_pendentes = PrestacoesPendentesSerializer()
    inadimplencia = InadimplenciaSerializer()

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        # `data` é o nome do contrato (spec técnica), mas um atributo `data` esconderia a propriedade `.data`.
        return {"data": serializers.DateField(), **super().get_fields()}


class ProximoEventoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    titulo = serializers.CharField()
    inicio = serializers.DateTimeField()
    categoria_nome = serializers.CharField()


class ComunicadoRecenteSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    titulo = serializers.CharField()
    publicado_em = serializers.DateTimeField()
    fixado = serializers.BooleanField()


class MesesSerializer(serializers.Serializer[Any]):
    de = serializers.CharField(help_text="Primeiro mês com lançamento realizado (ou o corrente), AAAA-MM")
    ate = serializers.CharField(help_text="O mês corrente, AAAA-MM")


class DashboardCompletoSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField(help_text="COMPLETO")
    mes = serializers.CharField(help_text="AAAA-MM")
    meses = MesesSerializer()
    do_mes = DoMesSerializer()
    hoje = HojeSerializer()
    proximos_eventos = ProximoEventoSerializer(many=True)
    ultimos_comunicados = ComunicadoRecenteSerializer(many=True)
    minhas_cobrancas = MinhasCobrancasSerializer()


class DashboardBasicoSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField(help_text="BASICO")
    classificacao_pendente = serializers.BooleanField()
    minhas_cobrancas = MinhasCobrancasSerializer()
    notificacoes_nao_lidas = serializers.IntegerField()


# Relatórios em PDF e CSV ---------------------------------------------------------------------------------


class TipoDeRelatorioSerializer(serializers.Serializer[Any]):
    codigo = serializers.CharField()
    nome = serializers.CharField()
    formatos = serializers.ListField(child=serializers.CharField())
    parametros = serializers.CharField(help_text="PERIODO, PERIODO_E_PENDENTES, MESES ou NENHUM")


class PedirRelatorioSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField(max_length=40)
    formato = serializers.CharField(max_length=3)
    parametros = serializers.DictField(required=False, default=dict)


class PedidoDeRelatorioSerializer(serializers.Serializer[Any]):
    """Os campos do pedido; nunca a chave do arquivo (CA-28)."""

    id = serializers.UUIDField()
    tipo = serializers.CharField()
    tipo_nome = serializers.CharField()
    formato = serializers.CharField()
    parametros = serializers.DictField()
    situacao = serializers.CharField()
    pedido_em = serializers.DateTimeField()
    concluido_em = serializers.DateTimeField(allow_null=True)
    expira_em = serializers.DateTimeField(allow_null=True)
    disponivel = serializers.BooleanField()
    codigo_da_falha = serializers.CharField()


class PaginaDePedidosSerializer(serializers.Serializer[Any]):
    itens = PedidoDeRelatorioSerializer(many=True)
    tem_mais = serializers.BooleanField()
