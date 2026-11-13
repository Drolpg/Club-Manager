from typing import Any

from rest_framework import serializers

from permissoes.models import AlvoDaConcessao


class NomeSerializer(serializers.Serializer[Any]):
    nome = serializers.CharField(min_length=2, max_length=60)


class CargoOuSetorSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    ativo = serializers.BooleanField()


class CatalogoSerializer(serializers.Serializer[Any]):
    codigo = serializers.CharField()
    nome = serializers.CharField()
    descricao = serializers.CharField()


class ConcessaoEntradaSerializer(serializers.Serializer[Any]):
    permissao = serializers.CharField(max_length=80)
    alvo_tipo = serializers.ChoiceField(choices=AlvoDaConcessao.values)
    alvo_id = serializers.UUIDField()


class _AlvoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="alvo_id")
    nome = serializers.CharField(source="alvo_nome")


class ConcessaoSerializer(serializers.Serializer[Any]):
    """Uma concessão com o alvo. Entra uma `ConcessaoInfo`, e não o modelo."""

    id = serializers.UUIDField()
    permissao = serializers.CharField()
    alvo_tipo = serializers.CharField()
    alvo = _AlvoSerializer(source="*")
    concedida_em = serializers.DateTimeField()
    revogada_em = serializers.DateTimeField(allow_null=True)


class ClassificacaoEntradaSerializer(serializers.Serializer[Any]):
    cargo_id = serializers.UUIDField(allow_null=True)
    setor_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class _OrigemSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField()
    id = serializers.UUIDField(allow_null=True)
    nome = serializers.CharField(allow_null=True)


class _PermissaoDoUsuarioSerializer(serializers.Serializer[Any]):
    codigo = serializers.CharField()
    nome = serializers.CharField()
    origens = _OrigemSerializer(many=True)


class DetalheDoUsuarioSerializer(serializers.Serializer[Any]):
    """Classificação e permissões com origens. Entra um `DetalheDoUsuario`."""

    cargo = CargoOuSetorSerializer(allow_null=True)
    setores = CargoOuSetorSerializer(many=True)
    permissoes = _PermissaoDoUsuarioSerializer(many=True)
