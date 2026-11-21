"""Serializers de `comunicacao`.

Os de entrada só validam o formato: o domínio confere tamanho e obrigatoriedade, para devolver a mensagem de
cada campo. Os de saída declaram os campos (ADR-004). O texto livre sai como foi guardado; quem o mostra o
trata como texto (R9).
"""

from typing import Any

from rest_framework import serializers

_TEXTO_LONGO = 50_000  # só barra abuso; o limite de cada campo é do domínio

# --- entrada ---


class ComunicadoEntradaSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField(allow_blank=True, max_length=32)
    titulo = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=_TEXTO_LONGO)
    texto = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=_TEXTO_LONGO)
    documentos_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class EdicaoDoComunicadoSerializer(serializers.Serializer[Any]):
    titulo = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=_TEXTO_LONGO)
    texto = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=_TEXTO_LONGO)
    documentos_ids = serializers.ListField(child=serializers.UUIDField())


class MotivoSerializer(serializers.Serializer[Any]):
    motivo = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=_TEXTO_LONGO)


class MotivoOpcionalSerializer(serializers.Serializer[Any]):
    motivo = serializers.CharField(
        allow_blank=True, required=False, default="", trim_whitespace=False, max_length=_TEXTO_LONGO
    )


class ReacaoEntradaSerializer(serializers.Serializer[Any]):
    tipo = serializers.CharField(allow_blank=True, max_length=32)


class TextoSerializer(serializers.Serializer[Any]):
    texto = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=_TEXTO_LONGO)


class DocumentoEntradaSerializer(serializers.Serializer[Any]):
    titulo = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=_TEXTO_LONGO)
    descricao = serializers.CharField(
        allow_blank=True, required=False, default="", trim_whitespace=False, max_length=_TEXTO_LONGO
    )
    categoria_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    arquivo = serializers.FileField(required=False, allow_null=True, default=None)


class AtaEntradaSerializer(serializers.Serializer[Any]):
    titulo = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=_TEXTO_LONGO)
    descricao = serializers.CharField(
        allow_blank=True, required=False, default="", trim_whitespace=False, max_length=_TEXTO_LONGO
    )
    data_da_reuniao = serializers.DateField(required=False, allow_null=True, default=None)
    arquivo = serializers.FileField(required=False, allow_null=True, default=None)


class NovaVersaoEntradaSerializer(serializers.Serializer[Any]):
    motivo = serializers.CharField(
        allow_blank=True, required=False, default="", trim_whitespace=False, max_length=_TEXTO_LONGO
    )
    arquivo = serializers.FileField(required=False, allow_null=True, default=None)


class NomeDaCategoriaSerializer(serializers.Serializer[Any]):
    nome = serializers.CharField(allow_blank=True, max_length=200)


class ConsultaDoFeedSerializer(serializers.Serializer[Any]):
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, required=False)


class ConsultaDeComentariosSerializer(serializers.Serializer[Any]):
    depois = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, required=False)


class ConsultaDeDocumentosSerializer(serializers.Serializer[Any]):
    categoria_id = serializers.UUIDField(required=False)
    tipo = serializers.CharField(required=False, max_length=32)
    titulo = serializers.CharField(required=False, max_length=120)
    arquivados = serializers.BooleanField(required=False, default=False)
    antes = serializers.UUIDField(required=False)
    limite = serializers.IntegerField(min_value=1, max_value=50, required=False)


class ConsultaDeCategoriasSerializer(serializers.Serializer[Any]):
    todas = serializers.BooleanField(required=False, default=False)


# --- saída ---


class PessoaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField(allow_blank=True)


class ItemDeReferenciaSerializer(serializers.Serializer[Any]):
    codigo = serializers.CharField()
    rotulo = serializers.CharField()


class CategoriaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    ativa = serializers.BooleanField()


class CategoriaDaReferenciaSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    nome = serializers.CharField()


class ReferenciasSerializer(serializers.Serializer[Any]):
    categorias = CategoriaDaReferenciaSerializer(many=True)
    tipos = ItemDeReferenciaSerializer(many=True)
    reacoes = ItemDeReferenciaSerializer(many=True)


class DocumentoDoComunicadoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    titulo = serializers.CharField()
    tipo = serializers.CharField()
    situacao = serializers.CharField()


class ReacoesSerializer(serializers.Serializer[Any]):
    contagem = serializers.DictField(child=serializers.IntegerField())
    minha = serializers.CharField(allow_null=True)
    quem = serializers.DictField(child=serializers.ListField(child=PessoaSerializer()), required=False)


class DespublicacaoSerializer(serializers.Serializer[Any]):
    em = serializers.DateTimeField(allow_null=True)
    por = PessoaSerializer(allow_null=True)
    motivo = serializers.CharField(allow_blank=True)


class ComunicadoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    titulo = serializers.CharField()
    texto = serializers.CharField()
    autor = PessoaSerializer()
    situacao = serializers.CharField()
    fixado = serializers.BooleanField()
    fixado_em = serializers.DateTimeField(allow_null=True)
    publicado_em = serializers.DateTimeField()
    editado = serializers.BooleanField()
    editado_em = serializers.DateTimeField(allow_null=True)
    despublicado = DespublicacaoSerializer(allow_null=True)
    documentos = DocumentoDoComunicadoSerializer(many=True)
    reacoes = ReacoesSerializer()
    total_de_comentarios = serializers.IntegerField()
    acoes = serializers.ListField(child=serializers.CharField())


class PaginaDoFeedSerializer(serializers.Serializer[Any]):
    fixados = ComunicadoSerializer(many=True)
    itens = ComunicadoSerializer(many=True)
    tem_mais = serializers.BooleanField()


class PaginaDeComunicadosSerializer(serializers.Serializer[Any]):
    itens = ComunicadoSerializer(many=True)
    tem_mais = serializers.BooleanField()


class OcultacaoSerializer(serializers.Serializer[Any]):
    em = serializers.DateTimeField(allow_null=True)
    por = PessoaSerializer(allow_null=True)
    pela_gerencia = serializers.BooleanField()
    motivo = serializers.CharField(allow_blank=True)


class ComentarioSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    autor = PessoaSerializer()
    texto = serializers.CharField()
    situacao = serializers.CharField()
    criado_em = serializers.DateTimeField()
    editado = serializers.BooleanField()
    editado_em = serializers.DateTimeField(allow_null=True)
    oculto = OcultacaoSerializer(allow_null=True)
    acoes = serializers.ListField(child=serializers.CharField())


class PaginaDeComentariosSerializer(serializers.Serializer[Any]):
    itens = ComentarioSerializer(many=True)
    tem_mais = serializers.BooleanField()


class ArquivoSerializer(serializers.Serializer[Any]):
    nome = serializers.CharField()
    mime = serializers.CharField()
    tamanho = serializers.IntegerField()


class DocumentoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    tipo = serializers.CharField()
    titulo = serializers.CharField()
    descricao = serializers.CharField(allow_blank=True)
    categoria = CategoriaDaReferenciaSerializer(allow_null=True)
    data_da_reuniao = serializers.DateField(allow_null=True)
    enviado_por = PessoaSerializer()
    situacao = serializers.CharField()
    versao_atual = serializers.IntegerField()
    arquivo = ArquivoSerializer()
    criado_em = serializers.DateTimeField()
    acoes = serializers.ListField(child=serializers.CharField())


class PaginaDeDocumentosSerializer(serializers.Serializer[Any]):
    itens = DocumentoSerializer(many=True)
    tem_mais = serializers.BooleanField()


class VersaoSerializer(ArquivoSerializer):
    numero = serializers.IntegerField()
    motivo = serializers.CharField(allow_blank=True)
    enviada_por = PessoaSerializer()
    enviada_em = serializers.DateTimeField()
    situacao = serializers.CharField()


class ComunicadoLigadoSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    titulo = serializers.CharField()


class DetalheDoDocumentoSerializer(DocumentoSerializer):
    versoes = VersaoSerializer(many=True)
    comunicados = ComunicadoLigadoSerializer(many=True)
