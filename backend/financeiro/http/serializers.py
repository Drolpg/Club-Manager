"""Serializers de entrada e saída das rotas financeiras (ADR-004: campos explícitos)."""

from typing import Any

from rest_framework import serializers

from financeiro.domain.competencia import Periodicidade
from financeiro.domain.pix import TipoChavePix
from financeiro.domain.realizado import EstadoDoLancamento, TipoDeLancamento
from financeiro.domain.transicoes import SituacaoCobranca, SituacaoEntrada, SituacaoSaida
from financeiro.models import AlvoEstorno, DecisaoQuestionamento, FormaPagamento, NaturezaCategoria

_NATUREZAS = [c.value for c in NaturezaCategoria]
_TIPOS_PIX = [t.value for t in TipoChavePix]
_SITUACOES_COBRANCA = [s.value for s in SituacaoCobranca]
_SITUACOES_ENTRADA = [s.value for s in SituacaoEntrada]
_SITUACOES_SAIDA = [s.value for s in SituacaoSaida]
_ALVOS_ESTORNO = [a.value for a in AlvoEstorno]
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


class EstornoResumoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    valor = _dinheiro()
    motivo_texto = serializers.CharField()
    justificativa = serializers.CharField()
    registrado_por = PessoaSerializer()
    registrado_em = serializers.DateTimeField()


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
    estorno = EstornoResumoSerializer(allow_null=True)
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


class EntradaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    categoria_id = serializers.UUIDField()
    categoria_nome = serializers.CharField()
    saida_id = serializers.UUIDField(allow_null=True)
    valor = _dinheiro()
    data = serializers.DateField()  # type: ignore[assignment]
    origem = serializers.CharField()
    evidencia_texto = serializers.CharField(allow_blank=True)
    comprovante_disponivel = serializers.BooleanField()
    comprovante_nome = serializers.CharField(allow_blank=True)
    registrada_por = PessoaSerializer()
    situacao = serializers.CharField()
    decidido_por = PessoaSerializer(allow_null=True)
    motivo_texto = serializers.CharField(allow_blank=True)
    decisao_texto = serializers.CharField(allow_blank=True)
    registrada_em = serializers.DateTimeField()
    decidido_em = serializers.DateTimeField(allow_null=True)
    estorno = EstornoResumoSerializer(allow_null=True)
    acoes = serializers.ListField(child=serializers.CharField())


class PaginaEntradasSerializer(serializers.Serializer[Any]):
    itens = EntradaSerializer(many=True)
    tem_mais = serializers.BooleanField()


class ConsultaEntradasSerializer(serializers.Serializer[Any]):
    situacao = serializers.ChoiceField(choices=_SITUACOES_ENTRADA, required=False)
    categoria_id = serializers.UUIDField(required=False)
    de = serializers.DateField(required=False)
    ate = serializers.DateField(required=False)
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, default=20)


class ConsultaResumoEntradasSerializer(serializers.Serializer[Any]):
    categoria_id = serializers.UUIDField(required=False)
    de = serializers.DateField(required=False)
    ate = serializers.DateField(required=False)


class ResumoEntradasSerializer(serializers.Serializer[Any]):
    quantidade = serializers.IntegerField()
    total = _dinheiro()


class NovaEntradaSerializer(serializers.Serializer[Any]):
    categoria_id = serializers.UUIDField()
    # Sem min_value aqui: valores <= 0 são recusados no domínio como 422 VALOR_INVALIDO.
    valor = _dinheiro()
    data = serializers.DateField()  # type: ignore[assignment]
    origem = serializers.CharField(min_length=2, max_length=150)
    evidencia_texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    comprovante = serializers.FileField(required=False, allow_null=True, default=None)


class DecidirEntradaSerializer(serializers.Serializer[Any]):
    motivo_id = serializers.UUIDField()
    texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


# --- Gastos, Saídas, Caixa e Estornos ---


class VisaoDoCaixaSerializer(serializers.Serializer[Any]):
    total_entradas_validadas = _dinheiro()
    total_saidas_liquidadas = _dinheiro()
    total_comprometido = _dinheiro()


class ReferenciaItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()


class ReferenciasGastosSerializer(serializers.Serializer[Any]):
    categorias_saida = ReferenciaItemSerializer(many=True)
    categorias_entrada = ReferenciaItemSerializer(many=True)
    setores = ReferenciaItemSerializer(many=True)
    aprovadores_gastos = PessoaSerializer(many=True)
    diretores_ativos = PessoaSerializer(many=True)


class UploadCotacaoSerializer(serializers.Serializer[Any]):
    arquivo = serializers.FileField()


class CotacaoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    mime = serializers.CharField()
    tamanho = serializers.IntegerField()
    criada_em = serializers.DateTimeField()


class ItemGastoSerializer(serializers.Serializer[Any]):
    descricao = serializers.CharField(max_length=160, allow_blank=True)
    valor = _dinheiro()


class NovaSolicitacaoGastoSerializer(serializers.Serializer[Any]):
    descricao = serializers.CharField(max_length=200, allow_blank=True)
    categoria_id = serializers.UUIDField()
    setor_id = serializers.UUIDField()
    itens = ItemGastoSerializer(many=True)
    cotacao_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    aprovador_indicado_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class SolicitacaoGastoCriadaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    situacao = serializers.CharField()
    solicitante_id = serializers.UUIDField()
    aprovador_indicado_id = serializers.UUIDField(allow_null=True)
    versao_atual = serializers.IntegerField()
    valor = _dinheiro(allow_null=True)
    resumo = serializers.CharField()
    conteudo = serializers.DictField()


class ConsultaSaidasSerializer(serializers.Serializer[Any]):
    situacao = serializers.ChoiceField(choices=_SITUACOES_SAIDA, required=False)
    categoria_id = serializers.UUIDField(required=False)
    setor_id = serializers.UUIDField(required=False)
    solicitante_id = serializers.UUIDField(required=False)
    evento_id = serializers.UUIDField(required=False)
    de = serializers.DateField(required=False)
    ate = serializers.DateField(required=False)
    pendentes_envio = serializers.BooleanField(required=False, default=False)
    pendentes_prestacao = serializers.BooleanField(required=False, default=False)
    atrasadas = serializers.BooleanField(required=False, default=False)
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, default=20)


class SaidaItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    solicitacao_id = serializers.UUIDField()
    versao_aprovada = serializers.IntegerField()
    solicitante = PessoaSerializer()
    categoria_id = serializers.UUIDField()
    categoria_nome = serializers.CharField()
    setor_id = serializers.UUIDField()
    setor_nome = serializers.CharField()
    evento_id = serializers.UUIDField(allow_null=True)
    descricao = serializers.CharField()
    valor_aprovado = _dinheiro()
    valor_aprovado_total = _dinheiro()
    total_enviado = _dinheiro()
    total_gasto = _dinheiro(allow_null=True)
    total_devolvido_validado = _dinheiro()
    total_devolvido_pendente = _dinheiro()
    valor_nao_reembolsado = _dinheiro()
    situacao = serializers.CharField()
    em_atraso = serializers.BooleanField()
    tem_complemento_aprovado_para_enviar = serializers.BooleanField()
    tem_complemento_em_andamento = serializers.BooleanField()
    primeiro_envio_em = serializers.DateTimeField(allow_null=True)
    criada_em = serializers.DateTimeField()
    atualizada_em = serializers.DateTimeField()


class PaginaSaidasSerializer(serializers.Serializer[Any]):
    itens = SaidaItemSerializer(many=True)
    tem_mais = serializers.BooleanField()


class CotacaoResumoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    disponivel = serializers.BooleanField()


class EnvioSaidaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    valor = _dinheiro()
    complemento_id = serializers.UUIDField(allow_null=True)
    enviado_por = PessoaSerializer()
    enviado_em = serializers.DateTimeField()
    comprovante_disponivel = serializers.BooleanField()
    comprovante_nome = serializers.CharField(allow_blank=True)


class PrestacaoSaidaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    valor = _dinheiro()
    descricao = serializers.CharField(allow_blank=True)
    registrada_por = PessoaSerializer()
    registrada_em = serializers.DateTimeField()
    situacao = serializers.CharField()
    comprovante_disponivel = serializers.BooleanField()
    comprovante_nome = serializers.CharField(allow_blank=True)
    devolvida_por = PessoaSerializer(allow_null=True)
    motivo_devolucao_texto = serializers.CharField(allow_blank=True)
    texto_devolucao = serializers.CharField(allow_blank=True)
    devolvida_em = serializers.DateTimeField(allow_null=True)


class DevolucaoSaidaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    valor = _dinheiro()
    data = serializers.DateField()  # type: ignore[assignment]
    origem = serializers.CharField()
    evidencia_texto = serializers.CharField(allow_blank=True)
    situacao = serializers.CharField()
    registrada_por = PessoaSerializer()
    registrada_em = serializers.DateTimeField()
    decidido_por = PessoaSerializer(allow_null=True)
    motivo_texto = serializers.CharField(allow_blank=True)
    decisao_texto = serializers.CharField(allow_blank=True)
    decidido_em = serializers.DateTimeField(allow_null=True)
    comprovante_disponivel = serializers.BooleanField()
    comprovante_nome = serializers.CharField(allow_blank=True)


class ComplementoSaidaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    solicitacao_id = serializers.UUIDField()
    valor = _dinheiro()
    situacao = serializers.CharField()
    aprovado_em = serializers.DateTimeField(allow_null=True)
    decidido_em = serializers.DateTimeField(allow_null=True)
    criado_em = serializers.DateTimeField()
    envio_id = serializers.UUIDField(allow_null=True)


class SaidaDetalheSerializer(SaidaItemSerializer):
    itens = ItemGastoSerializer(many=True)
    liquidacao_justificativa = serializers.CharField(allow_blank=True)
    liquidada_por = PessoaSerializer(allow_null=True)
    liquidada_em = serializers.DateTimeField(allow_null=True)
    cancelada_em = serializers.DateTimeField(allow_null=True)
    cotacao = CotacaoResumoSerializer(allow_null=True)
    envios = EnvioSaidaSerializer(many=True)
    prestacoes = PrestacaoSaidaSerializer(many=True)
    devolucoes = DevolucaoSaidaSerializer(many=True)
    complementos = ComplementoSaidaSerializer(many=True)
    estorno = EstornoResumoSerializer(allow_null=True)
    acoes = serializers.ListField(child=serializers.CharField())


class RegistrarEnvioSaidaSerializer(serializers.Serializer[Any]):
    valor = _dinheiro()
    enviado_em = serializers.DateTimeField(required=False, allow_null=True, default=None)
    complemento_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    comprovante = serializers.FileField(required=False, allow_null=True, default=None)


class RegistrarPrestacaoSerializer(serializers.Serializer[Any]):
    valor = _dinheiro()
    descricao = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    comprovante = serializers.FileField(required=False, allow_null=True, default=None)


class DevolverPrestacaoSerializer(serializers.Serializer[Any]):
    motivo_id = serializers.UUIDField()
    texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class RegistrarDevolucaoSaidaSerializer(serializers.Serializer[Any]):
    valor = _dinheiro()
    data = serializers.DateField(required=False, allow_null=True, default=None)  # type: ignore[assignment]
    categoria_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    origem = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    evidencia_texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    comprovante = serializers.FileField(required=False, allow_null=True, default=None)


class PedirComplementoSerializer(serializers.Serializer[Any]):
    itens = ItemGastoSerializer(many=True)
    descricao = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    cotacao_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    aprovador_indicado_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class ComplementoCriadoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    saida_id = serializers.UUIDField()
    solicitacao_id = serializers.UUIDField()
    valor = _dinheiro()
    situacao = serializers.CharField()


class LiquidarSaidaSerializer(serializers.Serializer[Any]):
    justificativa = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class RegistrarEstornoSerializer(serializers.Serializer[Any]):
    motivo_id = serializers.UUIDField()
    justificativa = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class ConsultaEstornosSerializer(serializers.Serializer[Any]):
    alvo_tipo = serializers.ChoiceField(choices=_ALVOS_ESTORNO, required=False)
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, default=20)


class EstornoItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    alvo_tipo = serializers.CharField()
    alvo_id = serializers.UUIDField()
    valor = _dinheiro()
    motivo_id = serializers.UUIDField()
    motivo_texto = serializers.CharField()
    justificativa = serializers.CharField()
    registrado_por = PessoaSerializer()
    registrado_em = serializers.DateTimeField()


class PaginaEstornosSerializer(serializers.Serializer[Any]):
    itens = EstornoItemSerializer(many=True)
    tem_mais = serializers.BooleanField()


class EstornoSaidaRespostaSerializer(EstornoItemSerializer):
    registro = SaidaDetalheSerializer()


class EstornoEntradaRespostaSerializer(EstornoItemSerializer):
    registro = EntradaSerializer()


class EstornoCobrancaRespostaSerializer(EstornoItemSerializer):
    registro = CobrancaDetalheSerializer()


# Lista de lançamentos (RF-104, spec `relatorios/dashboard-e-lancamentos`).


class ConsultaLancamentosSerializer(serializers.Serializer[Any]):
    de = serializers.DateField(required=False)
    ate = serializers.DateField(required=False)
    categoria_id = serializers.UUIDField(required=False)
    tipo = serializers.ChoiceField(choices=[t.value for t in TipoDeLancamento], required=False)
    estado = serializers.ChoiceField(choices=[e.value for e in EstadoDoLancamento], required=False)
    antes = serializers.CharField(required=False, max_length=80)
    limite = serializers.IntegerField(min_value=1, max_value=50, default=20)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        de, ate = attrs.get("de"), attrs.get("ate")
        if de is not None and ate is not None and de > ate:
            raise serializers.ValidationError({"ate": ["O fim do período vem antes do início."]})
        return attrs


class ReferenciaDeLancamentoSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField()
    id = serializers.UUIDField()


class LancamentoSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField()
    subtipo = serializers.CharField(allow_null=True)
    id = serializers.UUIDField()
    data_referencia = serializers.DateField()
    descricao = serializers.CharField()
    categoria = ReferenciaItemSerializer()
    contraparte = serializers.CharField(allow_blank=True)
    valor = _dinheiro()
    valor_realizado = _dinheiro(allow_null=True)
    estado = serializers.CharField()
    situacao = serializers.CharField(allow_blank=True)
    realizado_em = serializers.DateField(allow_null=True)
    original = ReferenciaDeLancamentoSerializer(allow_null=True)


class PaginaDeLancamentosSerializer(serializers.Serializer[Any]):
    itens = LancamentoSerializer(many=True)
    tem_mais = serializers.BooleanField()
