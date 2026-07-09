# Generated migration — FEBA v8 fix
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    1. Fix relationship default ('father' in DB → 'guardian' in model).
    2. Add DB-level UNIQUE constraint on ParentStudent.student:
       each student can only be attached to ONE parent.
    Reversible: RemoveConstraint + revert AlterField.
    """

    dependencies = [
        ("parents", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="parentstudent",
            name="relationship",
            field=models.CharField(
                choices=[
                    ("father", "Père"),
                    ("mother", "Mère"),
                    ("guardian", "Tuteur"),
                    ("other", "Autre"),
                ],
                default="guardian",
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="parentstudent",
            constraint=models.UniqueConstraint(
                fields=["student"],
                name="unique_student_has_one_parent",
            ),
        ),
    ]
