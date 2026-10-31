"""
Comptes enseignant ou parent sans profil (créés par l'ancienne création
générique). Simulation par défaut ; --apply crée les profils manquants, vides.
Rien n'est modifié ni supprimé. Les élèves sans fiche sont seulement signalés :
leur fiche exige des données (classe, année) qu'on ne peut pas inventer.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Signale, et avec --apply crée, les profils enseignant et parent manquants."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        from apps.parents.models import Parent
        from apps.teachers.models import Teacher

        users = get_user_model().objects
        for role, relation, modele in (("teacher", "teacher_profile", Teacher), ("parent", "parent_profile", Parent)):
            for user in users.filter(role=role, **{f"{relation}__isnull": True}):
                if options["apply"]:
                    modele.objects.get_or_create(user=user)
                self.stdout.write(f"{role} #{user.pk} (académie {user.school_id}) : "
                                  f"{'profil créé' if options['apply'] else 'profil manquant'}")
        for user in users.filter(role="student", student_profile__isnull=True):
            self.stdout.write(f"student #{user.pk} (académie {user.school_id}) : fiche manquante, à traiter à la main")
