"""Serializers do perfil: só de saída, com os campos declarados (ADR-004). O modelo nunca sai como está."""

from typing import Any

from rest_framework import serializers


class DadosSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    nome_de_usuario = serializers.CharField()
    email = serializers.CharField()
    telefone = serializers.CharField()
    ativo = serializers.BooleanField()
    admin = serializers.BooleanField()
    cadastrado_em = serializers.DateTimeField()
    cargo = serializers.CharField(allow_null=True)
    setores = serializers.ListField(child=serializers.CharField())


class PagamentoSerializer(serializers.Serializer[Any]):
    forma = serializers.CharField()
    data_pagamento = serializers.DateField()
    situacao = serializers.CharField()


class CobrancaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    descricao = serializers.CharField()
    categoria_nome = serializers.CharField()
    valor = serializers.CharField()
    vencimento = serializers.DateField()
    situacao = serializers.CharField()
    pagamentos = PagamentoSerializer(many=True)


class PaginaDeCobrancasSerializer(serializers.Serializer[Any]):
    itens = CobrancaSerializer(many=True)
    tem_mais = serializers.BooleanField()


class EventoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    titulo = serializers.CharField()
    inicio = serializers.DateTimeField()
    local = serializers.CharField()
    categoria_nome = serializers.CharField()
    situacao = serializers.CharField()
    papel = serializers.CharField()
    resposta = serializers.CharField(allow_null=True)


class PaginaDeEventosSerializer(serializers.Serializer[Any]):
    itens = EventoSerializer(many=True)
    tem_mais = serializers.BooleanField()


class NotificacoesSerializer(serializers.Serializer[Any]):
    nao_lidas = serializers.IntegerField()


class PerfilSerializer(serializers.Serializer[Any]):
    """As quatro seções; `notificacoes` só existe quando o alvo é quem consulta (a view a retira)."""

    dados = DadosSerializer()
    cobrancas = PaginaDeCobrancasSerializer()
    eventos = PaginaDeEventosSerializer()
    notificacoes = NotificacoesSerializer(required=False, allow_null=True)
