"""
Aligne le parcours linguistique des classes existantes sur ce qu'elles
enseignent RÉELLEMENT.

CE QUE CETTE MIGRATION FAIT, ET CE QU'ELLE REFUSE DE FAIRE
----------------------------------------------------------
Le champ `language_track` a été introduit avec la valeur BILINGUAL pour
toutes les classes — le choix sûr, qui laissait FEBA intacte. Mais pour
FEBA French Heritage Academy, cette valeur est devenue fausse le jour où
le backend s'est mis à la faire respecter : une classe qui n'enseigne que
le français, déclarée bilingue, devient impossible à enregistrer.

La migration ne DEVINE pas. Elle lit les matières déjà assignées, qui
sont un fait, et n'en tire une conclusion que lorsque celle-ci est
univoque :

    uniquement des matières françaises  →  FRANCOPHONE
    uniquement des matières anglaises   →  ANGLOPHONE
    les deux langues                    →  BILINGUAL (inchangé)
    aucune matière                      →  INCHANGÉ, et signalé

Le dernier cas est le seul ambigu, et c'est précisément celui où il ne
faut rien décider : une classe sans matière ne dit rien de son parcours.
Elle garde la valeur par défaut et apparaît dans le rapport, pour qu'un
administrateur tranche depuis l'écran Classes.

CE QU'ELLE NE TOUCHE JAMAIS
---------------------------
Les académies qui n'autorisent pas les parcours monolingues. Pour
Faith & Excellence Bilingual Academy, toutes les classes restent
bilingues — c'est l'identité de l'établissement, et `effective_track()`
l'imposerait de toute façon.

RÉVERSIBILITÉ
-------------
La migration inverse ramène à BILINGUAL les classes qu'elle a modifiées,
c'est-à-dire l'état antérieur exact.
"""
from django.db import migrations

BILINGUAL = "BILINGUAL"
FRANCOPHONE = "FRANCOPHONE"
ANGLOPHONE = "ANGLOPHONE"

#: Doit rester identique à `subject_rules.FEATURE_MONOLINGUAL`. Les
#: modèles historiques n'exposent pas `School.features`, la règle est donc
#: relue ici à partir des champs bruts.
FEATURE_MONOLINGUAL = "monolingual_classes"


def _autorise_monolingue(school):
    surcharge = ((school.settings or {}).get("features") or {})
    if FEATURE_MONOLINGUAL in surcharge:
        return bool(surcharge[FEATURE_MONOLINGUAL])
    return school.entity_type == "online"


def aligner(apps, schema_editor):
    Class = apps.get_model("classes", "Class")
    School = apps.get_model("schools", "School")

    concernees = {
        s.id for s in School.objects.all() if _autorise_monolingue(s)
    }
    if not concernees:
        return

    ajustees, a_valider = [], []
    classes = Class.objects.filter(
        school_year__school_id__in=concernees
    ).select_related("school_year__school").prefetch_related("subjects")

    for cls in classes:
        langues = set(cls.subjects.values_list("language", flat=True))
        if not langues:
            if cls.language_track == BILINGUAL:
                a_valider.append(f"{cls.school_year.school.code}/{cls.name}")
            continue

        if langues == {"fr"}:
            cible = FRANCOPHONE
        elif langues == {"en"}:
            cible = ANGLOPHONE
        else:
            cible = BILINGUAL

        if cible != cls.language_track:
            cls.language_track = cible
            cls.save(update_fields=["language_track"])
            ajustees.append(
                f"{cls.school_year.school.code}/{cls.name} → {cible}")

    if ajustees:
        print("\n  [classes.0004] parcours déduits des matières assignées :")
        for ligne in ajustees:
            print(f"    - {ligne}")
    if a_valider:
        print("\n  [classes.0004] classes SANS matière : parcours laissé à "
              "BILINGUAL, à confirmer depuis l'écran Classes :")
        for ligne in a_valider:
            print(f"    - {ligne}")


def revenir(apps, schema_editor):
    """Ramène à BILINGUAL les classes des académies concernées."""
    Class = apps.get_model("classes", "Class")
    School = apps.get_model("schools", "School")
    concernees = {s.id for s in School.objects.all() if _autorise_monolingue(s)}
    if concernees:
        Class.objects.filter(
            school_year__school_id__in=concernees
        ).update(language_track=BILINGUAL)


class Migration(migrations.Migration):

    dependencies = [
        ("classes", "0003_class_language_track"),
        ("schools", "0016_activate_orphan_school_years"),
        ("subjects", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(aligner, revenir),
    ]
