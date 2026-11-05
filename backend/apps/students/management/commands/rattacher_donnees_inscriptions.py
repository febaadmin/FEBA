"""
Rattache aux inscriptions existantes les notes, paiements, absences et bulletins
restés sans inscription (même élève, même année). Aucune valeur n'est modifiée :
seul le lien vers l'inscription est renseigné.

    python manage.py rattacher_donnees_inscriptions                       # simulation
    python manage.py rattacher_donnees_inscriptions --appliquer --journal j.json
    python manage.py rattacher_donnees_inscriptions --annuler j.json
"""
import json
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.students.models import StudentEnrollment

MODELES = {
    "notes": ("apps.grades.models", "Grade"),
    "paiements": ("apps.payments.models", "Payment"),
    "absences": ("apps.attendance.models", "Attendance"),
    "bulletins": ("apps.bulletins.models", "Bulletin"),
}


def _modele(nom):
    import importlib
    module, classe = MODELES[nom]
    return getattr(importlib.import_module(module), classe)


class Command(BaseCommand):
    help = "Rattache les données orphelines (sans inscription) à l'inscription de leur élève et de leur année."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true")
        parser.add_argument("--journal")
        parser.add_argument("--annuler")

    def handle(self, *args, **o):
        if o["annuler"]:
            with open(o["annuler"], encoding="utf-8") as f:
                journal = json.load(f)
            n = 0
            with transaction.atomic():
                for nom, lignes in journal["lignes"].items():
                    for ligne in lignes:
                        n += _modele(nom).objects.filter(pk=ligne["id"], enrollment_id=ligne["inscription"]).update(enrollment=None)
            self.stdout.write(self.style.SUCCESS(f"{n} ligne(s) détachée(s)."))
            return
        inscriptions = {(e.student_id, e.school_year_id): e.pk for e in StudentEnrollment.objects.all().only("id", "student_id", "school_year_id")}
        plan = {}
        for nom in MODELES:
            lignes = []
            for pk, eleve, annee in _modele(nom).objects.filter(enrollment__isnull=True, school_year__isnull=False).values_list("id", "student_id", "school_year_id"):
                if (eleve, annee) in inscriptions:
                    lignes.append({"id": pk, "inscription": inscriptions[(eleve, annee)]})
            plan[nom] = lignes
        self.stdout.write("À rattacher : " + ", ".join(f"{k} {len(v)}" for k, v in plan.items()))
        if not o["appliquer"]:
            self.stdout.write("Simulation : rien n'a été écrit.")
            return
        if not o["journal"]:
            raise CommandError("--journal est obligatoire avec --appliquer (retour arrière).")
        with transaction.atomic():
            for nom, lignes in plan.items():
                for ligne in lignes:
                    _modele(nom).objects.filter(pk=ligne["id"], enrollment__isnull=True).update(enrollment_id=ligne["inscription"])
        with open(o["journal"], "w", encoding="utf-8") as f:
            json.dump({"date": datetime.now(timezone.utc).isoformat(), "lignes": plan}, f, indent=1)
        self.stdout.write(self.style.SUCCESS(f"Rattaché. Journal : {o['journal']}"))
