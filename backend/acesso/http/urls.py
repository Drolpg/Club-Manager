from django.urls import path

from acesso.http import views

urlpatterns = [
    path("sessao/", views.SessaoView.as_view(), name="acesso-sessao"),
    path("convites/", views.ConvitesView.as_view(), name="acesso-convites"),
    path("convites/consultar/", views.ConsultarConviteView.as_view(), name="acesso-convite-consultar"),
    path(
        "convites/<uuid:convite_id>/regenerar/",
        views.RegenerarConviteView.as_view(),
        name="acesso-convite-regenerar",
    ),
    path(
        "convites/<uuid:convite_id>/revogar/",
        views.RevogarConviteView.as_view(),
        name="acesso-convite-revogar",
    ),
    path("cadastros/", views.CadastrosView.as_view(), name="acesso-cadastros"),
    path("verificacoes/", views.VerificacoesView.as_view(), name="acesso-verificacoes"),
    path(
        "verificacoes/reenviar/",
        views.ReenviarVerificacaoView.as_view(),
        name="acesso-verificacao-reenviar",
    ),
]
