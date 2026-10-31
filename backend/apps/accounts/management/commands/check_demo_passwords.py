"""
Comptes qui acceptent encore un mot de passe de démonstration (publics dans le
dépôt). N'affiche jamais de mot de passe. Code de sortie 1 s'il en reste.
"""
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

MOTS_DE_PASSE = ("SuperAdmin@2024", "Admin@2024", "Teacher@2024", "Parent@2024", "Student@2024")


class Command(BaseCommand):
    help = "Signale les comptes actifs dont le mot de passe est un mot de passe de démonstration."

    def handle(self, *args, **options):
        exposes = [u.pk for u in get_user_model().objects.filter(is_active=True, email__iregex=r"@(feba\.bj|febafha\.org)$")
                   if any(u.check_password(m) for m in MOTS_DE_PASSE)]
        self.stdout.write(f"Comptes exposés : {exposes or 'aucun'}")
        if exposes:
            sys.exit(1)
