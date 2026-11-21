"""Imutabilidade também no banco, no padrão do motor e de `eventos` ("nada é apagado"; CA-29).

Nenhuma das nove tabelas aceita `DELETE`, e as três tabelas de versão não aceitam `UPDATE`: uma versão gravada é
o registro do que se disse naquele momento.
"""

from django.db import migrations

TABELAS = (
    "comunicacao_categoriadedocumento",
    "comunicacao_comunicado",
    "comunicacao_versaodecomunicado",
    "comunicacao_vinculodedocumento",
    "comunicacao_reacao",
    "comunicacao_comentario",
    "comunicacao_versaodecomentario",
    "comunicacao_documento",
    "comunicacao_versaodedocumento",
)
VERSOES = (
    "comunicacao_versaodecomunicado",
    "comunicacao_versaodecomentario",
    "comunicacao_versaodedocumento",
)

SQL = """
CREATE FUNCTION comunicacao_sem_exclusao() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'registro de comunicacao nao pode ser apagado';
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION comunicacao_versao_imutavel() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'versao de comunicacao nao pode ser alterada';
END;
$$ LANGUAGE plpgsql;
"""
SQL += "".join(
    f"""
CREATE TRIGGER {tabela}_sem_exclusao
    BEFORE DELETE ON {tabela}
    FOR EACH ROW EXECUTE FUNCTION comunicacao_sem_exclusao();
"""
    for tabela in TABELAS
)
SQL += "".join(
    f"""
CREATE TRIGGER {tabela}_imutavel
    BEFORE UPDATE ON {tabela}
    FOR EACH ROW EXECUTE FUNCTION comunicacao_versao_imutavel();
"""
    for tabela in VERSOES
)

REVERSE_SQL = "".join(f"DROP TRIGGER {tabela}_imutavel ON {tabela};\n" for tabela in VERSOES)
REVERSE_SQL += "".join(f"DROP TRIGGER {tabela}_sem_exclusao ON {tabela};\n" for tabela in TABELAS)
REVERSE_SQL += "DROP FUNCTION comunicacao_versao_imutavel();\nDROP FUNCTION comunicacao_sem_exclusao();\n"


class Migration(migrations.Migration):
    dependencies = [
        ("comunicacao", "0002_categorias_e_concessoes_iniciais"),
    ]

    operations = [migrations.RunSQL(sql=SQL, reverse_sql=REVERSE_SQL)]
