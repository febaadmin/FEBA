# À exécuter avec le CODE DE LA VERSION PRÉCÉDENTE sur une COPIE de la base déjà migrée :
#   python manage.py shell < scripts/audit/rollback_columns_check.py
# Liste les colonnes NOT NULL sans défaut en base que l'ancien code ignore : chacune
# empêcherait un retour arrière du code sans restauration. Attendu : RISKY [].
from django.apps import apps
from django.db import connection
known = {}
for m in apps.get_models():
    known[m._meta.db_table] = {f.column for f in m._meta.concrete_fields} | \
        {f.m2m_db_table() for f in m._meta.many_to_many}
with connection.cursor() as c:
    c.execute("""select table_name, column_name from information_schema.columns
                 where table_schema='public' and is_nullable='NO' and column_default is null""")
    rows = c.fetchall()
risky = sorted((t, col) for t, col in rows if t in known and col not in known[t])
new_tables = sorted({t for t, _ in rows if t not in known})
print("RISKY", risky)
print("NEWTABLES", new_tables)
