import logging

from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)

_HealthSerializer = inline_serializer(
    name="Health",
    fields={"status": serializers.CharField(), "database": serializers.CharField()},
)


@extend_schema(
    summary="Situação do serviço",
    description="Usado pelo balanceador e pelo compose para saber se a API e o banco respondem.",
    responses={200: _HealthSerializer, 503: _HealthSerializer},
    auth=[],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        # O motivo fica só no log: a resposta não expõe detalhe do banco.
        logger.exception("Health: banco indisponível")
        return Response({"status": "unavailable", "database": "unavailable"}, status=503)
    return Response({"status": "ok", "database": "ok"})
