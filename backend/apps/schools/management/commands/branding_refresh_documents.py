"""
Documents COURANTS produits avant le dernier changement de logo d'une académie.

    python manage.py branding_refresh_documents --academy FEBA            # aperçu (rien n'est modifié)
    python manage.py branding_refresh_documents --academy FEBA --apply    # régénération
    options : --kinds bulletins,receipts,fha_sheets,prereg_sheets  --all (ignore les dates)

Un PDF stocké garde le logo qu'il avait à sa production : corriger le
générateur ne change pas les fichiers déjà écrits. Cette commande les
identifie (fichier plus ancien que le logo effectif de l'académie) et les
régénère avec les générateurs de l'application :

  - bulletins : le bulletin est RÉUTILISÉ (commentaire, notes, inscription
    conservés), nouveau PDF sous un nom unique, ancien fichier supprimé
    seulement après réussite ;
  - reçus de paiement : même remplacement atomique, paiement inchangé ;
  - fiches d'inscription FHA et fiches de préinscription : générateurs
    existants (« Régénérer la fiche »), qui conservent l'ancienne version.

N'est PAS régénéré : les rapports mensuels déjà envoyés. Ils font foi de ce
que la famille a reçu (règle de l'application : ils s'archivent, ils ne se
réécrivent pas) ; la commande les compte comme « historiques conservés ».

Idempotente : un document régénéré est plus récent que le logo et n'est plus
repris. Un échec n'interrompt pas les autres et laisse l'ancien fichier.
"""
import os
from datetime import datetime, timezone as dt_tz

from django.core.management.base import BaseCommand, CommandError

KINDS = ("bulletins", "receipts", "fha_sheets", "prereg_sheets")


def _mtime(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), tz=dt_tz.utc)
    except OSError:
        return None


def branding_changed_at(academy):
    """Date de la dernière modification du logo EFFECTIF de l'académie."""
    from apps.schools.branding import get_branding
    from apps.schools.models import SchoolBranding
    active = SchoolBranding.objects.filter(school=academy, is_active=True).first()
    if active is not None:
        return active.updated_at
    path = get_branding(academy).document_logo
    return _mtime(path) if path else None


class Command(BaseCommand):
    help = "Repère et régénère les documents courants produits avec un ancien logo."

    def add_arguments(self, parser):
        parser.add_argument("--academy", required=True, help="Code de l'académie (ex. FEBA, FEBA_FHA).")
        parser.add_argument("--kinds", default=",".join(KINDS))
        parser.add_argument("--apply", action="store_true", help="Régénère (sinon : aperçu seulement).")
        parser.add_argument("--all", action="store_true", help="Tous les documents, quelle que soit leur date.")

    def handle(self, *args, academy, kinds, apply, all, **opts):
        from apps.schools.models import School
        school = School.objects.filter(code=academy).first()
        if school is None:
            raise CommandError(f"Académie inconnue : {academy}")
        kinds = [k.strip() for k in kinds.split(",") if k.strip()]
        unknown = set(kinds) - set(KINDS)
        if unknown:
            raise CommandError(f"Types inconnus : {', '.join(sorted(unknown))}")
        since = None if all else branding_changed_at(school)
        self.stdout.write(f"Académie {school.code} — logo effectif modifié le {since or '—'}"
                          f" — mode {'APPLICATION' if apply else 'APERÇU (rien n’est modifié)'}")
        total_failed = 0
        for kind in kinds:
            items = list(getattr(self, f"_{kind}")(school))
            stale = [(label, path, regen) for label, path, regen in items
                     if since is None or (_mtime(path) or since) < since]
            ok, failed = 0, []
            if apply:
                for label, _path, regen in stale:
                    try:
                        if regen() is None:
                            raise RuntimeError("le générateur n'a rien produit")
                        ok += 1
                    except Exception as exc:  # un échec n'arrête pas les autres
                        failed.append(f"{label} : {exc}")
            total_failed += len(failed)
            self.stdout.write(f"  {kind:<14} {len(items):>5} documents · {len(stale):>5} antérieurs au logo"
                              + (f" · {ok} régénérés · {len(failed)} échecs" if apply else ""))
            for line in failed:
                self.stdout.write(f"      ÉCHEC {line}")
        from apps.monthly_reports.models import MonthlyStudentReport
        sent = MonthlyStudentReport.objects.filter(academy=school).exclude(sent_at__isnull=True).count() \
            if hasattr(MonthlyStudentReport, "sent_at") else 0
        self.stdout.write(f"  rapports mensuels envoyés : {sent} historiques conservés (non réécrits)")
        if total_failed:
            raise CommandError(f"{total_failed} document(s) non régénéré(s) ; les anciens fichiers sont conservés.")

    # ── Sources ────────────────────────────────────────────────────────

    def _bulletins(self, school):
        from apps.bulletins.models import Bulletin
        from apps.bulletins.pdf_generator import generate_bulletin
        for b in Bulletin.objects.filter(student__school=school).exclude(pdf_file="").exclude(
                pdf_file__isnull=True).select_related("student", "school_year"):
            yield (f"bulletin {b.pk} ({b.student.matricule} {b.period} {b.school_year.name})", b.pdf_file.path,
                   lambda b=b: generate_bulletin(b.student, b.period, b.school_year))

    def _receipts(self, school):
        from apps.payments.models import Payment
        from apps.payments.pdf_generator import generate_receipt
        for p in Payment.objects.filter(student__school=school).exclude(receipt_file="").exclude(
                receipt_file__isnull=True):
            yield (f"reçu {p.reference_number}", p.receipt_file.path, lambda p=p: generate_receipt(p))

    def _fha_sheets(self, school):
        from apps.website.fha_enrollment import generate_and_store_sheet
        from apps.website.models import FHAEnrollmentApplication
        for a in FHAEnrollmentApplication.objects.filter(entity=school).exclude(sheet_path=""):
            yield (f"fiche FHA {a.reference}", a.sheet_absolute_path if hasattr(a, "sheet_absolute_path")
                   else "", lambda a=a: generate_and_store_sheet(a))

    def _prereg_sheets(self, school):
        from apps.website.feba_prereg import generate_and_store_prereg_sheet
        from apps.website.models import PreRegistration
        for d in PreRegistration.objects.filter(entity=school).exclude(sheet_path=""):
            yield (f"fiche de préinscription {d.reference}", d.sheet_absolute_path,
                   lambda d=d: generate_and_store_prereg_sheet(d))
