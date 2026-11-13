from django.urls import path

from notificacoes.http import views

urlpatterns = [
    path("", views.CaixaView.as_view(), name="notificacoes-caixa"),
    path("resumo/", views.ResumoView.as_view(), name="notificacoes-resumo"),
    path("ler-todas/", views.LerTodasView.as_view(), name="notificacoes-ler-todas"),
    path("<uuid:notificacao_id>/ler/", views.LerView.as_view(), name="notificacoes-ler"),
    path("preferencias/", views.PreferenciasView.as_view(), name="notificacoes-preferencias"),
]
