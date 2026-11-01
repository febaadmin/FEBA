from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def reprendre(apps, schema_editor):
    """
    Conserve les droits d'aujourd'hui, à confirmer par l'administration : chaque
    matière de l'enseignant au programme de chacune de ses classes (toutes si la
    classe n'a pas de programme), plus les
    paires qui portent déjà une note active. Aucune note n'est modifiée.
    """
    Teacher = apps.get_model("teachers", "Teacher")
    Assignment = apps.get_model("teachers", "TeacherAssignment")
    Grade = apps.get_model("grades", "Grade")
    lignes = set()
    for teacher in Teacher.objects.prefetch_related("classes__subjects", "subjects"):
        classes = {c.pk: {s.pk for s in c.subjects.all()} for c in teacher.classes.all()}
        matieres = {s.pk for s in teacher.subjects.all()}
        for class_id, programme in classes.items():
            lignes.update((teacher.pk, class_id, s) for s in (matieres & programme if programme else matieres))
        notes = Grade.objects.filter(teacher=teacher, is_deleted=False).values_list(
            "student__current_class_id", "subject_id")
        lignes.update((teacher.pk, c, s) for c, s in notes if c in classes and s in matieres)
    Assignment.objects.bulk_create([
        Assignment(teacher_id=t, class_obj_id=c, subject_id=s, source="reprise") for t, c, s in sorted(lignes)
    ])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("grades", "0014_alter_grade_note_coefficient"),
        ("classes", "__latest__"),
        ("subjects", "__latest__"),
        ("teachers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("reprise", "Reprise automatique, à confirmer"), ("admin", "Confirmée par l'administration")], default="admin", max_length=10)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("class_obj", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_assignments", to="classes.class")),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("subject", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_assignments", to="subjects.subject")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="teachers.teacher")),
            ],
            options={"verbose_name": "Affectation enseignant"},
        ),
        migrations.AddConstraint(
            model_name="teacherassignment",
            constraint=models.UniqueConstraint(fields=("teacher", "class_obj", "subject"), name="uniq_affectation_enseignant"),
        ),
        migrations.RunPython(reprendre, migrations.RunPython.noop),
    ]
