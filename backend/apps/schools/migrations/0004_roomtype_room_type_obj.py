from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0003_room_custom_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoomType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="Nom du type")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="room_types",
                        to="schools.school",
                    ),
                ),
            ],
            options={
                "verbose_name": "Type de salle",
                "ordering": ["name"],
                "unique_together": {("school", "name")},
            },
        ),
        migrations.AddField(
            model_name="room",
            name="room_type_obj",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rooms",
                to="schools.roomtype",
                verbose_name="Type personnalisé",
            ),
        ),
    ]
