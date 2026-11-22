from django.urls import path

from relatorios.http import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="relatorios-dashboard"),
    path("perfil/", views.MeuPerfilView.as_view(), name="relatorios-meu-perfil"),
    path("perfil/cobrancas/", views.MinhasCobrancasView.as_view(), name="relatorios-minhas-cobrancas"),
    path("perfil/eventos/", views.MeusEventosView.as_view(), name="relatorios-meus-eventos"),
    path("perfil/<uuid:usuario_id>/", views.PerfilView.as_view(), name="relatorios-perfil"),
    path(
        "perfil/<uuid:usuario_id>/cobrancas/",
        views.CobrancasDoUsuarioView.as_view(),
        name="relatorios-perfil-cobrancas",
    ),
    path(
        "perfil/<uuid:usuario_id>/eventos/",
        views.EventosDoUsuarioView.as_view(),
        name="relatorios-perfil-eventos",
    ),
]
