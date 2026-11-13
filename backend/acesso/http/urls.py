from django.urls import path

from acesso.http import views

urlpatterns = [
    path("configuracao/", views.ConfiguracaoView.as_view(), name="acesso-configuracao"),
    path("sessao/", views.SessaoView.as_view(), name="acesso-sessao"),
    path("sessao/google/", views.SessaoGoogleView.as_view(), name="acesso-sessao-google"),
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
    path(
        "convites/<uuid:convite_id>/historico/",
        views.HistoricoDoConviteView.as_view(),
        name="acesso-convite-historico",
    ),
    path("cadastros/", views.CadastrosView.as_view(), name="acesso-cadastros"),
    path("cadastros/google/", views.CadastroGoogleView.as_view(), name="acesso-cadastro-google"),
    path("verificacoes/", views.VerificacoesView.as_view(), name="acesso-verificacoes"),
    path(
        "verificacoes/reenviar/",
        views.ReenviarVerificacaoView.as_view(),
        name="acesso-verificacao-reenviar",
    ),
    path("senhas/recuperar/", views.RecuperarSenhaView.as_view(), name="acesso-senha-recuperar"),
    path("senhas/redefinir/", views.RedefinirSenhaView.as_view(), name="acesso-senha-redefinir"),
    path("usuarios/", views.UsuariosView.as_view(), name="acesso-usuarios"),
    path(
        "usuarios/<uuid:usuario_id>/historico/",
        views.HistoricoDoUsuarioView.as_view(),
        name="acesso-usuario-historico",
    ),
    *(
        path(
            f"usuarios/<uuid:usuario_id>/{acao}/",
            views.AcaoDeUsuarioView.as_view(acao=acao),
            name=f"acesso-usuario-{acao}",
        )
        for acao in ("desativar", "reativar", "tornar-admin", "remover-admin")
    ),
]
