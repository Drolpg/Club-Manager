"""Imutabilidade também no banco, no padrão do motor (INV-EVT-04; "nada é apagado").

O evento recusa exclusão e qualquer alteração depois de realizado ou cancelado. Presença e categoria recusam
exclusão.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("eventos", "0002_categorias_e_concessoes_iniciais"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE FUNCTION eventos_evento_imutavel() RETURNS trigger AS $$
                BEGIN
                    IF TG_OP = 'DELETE' THEN
                        RAISE EXCEPTION 'evento nao pode ser apagado';
                    END IF;
                    IF OLD.situacao IN ('REALIZADO', 'CANCELADO') THEN
                        RAISE EXCEPTION 'evento realizado ou cancelado nao pode ser alterado';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER eventos_evento_imutavel
                    BEFORE UPDATE OR DELETE ON eventos_evento
                    FOR EACH ROW EXECUTE FUNCTION eventos_evento_imutavel();

                CREATE FUNCTION eventos_sem_exclusao() RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'registro de eventos nao pode ser apagado';
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER eventos_presenca_sem_exclusao
                    BEFORE DELETE ON eventos_presenca
                    FOR EACH ROW EXECUTE FUNCTION eventos_sem_exclusao();

                CREATE TRIGGER eventos_categoria_sem_exclusao
                    BEFORE DELETE ON eventos_categoriadeevento
                    FOR EACH ROW EXECUTE FUNCTION eventos_sem_exclusao();
            """,
            reverse_sql="""
                DROP TRIGGER eventos_categoria_sem_exclusao ON eventos_categoriadeevento;
                DROP TRIGGER eventos_presenca_sem_exclusao ON eventos_presenca;
                DROP FUNCTION eventos_sem_exclusao();
                DROP TRIGGER eventos_evento_imutavel ON eventos_evento;
                DROP FUNCTION eventos_evento_imutavel();
            """,
        ),
    ]
