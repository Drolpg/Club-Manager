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
