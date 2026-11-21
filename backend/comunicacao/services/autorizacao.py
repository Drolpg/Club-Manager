"""Os fatos de quem age, das APIs públicas de `permissoes`, para `domain/autorizacao.avaliar`.

As rotas conferem primeiro; os serviços conferem de novo, porque também são chamados em processo.
"""

import uuid
from dataclasses import dataclass

from comunicacao.domain.autorizacao import (
    PERM_ENVIAR_DOCUMENTOS,
    PERM_GERENCIAR,
    PERM_PUBLICAR,
    PERM_REGISTRAR_ATAS,
    Avaliacao,
    Fatos,
)
from comunicacao.domain.valores import (
    SituacaoDoComentario,
    SituacaoDoComunicado,
    SituacaoDoDocumento,
    TipoDeDocumento,
)
from comunicacao.erros import erro
from comunicacao.models import Comentario, Comunicado, Documento
from permissoes import public as permissoes


@dataclass(frozen=True)
class Quem:
    """Quem age, com as permissões lidas uma vez; monta os `Fatos` de cada item."""

    ator_id: uuid.UUID
    le_gestao: bool
    pode_publicar: bool
    pode_gerenciar: bool
    pode_enviar_documentos: bool
    pode_registrar_atas: bool

    def fatos(
        self,
        *,
        comunicado: Comunicado | None = None,
        tem_reacao_ativa: bool = False,
        comentario: Comentario | None = None,
        documento: Documento | None = None,
    ) -> Fatos:
        campos: dict[str, object] = {}
        if comunicado is not None:
            campos |= {
                "autor_do_comunicado_id": comunicado.autor_id,
                "situacao_do_comunicado": SituacaoDoComunicado(comunicado.situacao),
                "fixado": comunicado.fixado_em is not None,
                "tem_reacao_ativa": tem_reacao_ativa,
            }
        if comentario is not None:
            campos |= {
                "autor_do_comentario_id": comentario.autor_id,
                "situacao_do_comentario": SituacaoDoComentario(comentario.situacao),
                "oculto_pela_gerencia": comentario.oculto_pela_gerencia,
            }
        if documento is not None:
            campos |= {
                "enviado_por_id": documento.enviado_por_id,
                "tipo_do_documento": TipoDeDocumento(documento.tipo),
                "situacao_do_documento": SituacaoDoDocumento(documento.situacao),
            }
        return Fatos(
            ator_id=self.ator_id,
            le_gestao=self.le_gestao,
            pode_publicar=self.pode_publicar,
            pode_gerenciar=self.pode_gerenciar,
            pode_enviar_documentos=self.pode_enviar_documentos,
            pode_registrar_atas=self.pode_registrar_atas,
            **campos,  # type: ignore[arg-type]
        )


def quem(ator_id: uuid.UUID) -> Quem:
    """Uma leitura das permissões do ator."""
    do_ator = permissoes.permissoes_de(ator_id)
    return Quem(
        ator_id=ator_id,
        le_gestao=permissoes.le_gestao(ator_id),
        pode_publicar=PERM_PUBLICAR in do_ator,
        pode_gerenciar=PERM_GERENCIAR in do_ator,
        pode_enviar_documentos=PERM_ENVIAR_DOCUMENTOS in do_ator,
        pode_registrar_atas=PERM_REGISTRAR_ATAS in do_ator,
    )


def exigir(avaliacao: Avaliacao) -> None:
    if not avaliacao.pode:
        raise erro(avaliacao.erro or "PERMISSION_DENIED")


def exigir_leitura_de_gestao(ator_id: uuid.UUID) -> None:
    """Leitura de gestão (403) antes da existência (404): quem não lê não descobre quais IDs existem."""
    if not permissoes.le_gestao(ator_id):
        raise erro("PERMISSION_DENIED")
