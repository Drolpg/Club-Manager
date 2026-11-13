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


urlpatterns = [*_de_itens("cargos", Cargo), *_de_itens("setores", Setor)]
