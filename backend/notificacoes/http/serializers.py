from typing import Any

from rest_framework import serializers

from notificacoes.services.consulta import LIMITE_MAXIMO, LIMITE_PADRAO


class _Booleano(serializers.Field[bool, bool, bool, Any]):
    """Só aceita `true` ou `false`. O `BooleanField` do DRF aceitaria "sim", "1" e outros."""

    default_error_messages = {"invalid": "Informe verdadeiro ou falso."}  # noqa: RUF012

    def to_internal_value(self, data: Any) -> bool:
        if not isinstance(data, bool):
            self.fail("invalid")
        return data

    def to_representation(self, value: bool) -> bool:
        return bool(value)


class ConsultaDaCaixaSerializer(serializers.Serializer[Any]):
    limite = serializers.IntegerField(min_value=1, max_value=LIMITE_MAXIMO, default=LIMITE_PADRAO)
    antes = serializers.UUIDField(required=False)


class ItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    pede_acao = serializers.BooleanField()
    titulo = serializers.CharField()
    texto = serializers.CharField()
    caminho = serializers.CharField()
    criada_em = serializers.DateTimeField()
    lida_em = serializers.DateTimeField(allow_null=True)


class PaginaSerializer(serializers.Serializer[Any]):
    itens = ItemSerializer(many=True)
    tem_mais = serializers.BooleanField()


class ResumoSerializer(serializers.Serializer[Any]):
    nao_lidas = serializers.IntegerField()
    mais_recente_id = serializers.UUIDField(allow_null=True)


class MarcadasSerializer(serializers.Serializer[Any]):
    marcadas = serializers.IntegerField()


class PreferenciasSerializer(serializers.Serializer[Any]):
    aviso_na_tela = serializers.BooleanField()
    email_informativos = serializers.BooleanField()


class PreferenciasEntradaSerializer(serializers.Serializer[Any]):
    aviso_na_tela = _Booleano(required=False)
    email_informativos = _Booleano(required=False)
