from django.urls import path

from aprovacoes.http import views

urlpatterns = [
    path("tipos/", views.TiposView.as_view(), name="aprovacoes-tipos"),
    path("fila/", views.FilaView.as_view(), name="aprovacoes-fila"),
    path("solicitacoes/", views.SolicitacoesView.as_view(), name="aprovacoes-solicitacoes"),
    path(
        "solicitacoes/<uuid:solicitacao_id>/",
        views.DetalheView.as_view(),
        name="aprovacoes-solicitacao",
    ),
    path(
        "solicitacoes/<uuid:solicitacao_id>/historico/",
        views.HistoricoView.as_view(),
        name="aprovacoes-solicitacao-historico",
    ),
    *(
        path(
            f"solicitacoes/<uuid:solicitacao_id>/{acao}/",
            view.as_view(),
            name=f"aprovacoes-solicitacao-{acao}",
        )
        for acao, view in views.VIEWS_DO_SOLICITANTE.items()
    ),
    path("motivos/", views.MotivosView.as_view(), name="aprovacoes-motivos"),
    *(
        path(
            f"motivos/<uuid:motivo_id>/{acao}/",
            views.AcaoDeMotivoView.as_view(acao=acao),
            name=f"aprovacoes-motivo-{acao}",
        )
        for acao in ("editar", "desativar", "reativar")
    ),
    path("tipos-de-decisao/", views.TiposDeDecisaoView.as_view(), name="aprovacoes-tipos-de-decisao"),
]
