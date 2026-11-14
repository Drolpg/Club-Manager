from django.urls import path

from aprovacoes.http import views

urlpatterns = [
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
