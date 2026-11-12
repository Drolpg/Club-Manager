from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from kernel.errors import handler404, handler500  # noqa: F401
from kernel.health import health

# Toda rota de negócio entra aqui, sob /api/v1/, incluindo as urls do módulo dono.
v1: list[URLPattern | URLResolver] = [
    path("health/", health, name="health"),
    path("acesso/", include("acesso.http.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

urlpatterns = [path("api/v1/", include(v1))]
