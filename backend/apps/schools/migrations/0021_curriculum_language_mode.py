from django.db import migrations, models

from apps.schools.curriculum import classify_curriculum

# Valeurs par défaut des parcours monolingues par type d'entité
# (School.DEFAULT_FEATURES), surchargées par settings['features'].
MONOLINGUAL_DEFAULT = {"campus": False, "online": True}


def classify_existing(apps, schema_editor):
    """
    Classe chaque académie d'après SES matières et SES classes. Une académie
    ambiguë reste à NULL (comportement historique conservé) :
    `manage.py academy_languages_report` la liste avec le motif.
    """
    School = apps.get_model("schools", "School")
    Subject = apps.get_model("subjects", "Subject")
    Class = apps.get_model("classes", "Class")
    for school in School.objects.filter(curriculum_language_mode__isnull=True):
        languages = Subject.objects.filter(school_id=school.pk).values_list("language", flat=True)
        tracks = Class.objects.filter(school_year__school_id=school.pk).values_list(
            "language_track", flat=True)
        overrides = (school.settings or {}).get("features") or {}
        allowed = bool(overrides.get("monolingual_classes",
                                     MONOLINGUAL_DEFAULT.get(school.entity_type, False)))
        mode, _reason = classify_curriculum(languages, tracks, allowed)
        if mode:
            School.objects.filter(pk=school.pk).update(curriculum_language_mode=mode)


def unclassify(apps, schema_editor):
    """Retour arrière : la colonne disparaît, rien d'autre n'a été modifié."""


class Migration(migrations.Migration):

    dependencies = [
        ('schools', '0020_academy_type'),
        ('subjects', '0005_alter_subject_options'),
        ('classes', '0004_audit_language_tracks'),
    ]

    operations = [
        migrations.AddField(
            model_name='school',
            name='curriculum_language_mode',
            field=models.CharField(blank=True, choices=[('french_only', 'Français uniquement'), ('english_only', 'Anglais uniquement'), ('bilingual', 'Bilingue français-anglais')], help_text="Programme linguistique : matières françaises seulement, anglaises seulement, ou les deux. Obligatoire à la création ; vide = académie antérieure à configurer (fonctionnement historique conservé).", max_length=20, null=True),
        ),
        migrations.RunPython(classify_existing, unclassify),
    ]
