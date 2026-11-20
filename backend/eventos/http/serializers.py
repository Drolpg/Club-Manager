"""Serializers de `eventos`: os de entrada só validam o formato; os de saída declaram os campos (ADR-004)."""

import re
from typing import Any

from rest_framework import serializers

from eventos.domain.situacao import SituacaoDoEvento
from eventos.models import RespostaDePresenca

_SITUACOES = [s.value for s in SituacaoDoEvento]
_MES = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")

# --- entrada ---


class DadosDoEventoSerializer(serializers.Serializer[Any]):
    """O domínio confere tamanho e obrigatoriedade dos textos, para devolver a mensagem de cada campo."""

    titulo = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=2000)
    descricao = serializers.CharField(allow_blank=True, required=False, default="", max_length=4000)
    inicio = serializers.DateTimeField()
    local = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=2000)
    categoria_id = serializers.UUIDField()
    envolve_custo = serializers.BooleanField()


class PropostaSerializer(DadosDoEventoSerializer):
    aprovador_indicado_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class EdicaoSerializer(DadosDoEventoSerializer):
    justificativa = serializers.CharField(allow_blank=True, required=False, default="", max_length=1000)


class JustificativaSerializer(serializers.Serializer[Any]):
    justificativa = serializers.CharField(allow_blank=True, max_length=1000)


class ItemDoOrcamentoSerializer(serializers.Serializer[Any]):
    descricao = serializers.CharField(allow_blank=True, max_length=160)
    valor = serializers.CharField(max_length=20)


class OrcamentoEntradaSerializer(serializers.Serializer[Any]):
    descricao = serializers.CharField(allow_blank=True, max_length=200)
    categoria_id = serializers.UUIDField()
    setor_id = serializers.UUIDField()
    itens = ItemDoOrcamentoSerializer(many=True)
    cotacao_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    aprovador_indicado_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class PresencaEntradaSerializer(serializers.Serializer[Any]):
    resposta = serializers.ChoiceField(choices=RespostaDePresenca.values)


class RealizarSerializer(serializers.Serializer[Any]):
    # O contrato chama o campo de `data`; o DRF tira os campos declarados da classe, então não há conflito.
    data = serializers.DateField(required=False, allow_null=True, default=None)  # type: ignore[assignment]
    motivo = serializers.CharField(allow_blank=True, required=False, default="", max_length=1000)


class CancelarSerializer(serializers.Serializer[Any]):
    motivo = serializers.CharField(allow_blank=True, max_length=1000)


class ConsultaCalendarioSerializer(serializers.Serializer[Any]):
    mes = serializers.CharField(help_text="AAAA-MM")

    def validate_mes(self, valor: str) -> tuple[int, int]:
        casou = _MES.fullmatch(valor)
        if casou is None:
            raise serializers.ValidationError("Informe o mês no formato AAAA-MM.")
        return int(casou.group(1)), int(casou.group(2))


class ConsultaHistoricoSerializer(serializers.Serializer[Any]):
    situacao = serializers.ChoiceField(choices=_SITUACOES, required=False)
    categoria_id = serializers.UUIDField(required=False)
    de = serializers.DateField(required=False)
    ate = serializers.DateField(required=False)
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, default=20)


class ConsultaCategoriasSerializer(serializers.Serializer[Any]):
    todas = serializers.BooleanField(required=False, default=False)


class NomeCategoriaSerializer(serializers.Serializer[Any]):
    nome = serializers.CharField(allow_blank=True, max_length=200)


# --- saída ---


class PessoaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()


class ItemSimplesSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()


class ReferenciasSerializer(serializers.Serializer[Any]):
    categorias = ItemSimplesSerializer(many=True)
    aprovadores_eventos = PessoaSerializer(many=True)
    precisa_indicar_aprovador = serializers.BooleanField()


class CalendarioItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    titulo = serializers.CharField()
    inicio = serializers.DateTimeField()
    local = serializers.CharField()
    categoria_nome = serializers.CharField()
    situacao = serializers.CharField()


class EventoItemSerializer(CalendarioItemSerializer):
    categoria_id = serializers.UUIDField()
    envolve_custo = serializers.BooleanField()
    proponente_id = serializers.UUIDField()


class PaginaEventosSerializer(serializers.Serializer[Any]):
    itens = EventoItemSerializer(many=True)
    tem_mais = serializers.BooleanField()


class SolicitacaoLigadaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    situacao = serializers.CharField()


class OrcamentoSerializer(serializers.Serializer[Any]):
    solicitacao_id = serializers.UUIDField()
    situacao = serializers.CharField()


class PresencasSerializer(serializers.Serializer[Any]):
    vou = PessoaSerializer(many=True)
    nao_vou = PessoaSerializer(many=True)
    sem_resposta = PessoaSerializer(many=True)
    minha = serializers.CharField(allow_null=True)


class RealizacaoSerializer(serializers.Serializer[Any]):
    data = serializers.DateField()  # type: ignore[assignment]  # mesmo caso do RealizarSerializer
    motivo = serializers.CharField(allow_blank=True)
    por = PessoaSerializer(allow_null=True)
    em = serializers.DateTimeField()


class CancelamentoSerializer(serializers.Serializer[Any]):
    motivo = serializers.CharField()
    por = PessoaSerializer(allow_null=True)
    pelo_sistema = serializers.BooleanField()
    em = serializers.DateTimeField()


class DetalheSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="evento.id")
    titulo = serializers.CharField(source="evento.titulo")
    descricao = serializers.CharField(source="evento.descricao", allow_blank=True)
    inicio = serializers.DateTimeField(source="evento.inicio")
    local = serializers.CharField(source="evento.local")
    categoria_id = serializers.UUIDField(source="evento.categoria_id")
    categoria_nome = serializers.CharField(source="evento.categoria_nome")
    envolve_custo = serializers.BooleanField(source="evento.envolve_custo")
    situacao = serializers.CharField(source="evento.situacao")
    criado_em = serializers.DateTimeField(source="evento.criado_em")
    proponente = PessoaSerializer()
    solicitacao_do_evento = SolicitacaoLigadaSerializer()
    orcamento = OrcamentoSerializer(allow_null=True)
    presencas = PresencasSerializer()
    realizacao = RealizacaoSerializer(allow_null=True)
    cancelamento = CancelamentoSerializer(allow_null=True)
    acoes = serializers.ListField(child=serializers.CharField())


class HistoricoSerializer(serializers.Serializer[Any]):
    """Uma ação do histórico. `ator` é nulo para ações do sistema."""

    acao = serializers.CharField()
    ator = PessoaSerializer(allow_null=True)
    justificativa = serializers.CharField(allow_blank=True)
    criado_em = serializers.DateTimeField()


class CategoriaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    ativa = serializers.BooleanField()
