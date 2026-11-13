from typing import Any

from rest_framework import serializers


class NomeSerializer(serializers.Serializer[Any]):
    nome = serializers.CharField(min_length=2, max_length=60)


class CargoOuSetorSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    ativo = serializers.BooleanField()
