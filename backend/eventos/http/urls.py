from django.urls import path

from eventos.http.views import (
    CalendarioView,
    CancelarView,
    CategoriasView,
    DesativarCategoriaView,
    DetalheView,
    EditarCategoriaView,
    EditarView,
    EventosView,
    HistoricoView,
    OrcamentoView,
    PresencaView,
    ReabrirView,
    RealizarView,
    ReativarCategoriaView,
    ReferenciasView,
)

urlpatterns = [
    path("", EventosView.as_view(), name="eventos"),
    path("referencias/", ReferenciasView.as_view(), name="eventos-referencias"),
    path("calendario/", CalendarioView.as_view(), name="eventos-calendario"),
    path("categorias/", CategoriasView.as_view(), name="eventos-categorias"),
    path(
        "categorias/<uuid:categoria_id>/editar/",
        EditarCategoriaView.as_view(),
        name="eventos-categoria-editar",
    ),
    path(
        "categorias/<uuid:categoria_id>/desativar/",
        DesativarCategoriaView.as_view(),
        name="eventos-categoria-desativar",
    ),
    path(
        "categorias/<uuid:categoria_id>/reativar/",
        ReativarCategoriaView.as_view(),
        name="eventos-categoria-reativar",
    ),
    path("<uuid:evento_id>/", DetalheView.as_view(), name="eventos-detalhe"),
    path("<uuid:evento_id>/historico/", HistoricoView.as_view(), name="eventos-historico"),
    path("<uuid:evento_id>/editar/", EditarView.as_view(), name="eventos-editar"),
    path("<uuid:evento_id>/reabrir/", ReabrirView.as_view(), name="eventos-reabrir"),
    path("<uuid:evento_id>/orcamento/", OrcamentoView.as_view(), name="eventos-orcamento"),
    path("<uuid:evento_id>/presenca/", PresencaView.as_view(), name="eventos-presenca"),
    path("<uuid:evento_id>/realizar/", RealizarView.as_view(), name="eventos-realizar"),
    path("<uuid:evento_id>/cancelar/", CancelarView.as_view(), name="eventos-cancelar"),
]
