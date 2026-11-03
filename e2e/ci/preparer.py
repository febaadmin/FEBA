"""Prépare la base jetable des tests navigateur : modules activés sur les académies de démonstration."""
from apps.schools.models import School

MODULES = ("suivi_pedagogique", "suivi_familles", "evaluations_en_ligne", "monthly_reports",
           "online_admissions", "virtual_classrooms")

for ecole in School.objects.all():
    reglages = ecole.settings or {}
    reglages["features"] = {**reglages.get("features", {}), **{m: True for m in MODULES}}
    ecole.settings = reglages
    ecole.save(update_fields=["settings"])
print(f"modules activés sur {School.objects.count()} académie(s)")
