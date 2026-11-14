"""Entrada e saída das rotas. Os campos de saída são declarados: nenhum modelo sai como está (ADR-004)."""

from typing import Any

from rest_framework import serializers


class MotivoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo_de_decisao = serializers.CharField()
    texto = serializers.CharField()
    ativo = serializers.BooleanField()


class ConsultaDeMotivosSerializer(serializers.Serializer[Any]):
    tipo_de_decisao = serializers.CharField(required=False, max_length=60)
    todos = serializers.BooleanField(required=False, default=False)


class TextoDoMotivoSerializer(serializers.Serializer[Any]):
    texto = serializers.CharField(min_length=2, max_length=200)


class NovoMotivoSerializer(TextoDoMotivoSerializer):
    tipo_de_decisao = serializers.CharField(max_length=60)


class TipoDeDecisaoSerializer(serializers.Serializer[Any]):
    codigo = serializers.CharField()
    nome = serializers.CharField()


class EnvioSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField(max_length=80)
    # O formato é do módulo dono; o serviço confere que é um objeto de até 64 KB.
    conteudo = serializers.JSONField()
    aprovador_indicado_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class SolicitacaoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    situacao = serializers.CharField()
    solicitante_id = serializers.UUIDField()
    aprovador_indicado_id = serializers.UUIDField(allow_null=True)
    numero_da_versao_atual = serializers.IntegerField()
    criada_em = serializers.DateTimeField()
    atualizada_em = serializers.DateTimeField()


class ConteudoSerializer(serializers.Serializer[Any]):
    conteudo = serializers.JSONField()


class ReaberturaSerializer(serializers.Serializer[Any]):
    justificativa = serializers.CharField(max_length=1000)
    conteudo = serializers.JSONField(required=False, default=None)


class EdicaoSerializer(serializers.Serializer[Any]):
    conteudo = serializers.JSONField()
    justificativa = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class CancelamentoSerializer(serializers.Serializer[Any]):
    motivo = serializers.CharField(max_length=1000)


class DecisaoSerializer(serializers.Serializer[Any]):
    motivo_id = serializers.UUIDField()
    texto = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class ContestacaoSerializer(DecisaoSerializer):
    mensagem = serializers.CharField(max_length=1000)
    # Texto, e não número: o valor em dinheiro nunca passa por ponto flutuante. O serviço confere.
    teto_sugerido = serializers.CharField(max_length=20, required=False, allow_null=True, default=None)


# --- consultas ---

_SITUACOES = [
    "EM_ANALISE",
    "RETIRADA",
    "CONTESTADA",
    "RECUSADA",
    "APROVADA",
    "EM_EXECUCAO",
    "ENCERRADA",
    "CANCELADA",
]


def _dinheiro(**extra: Any) -> serializers.DecimalField:
    # Na API, dinheiro é texto com duas casas ("150.00").
    return serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True, **extra)


class PessoaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()


class TipoDeSolicitacaoSerializer(serializers.Serializer[Any]):
    codigo = serializers.CharField()
    nome = serializers.CharField()
    tem_valor = serializers.BooleanField()


class ConsultaDaListaSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField(required=False, max_length=80)
    situacao = serializers.ChoiceField(choices=_SITUACOES, required=False)
    minhas = serializers.BooleanField(required=False, default=False)
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, default=20)


class ItemDaListaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    tipo_nome = serializers.CharField()
    situacao = serializers.CharField()
    solicitante = PessoaSerializer()
    resumo = serializers.CharField()
    valor = _dinheiro(allow_null=True)
    numero_da_versao_atual = serializers.IntegerField()
    aguardando_desde = serializers.DateTimeField()
    criada_em = serializers.DateTimeField()
    atualizada_em = serializers.DateTimeField()


class PaginaSerializer(serializers.Serializer[Any]):
    itens = ItemDaListaSerializer(many=True)
    tem_mais = serializers.BooleanField()


class DecisaoInfoSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField()
    aprovador = PessoaSerializer()
    motivo_id = serializers.UUIDField()
    motivo_texto = serializers.CharField()
    texto = serializers.CharField(allow_blank=True)
    mensagem = serializers.CharField(allow_blank=True)
    teto_sugerido = _dinheiro(allow_null=True)
    aprovacao_propria = serializers.BooleanField()
    criada_em = serializers.DateTimeField()


class VersaoInfoSerializer(serializers.Serializer[Any]):
    numero = serializers.IntegerField()
    # O conteúdo é do módulo dono do tipo; o site o mostra como texto.
    conteudo = serializers.JSONField()
    valor = _dinheiro(allow_null=True)
    resumo = serializers.CharField()
    autor = PessoaSerializer()
    justificativa = serializers.CharField(allow_blank=True)
    criada_em = serializers.DateTimeField()
    decisao = DecisaoInfoSerializer(allow_null=True)


class DetalheSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    tipo_nome = serializers.CharField()
    tem_valor = serializers.BooleanField()
    situacao = serializers.CharField()
    solicitante = PessoaSerializer()
    aprovador_indicado = PessoaSerializer(allow_null=True)
    numero_da_versao_atual = serializers.IntegerField()
    criada_em = serializers.DateTimeField()
    atualizada_em = serializers.DateTimeField()
    versoes = VersaoInfoSerializer(many=True)
    # O que quem pergunta pode fazer agora; o site só mostra estes botões, e a API confere de novo.
    acoes = serializers.ListField(child=serializers.CharField())


class HistoricoSerializer(serializers.Serializer[Any]):
    """Uma ação do histórico. `ator` é nulo para ações do sistema."""

    acao = serializers.CharField()
    ator = PessoaSerializer(allow_null=True)
    justificativa = serializers.CharField(allow_blank=True)
    criado_em = serializers.DateTimeField()
