"""
Répare les académies qui ont des années mais aucune année ACTIVE.

POURQUOI
--------
Le filtre par défaut des listes de classes porte sur l'année active. Une
académie sans année active renvoyait donc zéro classe à toutes les listes
déroulantes — « Nouvelle salle virtuelle » ne proposait que « Toute
l'école », « Classes assignées » affichait « Aucun résultat » — pendant
que la page Classes, qui interroge une année précise, les affichait
toutes.

`SchoolYear.save()` empêche désormais cet état d'apparaître. Cette
migration répare celles qui y sont déjà, la base de production comprise.

CE QU'ELLE NE FAIT PAS
----------------------
Elle ne touche à AUCUNE académie qui a déjà une année active : déplacer
l'année de travail d'un établissement en service changerait ce que voient
tous ses écrans, sans que personne ne l'ait demandé. Seules les académies
qui n'en ont aucune sont concernées, et l'année retenue est la plus
récente — celle que l'utilisateur voit et manipule.
"""
from django.db import migrations


def activate_most_recent_year(apps, schema_editor):
    School = apps.get_model("schools", "School")
    SchoolYear = apps.get_model("schools", "SchoolYear")

    for school in School.objects.all():
        if SchoolYear.objects.filter(school=school, is_current=True).exists():
            continue
        recent = (SchoolYear.objects.filter(school=school)
                  .order_by("-start_date", "-id").first())
        if recent is not None:
            recent.is_current = True
            recent.save(update_fields=["is_current"])


def noop(apps, schema_editor):
    """
    Rien à défaire : désactiver une année remettrait une académie dans
    l'état exact que cette migration corrige.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0015_retire_legacy_institutional_phone"),
    ]

    operations = [
        migrations.RunPython(activate_most_recent_year, noop),
    ]
