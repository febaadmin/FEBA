from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("schools", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="Room",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("room_type", models.CharField(
                    choices=[("classroom","Salle de classe"),("computer","Salle informatique"),
                             ("canteen","Cantine"),("library","Bibliothèque"),
                             ("sports","Salle de sport"),("dance","Salle de danse"),
                             ("admin","Bureau administratif"),("other","Autre")],
                    default="classroom", max_length=20)),
                ("capacity", models.PositiveIntegerField(default=30)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="rooms", to="schools.school")),
            ],
            options={"verbose_name": "Salle", "ordering": ["name"]},
        )
    ]