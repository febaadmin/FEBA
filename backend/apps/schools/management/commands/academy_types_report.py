"""
Liste le type de chaque académie et, pour celles qui ne sont pas classées,
le motif — d'après leurs données réelles (règle de apps.schools.academy_types).

Lecture seule : ne modifie rien. Le classement se fait dans l'écran
« Académies » du super administrateur, qui vérifie la cohérence des niveaux.
"""
from django.core.management.base import BaseCommand

from apps.schools.academy_types import classify
from apps.schools.models import School


class Command(BaseCommand):
    help = "Rapport des types d'académie (lecture seule)."

    def handle(self, *args, **options):
        unclassified = 0
        for school in School.objects.order_by("name"):
            cycles = set(school.levels.values_list("cycle", flat=True))
            if school.academy_type:
                self.stdout.write(f"  {school.code or school.pk:<14} {school.get_academy_type_display()}")
                continue
            unclassified += 1
            suggestion, reason = classify(school.entity_type, cycles)
            hint = f" - proposition : {dict(School.ACADEMY_TYPE_CHOICES)[suggestion]}" if suggestion else ""
            self.stdout.write(self.style.WARNING(
                f"  {school.code or school.pk:<14} NON CLASSÉE : {reason}{hint}"))
        if unclassified:
            self.stdout.write(self.style.WARNING(
                f"{unclassified} académie(s) à classer dans « Académies » (super administrateur)."))
        else:
            self.stdout.write(self.style.SUCCESS("Toutes les académies sont classées."))
