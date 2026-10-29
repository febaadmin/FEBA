"""
Programme linguistique de chaque académie et, pour celles qui sont « à
configurer », le motif et la proposition déduite de leurs données (règle de
apps.schools.curriculum, la même que la migration 0021).

Lecture seule : ne modifie rien. Le programme se règle dans l'écran
« Académies » du super administrateur, qui affiche le diagnostic avant tout
changement.
"""
from django.core.management.base import BaseCommand

from apps.classes.models import Class
from apps.classes.subject_rules import allows_monolingual, curriculum_diagnostic
from apps.schools.curriculum import classify_curriculum
from apps.schools.models import School
from apps.subjects.models import Subject


class Command(BaseCommand):
    help = "Rapport des programmes linguistiques des académies (lecture seule)."

    def handle(self, *args, **options):
        labels = dict(School.CURRICULUM_CHOICES)
        pending = conflicts = 0
        for school in School.objects.order_by("name"):
            code = school.code or school.pk
            if school.curriculum_language_mode:
                diagnostic = curriculum_diagnostic(school, school.curriculum_language_mode)
                line = f"  {code:<18} {labels[school.curriculum_language_mode]}"
                if diagnostic["ok"]:
                    self.stdout.write(line)
                else:
                    conflicts += 1
                    self.stdout.write(self.style.WARNING(
                        f"{line} — {len(diagnostic['subjects'])} matière(s) hors programme, "
                        f"{diagnostic['grades']} note(s) rattachée(s) (conservées)"))
                continue
            pending += 1
            languages = Subject.objects.filter(school=school).values_list("language", flat=True)
            tracks = Class.objects.filter(school_year__school=school).values_list("language_track", flat=True)
            suggestion, reason = classify_curriculum(languages, tracks, allows_monolingual(school))
            hint = f" — proposition : {labels[suggestion]}" if suggestion else ""
            self.stdout.write(self.style.WARNING(f"  {code:<18} À CONFIGURER : {reason}{hint}"))
        if pending or conflicts:
            self.stdout.write(self.style.WARNING(
                f"{pending} académie(s) à configurer, {conflicts} avec des données hors programme "
                f"(écran « Académies », super administrateur)."))
        else:
            self.stdout.write(self.style.SUCCESS("Toutes les académies ont un programme linguistique cohérent."))
