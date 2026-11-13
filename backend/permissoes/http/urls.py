from django.urls import URLPattern, path

from permissoes.http import views
from permissoes.models import Cargo, Setor


def _de_itens(rota: str, modelo: type[Cargo] | type[Setor]) -> list[URLPattern]:
    return [
        path(f"{rota}/", views.ItensView.as_view(modelo=modelo), name=f"permissoes-{rota}"),
        *(
            path(
                f"{rota}/<uuid:item_id>/{acao}/",
                views.AcaoDeItemView.as_view(modelo=modelo, acao=acao),
                name=f"permissoes-{rota}-{acao}",
            )
            for acao in ("renomear", "desativar", "reativar")
        ),
    ]


urlpatterns = [
    *_de_itens("cargos", Cargo),
    *_de_itens("setores", Setor),
    path("catalogo/", views.CatalogoView.as_view(), name="permissoes-catalogo"),
    path("concessoes/", views.ConcessoesView.as_view(), name="permissoes-concessoes"),
    path(
        "concessoes/<uuid:concessao_id>/revogar/",
        views.RevogarConcessaoView.as_view(),
        name="permissoes-concessao-revogar",
    ),
    path("usuarios/<uuid:usuario_id>/", views.DetalheDoUsuarioView.as_view(), name="permissoes-usuario"),
    path(
        "usuarios/<uuid:usuario_id>/classificacao/",
        views.ClassificacaoView.as_view(),
        name="permissoes-usuario-classificacao",
    ),
    path("minhas/", views.MinhasView.as_view(), name="permissoes-minhas"),
]
