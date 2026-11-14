from django.urls import path

from aprovacoes.http import views

urlpatterns = [
    path("solicitacoes/", views.SolicitacoesView.as_view(), name="aprovacoes-solicitacoes"),
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
