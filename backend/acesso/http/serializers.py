from typing import Any

from django.utils import timezone
from rest_framework import serializers

from acesso import portas
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
        # Quem tem cargo é `permissoes` quem diz, pela porta. A lista passa o conjunto pronto em `com_cargo`,
        # para consultar uma vez só; um usuário sozinho (a sessão) consulta a porta para ele.
        com_cargo = self.context.get("com_cargo")
        if com_cargo is None:
            com_cargo = portas.usuarios_com_cargo([usuario.id])
        return usuario.id in com_cargo


class _AtorSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()


class HistoricoSerializer(serializers.Serializer[Any]):
    """Uma ação do histórico de um item. `ator` é nulo para ações do sistema."""

    acao = serializers.CharField()
    ator = _AtorSerializer(allow_null=True)
    justificativa = serializers.CharField(allow_blank=True)
    criado_em = serializers.DateTimeField()


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


class CredencialGoogleSerializer(serializers.Serializer[Any]):
    credencial = serializers.CharField(max_length=4096)


class CadastroGoogleSerializer(serializers.Serializer[Any]):
    """Cadastro pelo convite com o Google. O e-mail não é pedido: é sempre o que o Google confirmou."""

    token = serializers.CharField(max_length=200)
    credencial = serializers.CharField(max_length=4096)
    nome = serializers.CharField(max_length=120)
    nome_de_usuario = serializers.CharField(max_length=30)
    telefone = serializers.CharField(max_length=30)
    senha = serializers.CharField(max_length=128, trim_whitespace=False)


class ConfiguracaoSerializer(serializers.Serializer[Any]):
    google_client_id = serializers.CharField(allow_null=True)
