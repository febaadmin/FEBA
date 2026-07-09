"""
Management command: detect_incoherences_parent_eleve
Produces a CSV report of data integrity issues in the Parent ↔ Student
relationship.

Détecte (v29) :
  1. Liens ParentStudent où parent et élève n'appartiennent PAS au même
     établissement (fuite cross-tenant — devrait être impossible grâce
     à ParentStudent.clean(), mais vérifie les données existantes,
     notamment celles créées avant l'introduction de cette validation).
  2. Comptes Parent dont CustomUser.role != 'parent'.
  3. Comptes Élève (via ParentStudent.student.user) dont role != 'student'.
  4. Liens ParentStudent référençant un parent ou élève inexistant.

NOTE v29 — CHANGEMENT IMPORTANT : depuis la refonte multi-parents,
un élève lié à PLUSIEURS parents (père + mère + tuteur...) est un état
NORMAL et VOULU, plus une incohérence. L'ancienne vérification
"STUDENT_MULTI_PARENT" (qui faisait échouer ce script avec sys.exit(1)
dès qu'un élève avait 2 parents) a été supprimée : elle aurait
signalé comme "erreur" la fonctionnalité même que la v29 introduit.
Le nombre de parents par élève est maintenant juste informatif
(affiché dans le résumé, jamais une incohérence).

Usage:
  python manage.py detect_incoherences_parent_eleve
  python manage.py detect_incoherences_parent_eleve --output /tmp/report.csv
"""
import csv
import sys
from django.core.management.base import BaseCommand
from django.db.models import Count


class Command(BaseCommand):
    help = "Détecte les incohérences dans les liens Parent ↔ Élève et produit un CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="incoherences_parent_eleve.csv",
            help="Chemin du fichier CSV de sortie (défaut: incoherences_parent_eleve.csv)",
        )

    def handle(self, *args, **options):
        from apps.parents.models import Parent, ParentStudent
        from apps.students.models import Student

        rows = []

        # --- Info (non bloquant) : répartition du nombre de parents par élève ---
        multi = (
            ParentStudent.objects.values("student")
            .annotate(cnt=Count("id"))
            .filter(cnt__gt=1)
        )
        multi_count = multi.count()
        if multi_count:
            self.stdout.write(self.style.SUCCESS(
                f"ℹ️  {multi_count} élève(s) avec plusieurs parents enregistrés "
                f"— c'est attendu depuis la v29 (multi-parents), pas une erreur."
            ))

        # --- Check 1 (v29) : fuite cross-tenant parent ↔ élève ----------------
        # Devrait être impossible grâce à ParentStudent.clean(), sauf pour des
        # liens créés AVANT l'introduction de cette validation (à corriger
        # manuellement si détecté : ré-assigner le bon établissement, ou
        # supprimer le lien erroné).
        for ps in ParentStudent.objects.select_related("parent__user", "student"):
            parent_school_id = ps.parent.user.school_id if ps.parent.user else None
            student_school_id = ps.student.school_id
            if parent_school_id and student_school_id and parent_school_id != student_school_id:
                rows.append({
                    "type": "CROSS_TENANT_LEAK",
                    "student_id": ps.student.id,
                    "student_name": ps.student.get_full_name(),
                    "parent_id": ps.parent.id,
                    "parent_name": str(ps.parent),
                    "detail": (
                        f"Le parent#{ps.parent.id} (établissement {parent_school_id}) "
                        f"est lié à l'élève#{ps.student.id} (établissement "
                        f"{student_school_id}) — établissements différents."
                    ),
                })

        # --- Check 2 : ParentStudent référençant un student inexistant -------
        valid_student_ids = set(Student.objects.values_list("id", flat=True))
        for item in (
            ParentStudent.objects.values("student")
            .annotate(cnt=Count("id"))
        ):
            student_id = item["student"]
            if student_id not in valid_student_ids:
                rows.append({
                    "type": "ORPHAN_PARENTSTUDENT",
                    "student_id": student_id,
                    "student_name": "(introuvable)",
                    "parent_id": "",
                    "parent_name": "",
                    "detail": f"ParentStudent référence student_id={student_id} inexistant",
                })

        # --- Check 3 : Parent whose user.role != 'parent' ---------------------
        for p in Parent.objects.select_related("user"):
            if p.user.role != "parent":
                rows.append({
                    "type": "PARENT_WRONG_ROLE",
                    "student_id": "",
                    "student_name": "",
                    "parent_id": p.id,
                    "parent_name": str(p),
                    "detail": (
                        f"Parent#{p.id} (user={p.user.email}) a le rôle "
                        f"'{p.user.role}' au lieu de 'parent'."
                    ),
                })

        # --- Check 4 : ParentStudent → Student has user with wrong role -------
        for ps in ParentStudent.objects.select_related("student__user"):
            student = ps.student
            if student.user and student.user.role != "student":
                rows.append({
                    "type": "STUDENT_WRONG_ROLE",
                    "student_id": student.id,
                    "student_name": student.get_full_name(),
                    "parent_id": ps.parent_id,
                    "parent_name": "",
                    "detail": (
                        f"Élève#{student.id} a un compte utilisateur avec le rôle "
                        f"'{student.user.role}' au lieu de 'student'."
                    ),
                })

        # --- Write CSV -------------------------------------------------------
        output_path = options["output"]
        fieldnames = ["type", "student_id", "student_name", "parent_id", "parent_name", "detail"]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        count = len(rows)
        if count == 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Aucune incohérence détectée. Rapport vide écrit dans: {output_path}"
            ))
            sys.exit(0)
        else:
            self.stdout.write(self.style.ERROR(
                f"⚠️  {count} incohérence(s) détectée(s). Voir: {output_path}"
            ))
            sys.exit(1)
