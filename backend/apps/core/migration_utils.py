"""
apps/core/migration_utils.py — Opérations de migration conditionnées au SGBD

POURQUOI
--------
Huit migrations de la refonte multi-tenant (v29) sont écrites en SQL brut
PostgreSQL — `ADD COLUMN IF NOT EXISTS`, `DO $$ … $$`, `varchar_pattern_ops`.
Ce choix était délibéré : il fallait des migrations REJOUABLES sur des bases
de production déjà partiellement modifiées à la main.

L'effet de bord était que la base de test SQLite ne se créait plus du tout :
la suite entière échouait au moment de `migrate`, avec 529 erreurs qui
n'avaient rien à voir avec le code testé. Un développeur sans PostgreSQL
local ne pouvait donc plus lancer un seul test.

COMMENT
-------
Le SQL brut reste la source de vérité sur PostgreSQL — on ne réécrit pas
des migrations déjà appliquées en production. On lui adjoint simplement un
équivalent Django standard, exécuté UNIQUEMENT sur les autres moteurs :

    SeparateDatabaseAndState(
        database_operations=[
            PostgresOnlySQL(sql=…, reverse_sql=…),   # ignoré hors PostgreSQL
            OtherVendorsOnly(AddField(…)),           # ignoré sur PostgreSQL
        ],
        state_operations=[AddField(…)],
    )

Les deux chemins produisent le même schéma ; aucun n'est exécuté deux fois.
Les bases PostgreSQL existantes ne voient AUCUN changement : ces migrations
y sont déjà marquées comme appliquées, et leur contenu PostgreSQL est
inchangé.
"""
from django.db import migrations

POSTGRES = "postgresql"


class PostgresOnlySQL(migrations.RunSQL):
    """SQL brut PostgreSQL — silencieusement ignoré sur les autres moteurs."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != POSTGRES:
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != POSTGRES:
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)


def _skip_on_postgres(operation_class):
    """
    Fabrique une variante d'opération Django ignorée sur PostgreSQL.

    Utilisée pour rejouer, sur SQLite, l'équivalent portable du SQL brut
    ci-dessus. L'opération conserve son `state_forwards` : placée dans
    `database_operations`, elle a besoin de l'état local pour retrouver le
    modèle et le champ à créer.
    """

    class _Operation(operation_class):
        def database_forwards(self, app_label, schema_editor, from_state, to_state):
            if schema_editor.connection.vendor == POSTGRES:
                return
            super().database_forwards(app_label, schema_editor, from_state, to_state)

        def database_backwards(self, app_label, schema_editor, from_state, to_state):
            if schema_editor.connection.vendor == POSTGRES:
                return
            super().database_backwards(app_label, schema_editor, from_state, to_state)

    _Operation.__name__ = f"NonPostgres{operation_class.__name__}"
    _Operation.__qualname__ = _Operation.__name__
    return _Operation


#: Équivalents portables, exécutés hors PostgreSQL uniquement.
NonPostgresAddField = _skip_on_postgres(migrations.AddField)
NonPostgresAlterField = _skip_on_postgres(migrations.AlterField)
NonPostgresAddConstraint = _skip_on_postgres(migrations.AddConstraint)
NonPostgresRemoveConstraint = _skip_on_postgres(migrations.RemoveConstraint)
NonPostgresAlterUniqueTogether = _skip_on_postgres(migrations.AlterUniqueTogether)


#: Correspondance opération Django → variante ignorée sur PostgreSQL.
_TWINS = {
    migrations.AddField: NonPostgresAddField,
    migrations.AlterField: NonPostgresAlterField,
    migrations.AddConstraint: NonPostgresAddConstraint,
    migrations.RemoveConstraint: NonPostgresRemoveConstraint,
    migrations.AlterUniqueTogether: NonPostgresAlterUniqueTogether,
}


def _twin(operation):
    """Reconstruit une opération dans sa variante « hors PostgreSQL »."""
    cls = _TWINS.get(type(operation))
    if cls is None:
        return None
    _name, args, kwargs = operation.deconstruct()
    return cls(*args, **kwargs)


def portable_schema_change(*, sql, reverse_sql, state_operations):
    """
    Un changement de schéma exprimé DEUX FOIS : en SQL PostgreSQL brut et
    idempotent, et en opérations Django portables.

    PostgreSQL exécute le SQL brut (rejouable sur une base déjà modifiée à
    la main, ce qui était l'objectif d'origine) ; les autres moteurs —
    SQLite en test — exécutent l'équivalent Django. Un seul des deux
    chemins s'exécute, jamais les deux.

    `state_operations` reste la description de référence du schéma : c'est
    elle que voient les migrations suivantes, quel que soit le moteur.
    """
    twins = [twin for twin in (_twin(op) for op in state_operations) if twin is not None]
    return migrations.SeparateDatabaseAndState(
        database_operations=[
            PostgresOnlySQL(sql=sql, reverse_sql=reverse_sql),
            *twins,
        ],
        state_operations=state_operations,
    )
