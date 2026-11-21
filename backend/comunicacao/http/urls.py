from django.urls import path

from comunicacao.http import views

urlpatterns = [
    path("referencias/", views.ReferenciasView.as_view(), name="comunicacao-referencias"),
    # comunicados
    path("comunicados/", views.ComunicadosView.as_view(), name="comunicacao-comunicados"),
    path("comunicados/despublicados/", views.DespublicadosView.as_view(), name="comunicacao-despublicados"),
    path(
        "comunicados/<uuid:comunicado_id>/",
        views.ComunicadoDetalheView.as_view(),
        name="comunicacao-comunicado",
    ),
    path(
        "comunicados/<uuid:comunicado_id>/editar/",
        views.EditarComunicadoView.as_view(),
        name="comunicacao-comunicado-editar",
    ),
    path(
        "comunicados/<uuid:comunicado_id>/despublicar/",
        views.DespublicarView.as_view(),
        name="comunicacao-comunicado-despublicar",
    ),
    path(
        "comunicados/<uuid:comunicado_id>/republicar/",
        views.RepublicarView.as_view(),
        name="comunicacao-comunicado-republicar",
    ),
    path(
        "comunicados/<uuid:comunicado_id>/fixar/",
        views.FixarView.as_view(),
        name="comunicacao-comunicado-fixar",
    ),
    path(
        "comunicados/<uuid:comunicado_id>/desafixar/",
        views.DesafixarView.as_view(),
        name="comunicacao-comunicado-desafixar",
    ),
    # reações e comentários
    path("comunicados/<uuid:comunicado_id>/reacao/", views.ReacaoView.as_view(), name="comunicacao-reacao"),
    path(
        "comunicados/<uuid:comunicado_id>/reacao/retirar/",
        views.RetirarReacaoView.as_view(),
        name="comunicacao-reacao-retirar",
    ),
    path(
        "comunicados/<uuid:comunicado_id>/comentarios/",
        views.ComentariosView.as_view(),
        name="comunicacao-comentarios",
    ),
    path(
        "comentarios/<uuid:comentario_id>/editar/",
        views.EditarComentarioView.as_view(),
        name="comunicacao-comentario-editar",
    ),
    path(
        "comentarios/<uuid:comentario_id>/ocultar/",
        views.OcultarComentarioView.as_view(),
        name="comunicacao-comentario-ocultar",
    ),
    path(
        "comentarios/<uuid:comentario_id>/reexibir/",
        views.ReexibirComentarioView.as_view(),
        name="comunicacao-comentario-reexibir",
    ),
    # documentos e atas
    path("documentos/", views.DocumentosView.as_view(), name="comunicacao-documentos"),
    path("documentos/atas/", views.AtasView.as_view(), name="comunicacao-atas"),
    path(
        "documentos/<uuid:documento_id>/", views.DocumentoDetalheView.as_view(), name="comunicacao-documento"
    ),
    path(
        "documentos/<uuid:documento_id>/arquivo/",
        views.ArquivoVigenteView.as_view(),
        name="comunicacao-documento-arquivo",
    ),
    path(
        "documentos/<uuid:documento_id>/versoes/",
        views.NovaVersaoView.as_view(),
        name="comunicacao-documento-versoes",
    ),
    path(
        "documentos/<uuid:documento_id>/versoes/<int:numero>/arquivo/",
        views.ArquivoDaVersaoView.as_view(),
        name="comunicacao-documento-versao-arquivo",
    ),
    path(
        "documentos/<uuid:documento_id>/arquivar/",
        views.ArquivarView.as_view(),
        name="comunicacao-documento-arquivar",
    ),
    path(
        "documentos/<uuid:documento_id>/desarquivar/",
        views.DesarquivarView.as_view(),
        name="comunicacao-documento-desarquivar",
    ),
    # categorias de documento
    path("categorias/", views.CategoriasView.as_view(), name="comunicacao-categorias"),
    path(
        "categorias/<uuid:categoria_id>/editar/",
        views.EditarCategoriaView.as_view(),
        name="comunicacao-categoria-editar",
    ),
    path(
        "categorias/<uuid:categoria_id>/desativar/",
        views.DesativarCategoriaView.as_view(),
        name="comunicacao-categoria-desativar",
    ),
    path(
        "categorias/<uuid:categoria_id>/reativar/",
        views.ReativarCategoriaView.as_view(),
        name="comunicacao-categoria-reativar",
    ),
]
