from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from kernel.errors import handler404, handler500  # noqa: F401
from kernel.health import health

# Toda rota de negócio entra aqui, sob /api/v1/, incluindo as urls do módulo dono.
v1 = [
    path("health/", health, name="health"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

urlpatterns = [path("api/v1/", include(v1))]
