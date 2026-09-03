"""
tests/test_env_dev_email_config.py — Régression P4 (juillet 2026).

BUG RÉSOLU
----------
Le bouton « Envoyer » du rapport mensuel échouait systématiquement avec
« Message capturé localement par le backend
django.core.mail.backends.console.EmailBackend : aucun fournisseur
externe ne l'a accepté ».

Ce message n'était PAS un bug de logique (`apps/monthly_reports/emails.py`
distingue correctement « accepté » de « réellement envoyé », et cette
distinction est déjà couverte par `tests/test_monthly_reports.py ::
TestEnvoi`). Le vrai problème : Mailpit tourne comme service Docker
dédié à cet usage, mais `.env.dev.example` — le gabarit que
`scripts/bootstrap.sh` copie vers `.env.dev`, le fichier que
`docker-compose.yml` charge réellement — pointait vers le backend
console au lieu de Mailpit. Une installation neuve ne pouvait donc
JAMAIS envoyer un rapport, alors que l'infrastructure pour le faire
était déjà en place et en bonne santé.

Ce test ne vérifie pas du code applicatif : il verrouille un fichier de
configuration contre une régression silencieuse (quelqu'un qui reviendrait
au backend console sans s'en rendre compte).
"""
from django.test import SimpleTestCase

from tests.repo_root import parse_env_file, read_repo_file


class EnvDevExampleMailpitDefaultTests(SimpleTestCase):
    """
    .env.dev.example doit pointer vers Mailpit par défaut.

    CES TESTS NE S'IGNORENT PLUS.

    Ils appelaient `skipTest` quand `.env.dev.example` n'était pas
    visible — ce qui était TOUJOURS le cas dans le conteneur, où seul
    `./backend` est monté. `pytest` y affichait « 4 skipped » : vert dans
    un tableau de résultats, alors qu'aucune des trois valeurs n'avait
    été vérifiée. Un retour au backend console serait passé inaperçu,
    c'est-à-dire exactement le défaut que ce fichier surveille.

    La racine est désormais résolue par `tests/repo_root.py`, qui la
    trouve dans le conteneur comme hors conteneur, et qui ÉCHOUE bruyamment
    si elle est vraiment introuvable.
    """

    def setUp(self):
        self.values = parse_env_file(".env.dev.example")

    def test_email_backend_est_smtp_pas_console(self):
        self.assertEqual(
            self.values.get("EMAIL_BACKEND"),
            "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_BACKEND doit pointer vers SMTP (Mailpit), pas vers le "
            "backend console — sinon tout envoi échoue par conception dès "
            "l'installation, alors que Mailpit tourne déjà pour ça.",
        )

    def test_email_host_est_mailpit(self):
        self.assertEqual(self.values.get("EMAIL_HOST"), "mailpit")

    def test_email_port_est_le_port_smtp_de_mailpit(self):
        self.assertEqual(self.values.get("EMAIL_PORT"), "1025")

    def test_docker_compose_expose_bien_un_service_mailpit(self):
        """Vérifie que la cible existe réellement — pas un nom en l'air."""
        compose = read_repo_file("docker-compose.yml")
        self.assertIn("mailpit:", compose)
        self.assertIn('"1025:1025"', compose)
