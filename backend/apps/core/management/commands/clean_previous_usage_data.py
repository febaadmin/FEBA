"""
clean_previous_usage_data — remise à zéro des données d'usage antérieures.

OBJET
-----
Repartir d'une base propre pour la mise en service : on efface tout ce qui
relève de l'USAGE (élèves, parents, notes, paiements, messages, documents
générés…) en conservant intégralement la STRUCTURE (académies, matières,
classes, niveaux, salles, branding) et les COMPTES D'ENCADREMENT
(super administrateurs, administrateurs, enseignants).

POURQUOI CETTE COMMANDE PLUTÔT QU'UN `flush`
--------------------------------------------
`flush` vide TOUTES les tables, y compris les académies, les matières, les
classes et les comptes d'encadrement : la structure serait à reconstruire à
la main et les matricules repartiraient de zéro. Ici, la suppression est
sélective, vérifiée, transactionnelle et réversible tant qu'elle n'est pas
validée.

GARDE-FOUS
----------
  * `--dry-run` et `--execute` sont exclusifs, et l'un des deux est requis :
    aucune exécution « par défaut » n'est possible.
  * `--execute` exige `--confirm DELETE-PREVIOUS-USAGE-DATA`, à la lettre.
  * Un dry-run n'écrit RIEN : il travaille dans une transaction
    systématiquement annulée, ce qui lui permet de compter les cascades
    réelles sans en subir les effets.
  * Toute la suppression tient dans une seule transaction : si une
    vérification post-suppression échoue, l'ensemble est annulé
    (statut `ROLLED_BACK`).
  * Un verrou de fichier interdit deux exécutions simultanées.

Voir PREVIOUS_USAGE_CLEANUP.md pour le mode d'emploi complet.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction
from django.db.models.deletion import Collector

CONFIRM_TOKEN = "DELETE-PREVIOUS-USAGE-DATA"

#: Rôles dont les comptes sont TOUJOURS conservés. `enseignant` est accepté
#: en plus de `teacher` : les deux orthographes coexistent dans les données
#: historiques et supprimer un enseignant serait irréversible.
PROTECTED_ROLES = ("superadmin", "admin", "teacher", "enseignant")

#: Rôles dont les comptes relèvent de l'usage et sont supprimés.
DELETABLE_ROLES = ("student", "parent")


class _DryRunRollback(Exception):
    """Annule la transaction d'un dry-run. Jamais propagée à l'appelant."""


class _VerificationFailed(Exception):
    """Une vérification post-suppression a échoué : tout est annulé."""


def _model(label: str):
    """Renvoie un modèle, ou None s'il n'existe pas dans cette version."""
    try:
        return django_apps.get_model(label)
    except LookupError:
        return None


#: Modèles STRUCTURELS — jamais supprimés, et dont on vérifie après coup que
#: ni les identifiants ni les quantités n'ont bougé.
STRUCTURAL_MODELS = (
    "schools.School",
    "subjects.Subject",
    "classes.Class",
    "schools.Level",
)

#: Modèles conservés sans vérification d'identifiants (volume variable
#: légitime, ex. séquences qui peuvent s'incrémenter).
PRESERVED_MODELS = (
    "schools.SchoolBranding",
    "schools.SchoolYear",
    "schools.RoomType",
    "schools.Room",
    "teachers.Teacher",
    "students.StudentMatriculeSequence",
    "documents.DocumentNumberSequence",
    "website.SiteSettings",
    "website.GalleryAlbum",
)

#: Données d'usage à supprimer.
#:
#: `academy_path` est le chemin d'ORM menant à l'académie, utilisé par
#: `--academy`. `None` signifie qu'aucun rattachement fiable n'existe : le
#: modèle n'est alors traité qu'en nettoyage global, et l'omission est
#: signalée dans le rapport plutôt que devinée.
USAGE_MODELS = (
    # (label, academy_path)
    ("grades.GradeHistory", "grade__student__school"),
    ("grades.Grade", "student__school"),
    ("bulletins.Bulletin", "student__school"),
    ("attendance.Attendance", "student__school"),
    ("payments.PaymentHistory", "payment__student__school"),
    ("payments.Payment", "student__school"),
    ("monthly_reports.MonthlyReportAttempt", "report__student__school"),
    ("monthly_reports.MonthlyStudentReport", "student__school"),
    ("homework.HomeworkAttachment", "homework__cls__school_year__school"),
    ("homework.Homework", "cls__school_year__school"),
    ("documents.DocumentEvent", "document__student__school"),
    ("documents.GeneratedDocument", "student__school"),
    ("virtualclass.VirtualRoomAttendance", "room__school"),
    ("virtualclass.VirtualRoom", "school"),
    ("messaging.Message", "sender__school"),
    # Une conversation n'appartient à aucune académie : elle est définie par
    # ses participants, qui peuvent relever d'académies différentes. La
    # rattacher arbitrairement à l'une d'elles serait faux, on ne la traite
    # donc qu'en nettoyage global.
    ("messaging.Conversation", None),
    ("notifications.Notification", "user__school"),
    ("notifications.EmailDelivery", "entity"),
    ("announcements.Announcement", "author__school"),
    ("parents.ParentStudent", "student__school"),
    ("students.StudentEnrollment", "student__school"),
    # `Student.user` est en SET_NULL : supprimer le compte NE supprime PAS
    # le profil, il le laisse orphelin (user=NULL). Le profil doit donc être
    # supprimé explicitement, et AVANT les comptes pour que les cascades
    # restent lisibles. `Parent.user` est en CASCADE et part avec le compte,
    # mais on le liste aussi pour couvrir les profils déjà orphelins.
    ("students.Student", "school"),
    ("parents.Parent", "user__school"),
    ("website.FHAApplicationStatusHistory", "application__entity"),
    ("website.FHAPlacementTestResult", "request__application__entity"),
    ("website.FHAPlacementTestRequest", "application__entity"),
    ("website.FHAEnrollmentApplication", "entity"),
    ("website.ContactMessage", "entity"),
    ("website.PreRegistration", "entity"),
    ("schools.EntitySwitchLog", None),
    ("accounts.PasswordResetLog", None),
    ("incidents.TechnicalIncident", None),
    ("user_files.UserFile", None),
)

#: Jetons JWT — supprimés en dernier, après les comptes.
TOKEN_MODELS = (
    "token_blacklist.BlacklistedToken",
    "token_blacklist.OutstandingToken",
)


class Command(BaseCommand):
    help = (
        "Supprime les données d'usage antérieures (élèves, parents, notes, "
        "paiements, messages…) en conservant la structure et les comptes "
        "d'encadrement. Exige --dry-run ou --execute."
    )

    # ── Options ──────────────────────────────────────────────────────────
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Simule et n'écrit rien. Exclusif avec --execute.",
        )
        parser.add_argument(
            "--execute", action="store_true",
            help="Exécute réellement. Exige --confirm.",
        )
        parser.add_argument(
            "--confirm", default="",
            help=f"Doit valoir exactement « {CONFIRM_TOKEN} » avec --execute.",
        )
        parser.add_argument(
            "--academy", default=None,
            help="Restreint le nettoyage à une académie (code de School).",
        )
        parser.add_argument(
            "--keep-sessions", action="store_true",
            help="Conserve les sessions Django au lieu de les supprimer.",
        )
        parser.add_argument(
            "--report-json", default=None,
            help="Chemin d'écriture du rapport JSON.",
        )

    # ── Point d'entrée ───────────────────────────────────────────────────
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        execute = options["execute"]
        confirm = options["confirm"]
        academy_code = options["academy"]
        keep_sessions = options["keep_sessions"]
        report_path = options["report_json"]

        # — Sécurité des options : refuser tout ce qui est ambigu ——————
        if dry_run and execute:
            raise CommandError(
                "--dry-run et --execute sont exclusifs : choisissez l'un ou l'autre."
            )
        if not dry_run and not execute:
            raise CommandError(
                "Précisez --dry-run (simulation) ou --execute (suppression réelle). "
                "Aucun mode par défaut n'est appliqué."
            )
        if execute and confirm != CONFIRM_TOKEN:
            raise CommandError(
                f"--execute exige --confirm {CONFIRM_TOKEN} "
                f"(reçu : « {confirm or 'rien'} »)."
            )

        academy = self._resolve_academy(academy_code)

        report = {
            "mode": "dry-run" if dry_run else "execute",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "database": self._safe_database_label(),
            "debug": self._debug_flag(),
            "academy_filter": academy_code,
            "academies_processed": [],
            "keep_sessions": keep_sessions,
            "counts_before": {},
            "counts_after": {},
            "direct_deletions": {},
            "cascade_deletions": {},
            "kept_accounts": [],
            "deleted_accounts": [],
            "media_files": [],
            "anomalies": [],
            "status": None,
        }

        with self._exclusive_lock():
            try:
                with transaction.atomic():
                    self._run(report, academy, keep_sessions, dry_run)
                    if dry_run:
                        # Un dry-run a compté les cascades RÉELLES ; on annule
                        # maintenant tout ce qu'il a touché.
                        raise _DryRunRollback
                report["status"] = "SUCCESS"
            except _DryRunRollback:
                report["status"] = "SUCCESS"
                report["note"] = "Simulation annulée : aucune écriture."
            except _VerificationFailed as exc:
                report["status"] = "ROLLED_BACK"
                report["anomalies"].append(str(exc))

        report["finished_at"] = datetime.now(timezone.utc).isoformat()

        if report_path:
            with open(report_path, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, ensure_ascii=False)

        self._print_summary(report)

        if report["status"] == "ROLLED_BACK":
            raise CommandError(
                "Vérification post-suppression en échec : transaction annulée, "
                "la base est inchangée. Voir les anomalies ci-dessus."
            )
        return None

    # ── Déroulé ──────────────────────────────────────────────────────────
    def _run(self, report, academy, keep_sessions, dry_run):
        User = get_user_model()

        # 1. État structurel AVANT — identifiants et quantités mémorisés.
        structural_before = self._structural_snapshot(academy)
        report["counts_before"] = self._count_all(academy)

        report["academies_processed"] = [
            {"id": s.id, "code": getattr(s, "code", None), "name": str(s)}
            for s in self._academies(academy)
        ]

        # 2. Comptes conservés / supprimés.
        kept_qs = User.objects.filter(role__in=PROTECTED_ROLES)
        deletable_qs = User.objects.filter(role__in=DELETABLE_ROLES)
        if academy is not None:
            deletable_qs = deletable_qs.filter(school=academy)

        report["kept_accounts"] = list(
            kept_qs.values_list("email", flat=True).order_by("email")
        )
        report["deleted_accounts"] = list(
            deletable_qs.values_list("email", flat=True).order_by("email")
        )
        kept_ids = set(kept_qs.values_list("id", flat=True))

        # 3. Suppression des données d'usage, dans l'ordre des dépendances.
        for label, academy_path in USAGE_MODELS:
            model = _model(label)
            if model is None:
                continue
            qs = model._default_manager.all()
            if academy is not None:
                if academy_path is None:
                    report["anomalies"].append(
                        f"{label} : aucun rattachement d'académie fiable — "
                        f"ignoré en mode --academy (nettoyé en mode global)."
                    )
                    continue
                qs = qs.filter(**{f"{academy_path}": academy})
            self._delete_queryset(qs, label, report)

        # 4. Fichiers médias rattachés aux enregistrements supprimés.
        #    Recensés systématiquement, effacés du disque en mode réel seulement.
        self._collect_media(report, dry_run)

        # 5. Comptes élève / parent.
        self._delete_queryset(deletable_qs, "accounts.CustomUser", report)

        # 6. Jetons JWT et sessions.
        for label in TOKEN_MODELS:
            model = _model(label)
            if model is not None:
                self._delete_queryset(model._default_manager.all(), label, report)

        if not keep_sessions:
            session = _model("sessions.Session")
            if session is not None:
                self._delete_queryset(
                    session._default_manager.all(), "sessions.Session", report
                )

        # 7. Vérifications post-suppression — toute anomalie annule tout.
        report["counts_after"] = self._count_all(academy)
        self._verify(structural_before, kept_ids, academy, report)

    # ── Suppression instrumentée ─────────────────────────────────────────
    def _delete_queryset(self, qs, label, report):
        """Supprime en relevant les cascades réellement déclenchées."""
        count = qs.count()
        if not count:
            return
        report["direct_deletions"][label] = report["direct_deletions"].get(label, 0) + count

        # Le Collector expose ce que Django va supprimer PAR CASCADE — c'est
        # ce qui permet d'affirmer qu'aucune donnée structurelle n'est
        # emportée sans qu'on l'ait vu.
        try:
            collector = Collector(using=router.db_for_write(qs.model))
            collector.collect(list(qs))
            for model, instances in collector.data.items():
                cascade_label = f"{model._meta.app_label}.{model.__name__}"
                if cascade_label == label:
                    continue
                report["cascade_deletions"][cascade_label] = (
                    report["cascade_deletions"].get(cascade_label, 0) + len(instances)
                )
                if cascade_label in STRUCTURAL_MODELS:
                    report["anomalies"].append(
                        f"CASCADE INTERDITE : supprimer {label} emporterait "
                        f"{len(instances)} {cascade_label}."
                    )
        except Exception as exc:  # pragma: no cover - instrumentation seule
            report["anomalies"].append(f"Collector indisponible sur {label} : {exc}")

        qs.delete()

    # ── Vérifications ────────────────────────────────────────────────────
    def _verify(self, structural_before, kept_ids, academy, report):
        User = get_user_model()

        # a. Les modèles structurels sont intacts — identifiants ET quantités.
        after = self._structural_snapshot(academy)
        for label, before_ids in structural_before.items():
            now_ids = after.get(label, set())
            if now_ids != before_ids:
                lost = sorted(before_ids - now_ids)
                raise _VerificationFailed(
                    f"{label} : {len(lost)} enregistrement(s) structurel(s) "
                    f"perdu(s) (ids {lost[:10]})."
                )

        # b. Les comptes protégés sont tous là.
        still = set(User.objects.filter(id__in=kept_ids).values_list("id", flat=True))
        if still != kept_ids:
            raise _VerificationFailed(
                f"{len(kept_ids - still)} compte(s) d'encadrement supprimé(s) à tort."
            )

        # c. Leurs appartenances d'académie sont conservées.
        membership = _model("schools.OrganizationMembership")
        if membership is not None:
            orphan = membership._default_manager.exclude(user_id__in=still).exists()
            if orphan and academy is None:
                raise _VerificationFailed(
                    "Des OrganizationMembership subsistent sans compte associé."
                )

        # d. Aucun profil orphelin (élève/parent sans compte).
        for label, field in (("parents.Parent", "user"), ("students.Student", "user")):
            model = _model(label)
            if model is None:
                continue
            if model._default_manager.filter(**{f"{field}__isnull": False}).exclude(
                **{f"{field}__in": User.objects.all()}
            ).exists():
                raise _VerificationFailed(f"{label} : profils orphelins détectés.")

        # e. Plus aucun compte élève/parent dans le périmètre traité.
        leftovers = User.objects.filter(role__in=DELETABLE_ROLES)
        if academy is not None:
            leftovers = leftovers.filter(school=academy)
        if leftovers.exists():
            raise _VerificationFailed(
                f"{leftovers.count()} compte(s) élève/parent non supprimé(s)."
            )

    # ── Utilitaires ──────────────────────────────────────────────────────
    def _resolve_academy(self, code):
        if not code:
            return None
        School = _model("schools.School")
        if School is None:
            raise CommandError("Modèle schools.School introuvable.")
        try:
            return School._default_manager.get(code=code)
        except School.DoesNotExist:
            available = ", ".join(
                School._default_manager.values_list("code", flat=True)
            ) or "aucune"
            raise CommandError(
                f"Académie « {code} » inconnue. Académies disponibles : {available}."
            )

    def _academies(self, academy):
        School = _model("schools.School")
        if School is None:
            return []
        if academy is not None:
            return [academy]
        return list(School._default_manager.all())

    def _structural_snapshot(self, academy):
        """Identifiants de chaque modèle structurel, pour comparaison après."""
        snapshot = {}
        for label in STRUCTURAL_MODELS:
            model = _model(label)
            if model is None:
                continue
            snapshot[label] = set(
                model._default_manager.values_list("id", flat=True)
            )
        return snapshot

    def _count_all(self, academy):
        counts = {}
        labels = (
            list(STRUCTURAL_MODELS)
            + list(PRESERVED_MODELS)
            + [label for label, _ in USAGE_MODELS]
            + list(TOKEN_MODELS)
            + ["accounts.CustomUser", "sessions.Session"]
        )
        for label in labels:
            model = _model(label)
            if model is None:
                continue
            try:
                counts[label] = model._default_manager.count()
            except Exception:  # pragma: no cover - table absente
                continue
        return counts

    def _collect_media(self, report, dry_run):
        """
        Recense les fichiers médias des enregistrements supprimés.

        Ils ne sont effacés du disque QU'EN MODE RÉEL : un dry-run qui
        supprimerait des fichiers ne serait pas une simulation.
        """
        for label in ("documents.GeneratedDocument", "user_files.UserFile"):
            model = _model(label)
            if model is None:
                continue
            file_fields = [
                f.name for f in model._meta.get_fields()
                if getattr(f, "get_internal_type", lambda: "")() in ("FileField", "ImageField")
            ]
            if not file_fields:
                continue
            for obj in model._default_manager.all().iterator():
                for field in file_fields:
                    value = getattr(obj, field, None)
                    path = getattr(value, "path", None) if value else None
                    if not path or not os.path.exists(path):
                        continue
                    report["media_files"].append(path)
                    if not dry_run:
                        try:
                            os.remove(path)
                        except OSError as exc:
                            report["anomalies"].append(
                                f"Média non supprimé ({path}) : {exc}"
                            )

    def _safe_database_label(self):
        """Base ciblée, SANS mot de passe."""
        from django.conf import settings

        db = settings.DATABASES.get("default", {})
        engine = db.get("ENGINE", "?").rsplit(".", 1)[-1]
        name = db.get("NAME", "?")
        host = db.get("HOST") or "local"
        return f"{engine}://{host}/{name}"

    def _debug_flag(self):
        from django.conf import settings

        return bool(getattr(settings, "DEBUG", False))

    def _exclusive_lock(self):
        """Verrou inter-processus : deux nettoyages ne peuvent pas se croiser."""

        class _Lock:
            def __init__(self):
                self.path = os.path.join(
                    tempfile.gettempdir(), "feba_clean_previous_usage_data.lock"
                )
                self.handle = None

            def __enter__(self):
                self.handle = open(self.path, "w")
                try:
                    fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    self.handle.close()
                    raise CommandError(
                        "Un autre nettoyage est déjà en cours "
                        f"(verrou {self.path}). Réessayez plus tard."
                    )
                return self

            def __exit__(self, *exc):
                try:
                    fcntl.flock(self.handle, fcntl.LOCK_UN)
                finally:
                    self.handle.close()
                return False

        return _Lock()

    def _print_summary(self, report):
        w = self.stdout.write
        w("")
        w(f"  Mode           : {report['mode']}")
        w(f"  Base           : {report['database']}")
        w(f"  DEBUG          : {report['debug']}")
        w(f"  Académies      : {[a['code'] for a in report['academies_processed']]}")
        w(f"  Comptes gardés : {len(report['kept_accounts'])}")
        w(f"  Comptes purgés : {len(report['deleted_accounts'])}")
        w(f"  Médias         : {len(report['media_files'])}")
        if report["direct_deletions"]:
            w("  Suppressions directes :")
            for label, n in sorted(report["direct_deletions"].items()):
                w(f"    - {label:45s} {n}")
        if report["anomalies"]:
            w("  Anomalies :")
            for item in report["anomalies"]:
                w(f"    ! {item}")
        w(f"  Statut         : {report['status']}")
        if report["mode"] == "dry-run":
            w("  (simulation — aucune écriture effectuée)")
        w("")
