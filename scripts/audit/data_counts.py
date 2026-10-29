# Effectifs, empreinte des identifiants et sommes des entités critiques (lecture seule).
# À exécuter AVANT et APRÈS une migration sur une copie de la base ; les deux sorties
# doivent être identiques :  python manage.py shell < scripts/audit/data_counts.py
import json
from django.apps import apps
names = ["schools.School","schools.SchoolYear","accounts.CustomUser","students.Student","students.StudentEnrollment",
         "parents.Parent","parents.ParentStudent","teachers.Teacher","classes.Class","subjects.Subject",
         "grades.Grade","bulletins.Bulletin","payments.Payment","attendance.Attendance","schedule.ClassSchedule",
         "website.PreRegistration","website.FHAEnrollmentApplication"]
out = {}
for n in names:
    try:
        m = apps.get_model(n)
        out[n] = [m.objects.count(), sorted(m.objects.values_list("pk", flat=True))[:3] and
                  __import__("hashlib").sha256(",".join(map(str, m.objects.order_by("pk").values_list("pk", flat=True))).encode()).hexdigest()[:12]]
    except LookupError:
        out[n] = "absent"
from django.db.models import Sum
P = apps.get_model("payments.Payment")
out["payments.sum"] = str(P.objects.aggregate(s=Sum("amount"))["s"])
G = apps.get_model("grades.Grade")
out["grades.sum"] = str(G.objects.aggregate(s=Sum("value"))["s"])
print("COUNTS " + json.dumps(out, sort_keys=True))
