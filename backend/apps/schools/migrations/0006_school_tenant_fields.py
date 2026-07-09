"""
schools/migrations/0006_school_tenant_fields.py — VERSION IDEMPOTENTE (v29.1)

Réécriture complète de la migration originale pour la rendre rejouable
sans erreur même si les colonnes ou index existent déjà en base.

POURQUOI atomic=False + IF NOT EXISTS ?
---------------------------------------
Django exécute les migrations dans une transaction. Mais dans PostgreSQL,
certaines opérations DDL (notamment la création des index "deferred SQL"
comme l'index `varchar_pattern_ops` pour LIKE) sont émises HORS de la
transaction principale par le SchemaEditor de Django. Si Django crashe
APRÈS la création de cet index mais AVANT d'enregistrer la migration dans
`django_migrations`, l'index reste en base (il était déjà commis) mais
la migration n'est pas marquée comme appliquée.

Résultat : une nouvelle tentative de `migrate` échoue avec :
  DuplicateTable: relation "schools_school_slug_b6a402eb_like" already exists

Avec `atomic=False` et `IF NOT EXISTS`, chaque opération est idempotente :
si elle trouve que la colonne/index existe déjà, elle l'ignore et continue.
La migration peut être relancée autant de fois que nécessaire.

Cette approche est la pratique recommandée (Django docs § "Non-atomic
migrations") pour toute migration qui modifie le schéma de façon
incompatible avec un rollback propre.
"""
from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs_idempotent(apps, schema_editor):
    """
    Remplit les slugs VIDES uniquement (idempotent).
    Si des slugs existent déjà (migration partielle précédente), ils
    sont conservés et exclus du traitement.
    """
    School = apps.get_model('schools', 'School')

    # Pré-charger les slugs déjà présents pour éviter les doublons
    seen = set(School.objects.exclude(slug='').values_list('slug', flat=True))

    for school in School.objects.filter(slug=''):
        base = slugify(school.name)[:70] or "ecole"
        slug = base
        i = 1
        while slug in seen or School.objects.filter(slug=slug).exclude(pk=school.pk).exists():
            i += 1
            slug = f"{base}-{i}"
        seen.add(slug)
        school.slug = slug
        school.save(update_fields=['slug'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    # atomic=False OBLIGATOIRE pour que les CREATE INDEX IF NOT EXISTS
    # fonctionnent correctement en PostgreSQL (cf. explication ci-dessus).
    atomic = False

    dependencies = [
        ('schools', '0005_schoolbranding_level_cycle'),
    ]

    operations = [
        # ── Étape 1 : colonnes (IF NOT EXISTS = idempotent) ─────────────────
        #
        # On utilise SeparateDatabaseAndState pour :
        #  - database_operations : SQL brut avec IF NOT EXISTS (PostgreSQL)
        #  - state_operations   : description Django des champs (pour que
        #    les migrations suivantes connaissent le schéma attendu)
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE schools_school
                            ADD COLUMN IF NOT EXISTS slug
                                VARCHAR(80) NOT NULL DEFAULT '',
                            ADD COLUMN IF NOT EXISTS is_active
                                BOOLEAN NOT NULL DEFAULT TRUE,
                            ADD COLUMN IF NOT EXISTS plan
                                VARCHAR(20) NOT NULL DEFAULT 'trial',
                            ADD COLUMN IF NOT EXISTS max_students
                                INTEGER NOT NULL DEFAULT 0,
                            ADD COLUMN IF NOT EXISTS trial_ends_at
                                DATE DEFAULT NULL,
                            ADD COLUMN IF NOT EXISTS subscription_notes
                                TEXT NOT NULL DEFAULT '';
                    """,
                    reverse_sql="""
                        ALTER TABLE schools_school
                            DROP COLUMN IF EXISTS slug,
                            DROP COLUMN IF EXISTS is_active,
                            DROP COLUMN IF EXISTS plan,
                            DROP COLUMN IF EXISTS max_students,
                            DROP COLUMN IF EXISTS trial_ends_at,
                            DROP COLUMN IF EXISTS subscription_notes;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='school',
                    name='slug',
                    field=models.SlugField(max_length=80, blank=True, default=''),
                ),
                migrations.AddField(
                    model_name='school',
                    name='is_active',
                    field=models.BooleanField(
                        default=True,
                        help_text=(
                            "Un établissement désactivé ne peut plus se connecter "
                            "(suspension d'abonnement, impayé...)."
                        ),
                    ),
                ),
                migrations.AddField(
                    model_name='school',
                    name='plan',
                    field=models.CharField(
                        max_length=20,
                        choices=[
                            ('trial', 'Essai gratuit'),
                            ('standard', 'Standard'),
                            ('premium', 'Premium'),
                        ],
                        default='trial',
                    ),
                ),
                migrations.AddField(
                    model_name='school',
                    name='max_students',
                    field=models.PositiveIntegerField(
                        default=0,
                        help_text="0 = illimité. Quota contractuel selon le plan souscrit.",
                    ),
                ),
                migrations.AddField(
                    model_name='school',
                    name='trial_ends_at',
                    field=models.DateField(null=True, blank=True),
                ),
                migrations.AddField(
                    model_name='school',
                    name='subscription_notes',
                    field=models.TextField(
                        blank=True,
                        default='',
                        help_text=(
                            "Notes internes (équipe commerciale/support), "
                            "non visibles par l'établissement."
                        ),
                    ),
                ),
            ],
        ),

        # ── Étape 2 : backfill slugs (idempotent) ───────────────────────────
        migrations.RunPython(backfill_slugs_idempotent, noop_reverse),

        # ── Étape 3 : index unique slug (IF NOT EXISTS = idempotent) ────────
        #
        # On crée manuellement les deux index que Django aurait générés
        # via AlterField(unique=True) :
        #   1. schools_school_slug_key       : index unique standard
        #   2. schools_school_slug_b6a402eb_like : index varchar_pattern_ops
        #      (utilisé par PostgreSQL pour les requêtes LIKE 'x%')
        #
        # Ces noms correspondent exactement à ceux que Django génère
        # automatiquement (confirmé par l'erreur réelle observée en prod).
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE UNIQUE INDEX IF NOT EXISTS schools_school_slug_key
                            ON schools_school (slug);
                        CREATE INDEX IF NOT EXISTS schools_school_slug_b6a402eb_like
                            ON schools_school (slug varchar_pattern_ops);
                    """,
                    reverse_sql="""
                        DROP INDEX IF EXISTS schools_school_slug_key;
                        DROP INDEX IF EXISTS schools_school_slug_b6a402eb_like;
                    """,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='school',
                    name='slug',
                    field=models.SlugField(
                        max_length=80,
                        unique=True,
                        blank=True,
                        help_text=(
                            "Identifiant court unique (sous-domaine / sélection tenant). "
                            "Généré automatiquement si vide."
                        ),
                    ),
                ),
            ],
        ),
    ]
