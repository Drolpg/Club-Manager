from typing import Any

from django.utils import timezone
from rest_framework import serializers

from acesso.models import Convite, Usuario


class LoginSerializer(serializers.Serializer[Any]):
    identificador = serializers.CharField(max_length=254)
    senha = serializers.CharField(max_length=128, trim_whitespace=False)


class UsuarioSerializer(serializers.Serializer[Any]):
    """O que a API mostra de um usuário. Os campos são declarados um a um; o modelo nunca sai como está."""

    id = serializers.UUIDField()
    nome = serializers.CharField()
    nome_de_usuario = serializers.CharField()
    email = serializers.EmailField()
    admin = serializers.BooleanField()
    situacao = serializers.CharField()
    tem_cargo = serializers.SerializerMethodField()

    def get_tem_cargo(self, usuario: Usuario) -> bool:
        # Cargo e setores chegam com o módulo `permissoes` (M3). Até lá, ninguém tem cargo.
        return False


class SessaoSerializer(serializers.Serializer[Any]):
    usuario = UsuarioSerializer(allow_null=True)


class TokenSerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=200)


class _QuemGerouSerializer(serializers.Serializer[Usuario]):
    id = serializers.UUIDField()
    nome = serializers.CharField()


class ConviteSerializer(serializers.Serializer[Any]):
    """Um convite, sem o link: o token só existe na resposta de gerar ou regenerar."""

    id = serializers.UUIDField()
    situacao = serializers.SerializerMethodField()
    gerado_por = _QuemGerouSerializer()
    gerado_em = serializers.DateTimeField()
    expira_em = serializers.DateTimeField()
    usado_em = serializers.DateTimeField(allow_null=True)
    revogado_em = serializers.DateTimeField(allow_null=True)

    def get_situacao(self, convite: Convite) -> str:
        return convite.situacao(timezone.now()).value


class ConviteGeradoSerializer(ConviteSerializer):
    link = serializers.CharField(help_text="Mostrado uma única vez. Envie ao convidado por fora.")


class CadastroSerializer(serializers.Serializer[Any]):
    """Dados do cadastro pelo convite. Campos fora desta lista são ignorados; o sistema não pede CPF."""

    token = serializers.CharField(max_length=200)
    nome = serializers.CharField(max_length=120)
    nome_de_usuario = serializers.CharField(max_length=30)
    telefone = serializers.CharField(max_length=30)
    email = serializers.CharField(max_length=254)
    senha = serializers.CharField(max_length=128, trim_whitespace=False)


class SituacaoSerializer(serializers.Serializer[Any]):
    situacao = serializers.CharField()


class IdentificadorSerializer(serializers.Serializer[Any]):
    identificador = serializers.CharField(max_length=254)


class EmailSerializer(serializers.Serializer[Any]):
    email = serializers.CharField(max_length=254)


class RedefinirSenhaSerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=300)
    senha = serializers.CharField(max_length=128, trim_whitespace=False)
