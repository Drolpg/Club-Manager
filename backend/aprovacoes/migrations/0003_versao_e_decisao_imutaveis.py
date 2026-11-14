"""Imutabilidade também no banco (adendo 1 da technical-spec), no padrão da auditoria.

A decisão recusa alteração e exclusão. A versão recusa exclusão e só aceita alterar as duas datas de lembrete:
a comparação é da linha inteira, menos essas duas colunas, e por isso uma coluna nova também fica protegida.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("aprovacoes", "0002_motivos_iniciais"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE FUNCTION aprovacoes_decisao_imutavel() RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'decisao nao pode ser alterada nem apagada';
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER aprovacoes_decisao_imutavel
                    BEFORE UPDATE OR DELETE ON aprovacoes_decisao
                    FOR EACH ROW EXECUTE FUNCTION aprovacoes_decisao_imutavel();

                CREATE FUNCTION aprovacoes_versao_imutavel() RETURNS trigger AS $$
                BEGIN
                    IF TG_OP = 'DELETE' THEN
                        RAISE EXCEPTION 'versao nao pode ser apagada';
                    END IF;
                    IF (to_jsonb(NEW) - 'lembrete_em' - 'aviso_ao_admin_em')
                        IS DISTINCT FROM (to_jsonb(OLD) - 'lembrete_em' - 'aviso_ao_admin_em') THEN
                        RAISE EXCEPTION 'versao so aceita alterar as datas de lembrete';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER aprovacoes_versao_imutavel
                    BEFORE UPDATE OR DELETE ON aprovacoes_versao
                    FOR EACH ROW EXECUTE FUNCTION aprovacoes_versao_imutavel();
            """,
            reverse_sql="""
                DROP TRIGGER aprovacoes_versao_imutavel ON aprovacoes_versao;
                DROP FUNCTION aprovacoes_versao_imutavel();
                DROP TRIGGER aprovacoes_decisao_imutavel ON aprovacoes_decisao;
                DROP FUNCTION aprovacoes_decisao_imutavel();
            """,
        ),
    ]
