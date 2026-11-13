import uuid

import pytest
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction

from auditoria import public
from auditoria.models import RegistroDeAuditoria, RegistroImutavel

pytestmark = pytest.mark.django_db


def _registrar(**extra: object) -> tuple[uuid.UUID, uuid.UUID]:
    ator, item = uuid.uuid7(), uuid.uuid7()
    campos: dict[str, object] = {
        "ator_id": ator,
        "acao": "CONVITE_GERADO",
        "item_tipo": "convite",
        "item_id": item,
    }
    campos.update(extra)
    public.registrar(**campos)  # type: ignore[arg-type]
    return ator, item


def test_registrar_grava_quem_o_que_quando_e_sobre_qual_item() -> None:
    ator, item = _registrar(justificativa="link vazou", dados={"motivo": "teste"})

    registro = RegistroDeAuditoria.objects.get()
    assert registro.ator_id == ator
    assert registro.acao == "CONVITE_GERADO"
    assert registro.item_tipo == "convite"
    assert registro.item_id == item
    assert registro.justificativa == "link vazou"
    assert registro.dados == {"motivo": "teste"}
    assert registro.criado_em is not None


def test_registrar_aceita_acao_do_sistema_sem_ator() -> None:
    _registrar(ator_id=None)

    assert RegistroDeAuditoria.objects.get().ator_id is None


def test_historico_do_item_devolve_os_registros_em_ordem_sem_expor_o_modelo() -> None:
    item = uuid.uuid7()
    public.registrar(ator_id=None, acao="PRIMEIRA", item_tipo="usuario", item_id=item)
    public.registrar(ator_id=None, acao="SEGUNDA", item_tipo="usuario", item_id=item)
    public.registrar(ator_id=None, acao="DE_OUTRO_ITEM", item_tipo="usuario", item_id=uuid.uuid7())

    historico = public.historico_do_item("usuario", item)

    assert [r.acao for r in historico] == ["PRIMEIRA", "SEGUNDA"]
    assert not isinstance(historico[0], RegistroDeAuditoria)


def test_registro_nao_pode_ser_alterado_pelo_modelo() -> None:
    _registrar()
    registro = RegistroDeAuditoria.objects.get()
    registro.acao = "ADULTERADO"

    with pytest.raises(RegistroImutavel):
        registro.save()


def test_registro_nao_pode_ser_apagado_pelo_modelo() -> None:
    _registrar()

    with pytest.raises(RegistroImutavel):
        RegistroDeAuditoria.objects.get().delete()


def test_banco_recusa_alterar_registro_mesmo_fora_do_modelo() -> None:
    _registrar()

    with pytest.raises(DatabaseError), transaction.atomic():
        RegistroDeAuditoria.objects.update(acao="ADULTERADO")

    assert RegistroDeAuditoria.objects.get().acao == "CONVITE_GERADO"


def test_banco_recusa_apagar_registro_mesmo_fora_do_modelo() -> None:
    _registrar()

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM auditoria_registrodeauditoria")

    assert RegistroDeAuditoria.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_migracao_reverte_e_reaplica() -> None:
    call_command("migrate", "auditoria", "zero", verbosity=0)
    assert "auditoria_registrodeauditoria" not in connection.introspection.table_names()

    call_command("migrate", "auditoria", verbosity=0)
    assert "auditoria_registrodeauditoria" in connection.introspection.table_names()
