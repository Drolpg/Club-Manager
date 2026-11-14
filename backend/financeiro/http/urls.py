from django.urls import path

from financeiro.http.views import (
    CategoriaDesativarView,
    CategoriaHistoricoView,
    CategoriaReativarView,
    CategoriaRenomearView,
    CategoriasView,
    ChavePixDesativarView,
    ChavePixEditarView,
    ChavePixHistoricoView,
    ChavePixPadraoView,
    ChavePixReativarView,
    ChavesPixView,
    CobrancaCancelarView,
    CobrancaDetalheView,
    CobrancaHistoricoView,
    CobrancaLoteView,
    CobrancasView,
    MinhasCobrancasView,
)

urlpatterns = [
    path("categorias/", CategoriasView.as_view(), name="financeiro-categorias"),
    path(
        "categorias/<uuid:categoria_id>/renomear/",
        CategoriaRenomearView.as_view(),
        name="financeiro-categoria-renomear",
    ),
    path(
        "categorias/<uuid:categoria_id>/desativar/",
        CategoriaDesativarView.as_view(),
        name="financeiro-categoria-desativar",
    ),
    path(
        "categorias/<uuid:categoria_id>/reativar/",
        CategoriaReativarView.as_view(),
        name="financeiro-categoria-reativar",
    ),
    path(
        "categorias/<uuid:categoria_id>/historico/",
        CategoriaHistoricoView.as_view(),
        name="financeiro-categoria-historico",
    ),
    path("chaves-pix/", ChavesPixView.as_view(), name="financeiro-chaves-pix"),
    path(
        "chaves-pix/<uuid:chave_id>/editar/",
        ChavePixEditarView.as_view(),
        name="financeiro-chave-pix-editar",
    ),
    path(
        "chaves-pix/<uuid:chave_id>/marcar-padrao/",
        ChavePixPadraoView.as_view(),
        name="financeiro-chave-pix-padrao",
    ),
    path(
        "chaves-pix/<uuid:chave_id>/desativar/",
        ChavePixDesativarView.as_view(),
        name="financeiro-chave-pix-desativar",
    ),
    path(
        "chaves-pix/<uuid:chave_id>/reativar/",
        ChavePixReativarView.as_view(),
        name="financeiro-chave-pix-reativar",
    ),
    path(
        "chaves-pix/<uuid:chave_id>/historico/",
        ChavePixHistoricoView.as_view(),
        name="financeiro-chave-pix-historico",
    ),
    path("minhas-cobrancas/", MinhasCobrancasView.as_view(), name="financeiro-minhas-cobrancas"),
    path("cobrancas/", CobrancasView.as_view(), name="financeiro-cobrancas"),
    path("cobrancas/lote/", CobrancaLoteView.as_view(), name="financeiro-cobrancas-lote"),
    path("cobrancas/<uuid:cobranca_id>/", CobrancaDetalheView.as_view(), name="financeiro-cobranca-detalhe"),
    path(
        "cobrancas/<uuid:cobranca_id>/historico/",
        CobrancaHistoricoView.as_view(),
        name="financeiro-cobranca-historico",
    ),
    path(
        "cobrancas/<uuid:cobranca_id>/cancelar/",
        CobrancaCancelarView.as_view(),
        name="financeiro-cobranca-cancelar",
    ),
]
