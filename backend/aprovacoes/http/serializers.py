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
