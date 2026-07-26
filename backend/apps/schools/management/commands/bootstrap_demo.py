"""
V8 — Préparation COMPLÈTE d'une base de démonstration.

Pourquoi cette commande existe
------------------------------
La base de démonstration était jusqu'ici créée à la main par
`migrate --run-syncdb` puis `seed_demo_data`. Or les réglages `dev_sqlite`
neutralisent les migrations (`MIGRATION_MODULES = _DisableMigrations()`, voir
le commentaire de ce fichier) : le schéma était bien créé, mais **aucune
migration de données ne s'exécutait**. La migration `grades/0011`, qui ramène
tous les poids d'évaluation à 1, était donc systématiquement sautée — une
installation de démonstration pouvait conserver d'anciens poids ≠ 1 et donc
des moyennes fausses, alors qu'une installation réelle (PostgreSQL, chaîne de
migrations complète) était correcte.

Cette commande reproduit le comportement d'une installation réelle :

  1. migrations Django (chaîne complète si elle est disponible ; sinon schéma
     dérivé des modèles) ;
  2. migrations de DONNÉES V8 appliquées explicitement si la chaîne a été
     court-circuitée ;
  3. seeds ;
  4. VÉRIFICATION BLOQUANTE : aucune note ne peut avoir un poids ≠ 1.

Usage :
    python manage.py bootstrap_demo
    python manage.py bootstrap_demo --skip-website
    python manage.py bootstrap_demo --check-only   # vérifie sans rien écrire
"""
import importlib

from django.apps import apps as global_apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.migrations.recorder import MigrationRecorder

from apps.grades.grading import ASSESSMENT_WEIGHT

# Migrations de DONNÉES V8 à rejouer quand la chaîne de migrations est
# neutralisée (mode démonstration SQLite). Format : (app, module, fonction).
DATA_MIGRATIONS = [
    ("grades", "apps.grades.migrations.0011_assessment_weight_one", "forwards"),
]


class Command(BaseCommand):
    help = ("Prépare une base de démonstration complète : migrations, "
            "migrations de données V8, seeds, puis vérification des poids.")

    def add_arguments(self, parser):
        parser.add_argument("--skip-website", action="store_true",
                            help="Ne pas seeder le site vitrine.")
        parser.add_argument("--check-only", action="store_true",
                            help="Vérifier seulement l'invariant des poids.")

    # ── Étapes ──────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        if options["check_only"]:
            self._verify_weights()
            return

        self._migrate()
        self._apply_data_migrations()
        self._seed(skip_website=options["skip_website"])
        self._verify_weights()
        self.stdout.write(self.style.SUCCESS(
            "\n✅ Base de démonstration prête et conforme."))

    def _migrate(self):
        self.stdout.write(self.style.MIGRATE_HEADING("1. Migrations Django"))
        call_command("migrate", run_syncdb=True, verbosity=1)

    def _migrations_are_disabled(self):
        """Vrai si les réglages neutralisent la chaîne de migrations."""
        modules = getattr(settings, "MIGRATION_MODULES", None)
        return bool(modules) and modules.get("grades", "absent") is None

    def _applied(self, app, name_prefix):
        try:
            return MigrationRecorder.Migration.objects.filter(
                app=app, name__startswith=name_prefix).exists()
        except Exception:               # table absente = rien d'appliqué
            return False

    def _apply_data_migrations(self):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n2. Migrations de DONNÉES V8"))
        disabled = self._migrations_are_disabled()
        for app, module_path, func_name in DATA_MIGRATIONS:
            prefix = module_path.rsplit(".", 1)[-1].split("_", 1)[0]
            if not disabled and self._applied(app, prefix):
                self.stdout.write(
                    f"  • {app}/{prefix} déjà appliquée par la chaîne de "
                    f"migrations — rien à rejouer.")
                continue
            module = importlib.import_module(module_path)
            getattr(module, func_name)(global_apps, None)
            self.stdout.write(
                f"  • {app}/{prefix} appliquée explicitement "
                f"(chaîne de migrations neutralisée).")

    def _seed(self, *, skip_website):
        self.stdout.write(self.style.MIGRATE_HEADING("\n3. Seeds"))
        call_command("seed_demo_data")
        if not skip_website:
            call_command("seed_website")

    def _verify_weights(self):
        """Vérification BLOQUANTE de l'invariant V8 (poids d'évaluation = 1)."""
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n4. Vérification des poids d'évaluation"))
        Grade = global_apps.get_model("grades", "Grade")
        total = Grade.objects.count()
        deviants = Grade.objects.exclude(note_coefficient=ASSESSMENT_WEIGHT)
        count = deviants.count()
        self.stdout.write(
            f"  nombre de notes avec poids d'évaluation != {ASSESSMENT_WEIGHT} "
            f"= {count}   (sur {total} note(s))")
        if count:
            exemples = list(deviants.values_list("id", "note_coefficient")[:5])
            raise CommandError(
                f"{count} note(s) ont un poids d'évaluation ≠ "
                f"{ASSESSMENT_WEIGHT} — la base n'est PAS conforme à la règle "
                f"V8. Exemples (id, poids) : {exemples}")
        self.stdout.write(self.style.SUCCESS("  ✔ conforme"))
