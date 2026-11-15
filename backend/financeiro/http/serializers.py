"""Serializers de entrada e saída das rotas financeiras (ADR-004: campos explícitos)."""

from typing import Any

from rest_framework import serializers

from financeiro.domain.competencia import Periodicidade
from financeiro.domain.pix import TipoChavePix
from financeiro.domain.transicoes import SituacaoCobranca
from financeiro.models import DecisaoQuestionamento, FormaPagamento, NaturezaCategoria

_NATUREZAS = [c.value for c in NaturezaCategoria]
_TIPOS_PIX = [t.value for t in TipoChavePix]
_SITUACOES_COBRANCA = [s.value for s in SituacaoCobranca]
_FORMAS_PAGAMENTO = [f.value for f in FormaPagamento]
_PERIODICIDADES = [p.value for p in Periodicidade]
_DECISOES_QUESTIONAMENTO = [d.value for d in DecisaoQuestionamento]


def _dinheiro(**extra: Any) -> serializers.DecimalField:
    return serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True, **extra)


class PessoaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()


class HistoricoSerializer(serializers.Serializer[Any]):
    """Uma ação do histórico. `ator` é nulo para ações automáticas do sistema."""

    acao = serializers.CharField()
    ator = PessoaSerializer(allow_null=True)
    justificativa = serializers.CharField(allow_blank=True)
    dados = serializers.DictField()
    criado_em = serializers.DateTimeField()


# --- Categorias ---


class CategoriaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    natureza = serializers.CharField()
    ativa = serializers.BooleanField()
    criada_em = serializers.DateTimeField()


class ConsultaCategoriasSerializer(serializers.Serializer[Any]):
    natureza = serializers.ChoiceField(choices=_NATUREZAS, required=False)
    todas = serializers.BooleanField(required=False, default=False)


class NomeCategoriaSerializer(serializers.Serializer[Any]):
    nome = serializers.CharField(min_length=2, max_length=80)


class NovaCategoriaSerializer(NomeCategoriaSerializer):
    natureza = serializers.ChoiceField(choices=_NATUREZAS)


# --- Chaves Pix ---


class ChavePixSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    chave = serializers.CharField()
    nome_recebedor = serializers.CharField()
    cidade = serializers.CharField()
    padrao = serializers.BooleanField()
    ativa = serializers.BooleanField()
    criada_em = serializers.DateTimeField()


class ConsultaChavesPixSerializer(serializers.Serializer[Any]):
    todas = serializers.BooleanField(required=False, default=False)


class EditarChavePixSerializer(serializers.Serializer[Any]):
    tipo = serializers.ChoiceField(choices=_TIPOS_PIX)
    chave = serializers.CharField(min_length=3, max_length=140)
    nome_recebedor = serializers.CharField(min_length=2, max_length=100)
    cidade = serializers.CharField(min_length=2, max_length=60)


class NovaChavePixSerializer(EditarChavePixSerializer):
    padrao = serializers.BooleanField(required=False, default=False)


# --- Cobranças ---


class CobrancaItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    devedor = PessoaSerializer()
    categoria_id = serializers.UUIDField()
    categoria_nome = serializers.CharField()
    descricao = serializers.CharField()
    valor = _dinheiro()
    vencimento = serializers.DateField()
    situacao = serializers.CharField()
    tem_questionamento_aberto = serializers.BooleanField()
    tem_convocacao_aberta = serializers.BooleanField()
    recorrencia_id = serializers.UUIDField(allow_null=True)
    competencia = serializers.CharField(allow_blank=True)
    cobranca_origem_id = serializers.UUIDField(allow_null=True)
    criada_em = serializers.DateTimeField()


class PagamentoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    forma = serializers.CharField()
    data_pagamento = serializers.DateField()
    recebedor = PessoaSerializer(allow_null=True)
    comprovante_disponivel = serializers.BooleanField()
    comprovante_nome = serializers.CharField(allow_blank=True)
    situacao = serializers.CharField()
    decidido_por = PessoaSerializer(allow_null=True)
    motivo_texto = serializers.CharField(allow_blank=True)
    decisao_texto = serializers.CharField(allow_blank=True)
    registrado_em = serializers.DateTimeField()
    decidido_em = serializers.DateTimeField(allow_null=True)


class QuestionamentoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    texto = serializers.CharField()
    situacao = serializers.CharField()
    decisao = serializers.CharField(allow_null=True)
    decidido_por = PessoaSerializer(allow_null=True)
    motivo_texto = serializers.CharField(allow_blank=True)
    decisao_texto = serializers.CharField(allow_blank=True)
    aberto_em = serializers.DateTimeField()
    decidido_em = serializers.DateTimeField(allow_null=True)


class ConvocacaoSerializer(serializers.Serializer[Any]):
    convocado_em = serializers.DateTimeField()
    justificativa_do_devedor = serializers.CharField(allow_blank=True)
    justificada_em = serializers.DateTimeField(allow_null=True)
    decisao = serializers.CharField(allow_null=True)
    decidido_por = PessoaSerializer(allow_null=True)
    motivo_texto = serializers.CharField(allow_blank=True)
    decisao_texto = serializers.CharField(allow_blank=True)
    decidido_em = serializers.DateTimeField(allow_null=True)


class RenegociacaoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    valor_acordado = _dinheiro()
    quantidade_parcelas = serializers.IntegerField()
    decidido_por = PessoaSerializer()
    motivo_texto = serializers.CharField(allow_blank=True)
    decisao_texto = serializers.CharField(allow_blank=True)
    criada_em = serializers.DateTimeField()


class RegistroDecisaoPorSerializer(serializers.Serializer[Any]):
    por = PessoaSerializer()
    motivo_texto = serializers.CharField()
    texto = serializers.CharField(allow_blank=True)


class IsencaoInfoSerializer(serializers.Serializer[Any]):
    por = PessoaSerializer()
    justificativa = serializers.CharField()


class CobrancaDetalheSerializer(CobrancaItemSerializer):
    limite_de_inadimplencia = serializers.IntegerField()
    chave_pix_id = serializers.UUIDField()
    pix_chave = serializers.CharField()
    pix_nome_recebedor = serializers.CharField()
    pix_cidade = serializers.CharField()
    pix_copia_e_cola = serializers.CharField()
    qrcode_svg = serializers.CharField()
    pausada_por_questionamento_em = serializers.DateField(allow_null=True)
    dias_pausados_inadimplencia = serializers.IntegerField()
    isencao = IsencaoInfoSerializer(allow_null=True)
    cancelamento = RegistroDecisaoPorSerializer(allow_null=True)
    perdao = RegistroDecisaoPorSerializer(allow_null=True)
    paga_em = serializers.DateTimeField(allow_null=True)
    encerrada_em = serializers.DateTimeField(allow_null=True)
    atualizada_em = serializers.DateTimeField()
    pagamentos = PagamentoSerializer(many=True)
    questionamentos = QuestionamentoSerializer(many=True)
    convocacao = ConvocacaoSerializer(allow_null=True)
    renegociacao = RenegociacaoSerializer(allow_null=True)
    parcelas = CobrancaItemSerializer(many=True)
    acoes = serializers.ListField(child=serializers.CharField())


class PaginaCobrancasSerializer(serializers.Serializer[Any]):
    itens = CobrancaItemSerializer(many=True)
    tem_mais = serializers.BooleanField()


class ConsultaMinhasCobrancasSerializer(serializers.Serializer[Any]):
    situacao = serializers.ChoiceField(choices=_SITUACOES_COBRANCA, required=False)
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, default=20)


class ConsultaCobrancasSerializer(serializers.Serializer[Any]):
    situacao = serializers.ChoiceField(choices=_SITUACOES_COBRANCA, required=False)
    categoria_id = serializers.UUIDField(required=False)
    devedor_id = serializers.UUIDField(required=False)
    de = serializers.DateField(required=False)
    ate = serializers.DateField(required=False)
    inadimplentes = serializers.BooleanField(required=False, default=False)
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, default=20)


class _CamposComunsCobrancaSerializer(serializers.Serializer[Any]):
    categoria_id = serializers.UUIDField()
    descricao = serializers.CharField(min_length=2, max_length=200)
    # Sem min_value aqui: valores <= 0 são recusados no domínio como 422 VALOR_INVALIDO.
    valor = _dinheiro()
    vencimento = serializers.DateField()
    limite_de_inadimplencia = serializers.IntegerField(min_value=1, max_value=365, required=False, default=30)
    chave_pix_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class NovaCobrancaSerializer(_CamposComunsCobrancaSerializer):
    devedor_id = serializers.UUIDField()


class NovoLoteCobrancasSerializer(_CamposComunsCobrancaSerializer):
    devedor_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    todos_ativos_com_cargo = serializers.BooleanField(required=False, default=False)


class CancelarCobrancaSerializer(serializers.Serializer[Any]):
    motivo_id = serializers.UUIDField()
    texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class RegistrarPagamentoSerializer(serializers.Serializer[Any]):
    forma = serializers.ChoiceField(choices=_FORMAS_PAGAMENTO)
    data_pagamento = serializers.DateField()
    recebedor_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    comprovante = serializers.FileField(required=False, allow_null=True, default=None)


class DecidirPagamentoSerializer(serializers.Serializer[Any]):
    motivo_id = serializers.UUIDField()
    texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class IsentarCobrancaSerializer(serializers.Serializer[Any]):
    justificativa = serializers.CharField(min_length=2, max_length=1000)


class QuestionarCobrancaSerializer(serializers.Serializer[Any]):
    texto = serializers.CharField(min_length=2, max_length=1000)


class DecidirQuestionamentoSerializer(serializers.Serializer[Any]):
    decisao = serializers.ChoiceField(choices=_DECISOES_QUESTIONAMENTO)
    motivo_id = serializers.UUIDField()
    texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class JustificarDividaSerializer(serializers.Serializer[Any]):
    texto = serializers.CharField(min_length=2, max_length=1000)


class DecidirDividaSerializer(serializers.Serializer[Any]):
    motivo_id = serializers.UUIDField()
    texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class ParcelaRenegociacaoSerializer(serializers.Serializer[Any]):
    # Sem min_value: valores <= 0 são recusados no domínio como 422 VALOR_INVALIDO.
    valor = _dinheiro()
    vencimento = serializers.DateField()


class RenegociarDividaSerializer(serializers.Serializer[Any]):
    motivo_id = serializers.UUIDField()
    texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    parcelas = ParcelaRenegociacaoSerializer(many=True, allow_empty=True)


# --- Recorrências e Suspensões ---


class RecorrenciaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    devedor = PessoaSerializer()
    categoria_id = serializers.UUIDField()
    categoria_nome = serializers.CharField()
    descricao = serializers.CharField()
    valor = _dinheiro()
    periodicidade = serializers.CharField()
    dia_vencimento = serializers.IntegerField()
    mes_vencimento = serializers.IntegerField(allow_null=True)
    antecedencia_dias = serializers.IntegerField()
    limite_de_inadimplencia = serializers.IntegerField()
    chave_pix_id = serializers.UUIDField()
    ativa = serializers.BooleanField()
    a_partir_de = serializers.DateField()
    criada_em = serializers.DateTimeField()


class ConsultaRecorrenciasSerializer(serializers.Serializer[Any]):
    devedor_id = serializers.UUIDField(required=False)
    todas = serializers.BooleanField(required=False, default=False)


class EditarRecorrenciaSerializer(serializers.Serializer[Any]):
    categoria_id = serializers.UUIDField()
    descricao = serializers.CharField(min_length=2, max_length=200)
    valor = _dinheiro()
    dia_vencimento = serializers.IntegerField(min_value=1, max_value=31)
    mes_vencimento = serializers.IntegerField(
        min_value=1, max_value=12, required=False, allow_null=True, default=None
    )
    antecedencia_dias = serializers.IntegerField(min_value=0, max_value=90, required=False, default=5)
    limite_de_inadimplencia = serializers.IntegerField(min_value=1, max_value=365, required=False, default=30)
    chave_pix_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class NovaRecorrenciaSerializer(EditarRecorrenciaSerializer):
    devedor_id = serializers.UUIDField()
    periodicidade = serializers.ChoiceField(choices=_PERIODICIDADES)
    a_partir_de = serializers.DateField(required=False, allow_null=True, default=None)


class SuspensaoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    diretor = PessoaSerializer()
    recorrencia_id = serializers.UUIDField(allow_null=True)
    inicio = serializers.DateField()
    fim = serializers.DateField(allow_null=True)
    justificativa = serializers.CharField()
    situacao = serializers.CharField()
    criada_em = serializers.DateTimeField()
    encerrada_em = serializers.DateTimeField(allow_null=True)


class ConsultaSuspensoesSerializer(serializers.Serializer[Any]):
    diretor_id = serializers.UUIDField(required=False)
    todas = serializers.BooleanField(required=False, default=False)


class NovaSuspensaoSerializer(serializers.Serializer[Any]):
    diretor_id = serializers.UUIDField()
    recorrencia_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    inicio = serializers.DateField()
    fim = serializers.DateField(required=False, allow_null=True, default=None)
    justificativa = serializers.CharField(min_length=2, max_length=1000)
