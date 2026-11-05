"""
Complète la classe des inscriptions annuelles qui n'en ont pas.

Règle unique, sans invention : une inscription (élève, année) sans classe reçoit la
classe actuelle de l'élève SEULEMENT si cette classe appartient à la même année.
Toute autre inscription est laissée telle quelle et listée.

Par défaut, simulation : rien n'est écrit. `--appliquer` écrit dans une transaction
et enregistre un journal JSON (identifiants des inscriptions modifiées) qui permet
le retour arrière exact :

    python manage.py completer_classes_inscriptions                 # simulation
    python manage.py completer_classes_inscriptions --appliquer --journal /chemin/journal.json
    python manage.py completer_classes_inscriptions --annuler /chemin/journal.json
"""
import json
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.students.models import StudentEnrollment


class Command(BaseCommand):
    help = "Complète la classe des inscriptions sans classe à partir de la classe actuelle de la même année."

    def add_arguments(self, parser):
        parser.add_argument("--appliquer", action="store_true", help="Écrire (sinon : simulation).")
        parser.add_argument("--journal", help="Fichier JSON où consigner les inscriptions modifiées.")
        parser.add_argument("--annuler", help="Journal d'une exécution précédente : remet ces inscriptions sans classe.")
        parser.add_argument("--academie", type=int, help="Limiter à une académie (identifiant).")

    def handle(self, *args, **o):
        if o["annuler"]:
            return self.annuler(o["annuler"])
        qs = (StudentEnrollment.objects.filter(class_obj__isnull=True)
              .select_related("student__current_class", "student__school", "school_year"))
        if o["academie"]:
            qs = qs.filter(student__school_id=o["academie"])
        a_completer, ignorees = [], []
        for e in qs:
            cls = e.student.current_class
            if cls is not None and cls.school_year_id == e.school_year_id:
                a_completer.append((e, cls))
            else:
                ignorees.append(e)
        par_academie = {}
        for e, _ in a_completer:
            par_academie[e.student.school.name] = par_academie.get(e.student.school.name, 0) + 1
        self.stdout.write(f"Inscriptions sans classe : {qs.count()}")
        self.stdout.write(f"  complétables (classe actuelle de la même année) : {len(a_completer)} {par_academie}")
        self.stdout.write(f"  laissées telles quelles (pas de classe de cette année) : {len(ignorees)}")
        if not o["appliquer"]:
            self.stdout.write("Simulation : rien n'a été écrit. Ajoutez --appliquer --journal <fichier> pour écrire.")
            return
        if not o["journal"]:
            raise CommandError("--journal est obligatoire avec --appliquer (retour arrière).")
        with transaction.atomic():
            for e, cls in a_completer:
                StudentEnrollment.objects.filter(pk=e.pk, class_obj__isnull=True).update(class_obj=cls)
        with open(o["journal"], "w", encoding="utf-8") as f:
            json.dump({"date": datetime.now(timezone.utc).isoformat(),
                       "inscriptions": [{"id": e.pk, "classe": cls.pk} for e, cls in a_completer]}, f, indent=1)
        self.stdout.write(self.style.SUCCESS(f"{len(a_completer)} inscription(s) complétée(s). Journal : {o['journal']}"))

    def annuler(self, chemin):
        with open(chemin, encoding="utf-8") as f:
            journal = json.load(f)
        n = 0
        with transaction.atomic():
            for ligne in journal["inscriptions"]:
                # Seules les inscriptions encore dans l'état écrit par la commande sont remises.
                n += StudentEnrollment.objects.filter(pk=ligne["id"], class_obj_id=ligne["classe"]).update(class_obj=None)
        self.stdout.write(self.style.SUCCESS(f"{n} inscription(s) remise(s) sans classe."))
