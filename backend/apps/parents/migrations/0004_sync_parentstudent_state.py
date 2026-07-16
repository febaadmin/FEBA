from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parents", "0003_remove_single_parent_constraint"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="parentstudent",
                    name="created_at",
                    field=models.DateTimeField(auto_now_add=True),
                ),
                migrations.AlterField(
                    model_name="parentstudent",
                    name="is_primary_contact",
                    field=models.BooleanField(
                        default=False,
                        help_text=(
                            "Contact prioritaire pour les communications "
                            "de l'établissement."
                        ),
                    ),
                ),
            ],
        ),
    ]
