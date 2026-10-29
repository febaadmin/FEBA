"""
La racine du dépôt doit être atteignable depuis les tests, partout.

CE QUE CE FICHIER VERROUILLE
----------------------------
Plusieurs tests vérifient des FICHIERS DE LIVRAISON situés au-dessus de
`backend/`. Dans le conteneur de développement, seul `./backend` était
monté : ces fichiers étaient invisibles. Deux tests échouaient
franchement, six s'ignoraient en silence — et un « skipped » se lit
comme un succès dans un tableau de résultats.

Le correctif tient en deux pièces qui ne valent que EnsEMBLE :
  * `tests/repo_root.py`, résolution unique et bruyante ;
  * le montage `.:/repo:ro` du service `backend-dev`.

Ce fichier vérifie les deux, et refuse le retour du silence.
"""
import os
import subprocess
import sys
import textwrap

from django.test import SimpleTestCase

from tests.repo_root import (
    CONTAINER_MOUNT, ENV_VAR, MARKERS, find_repo_root, parse_env_file,
    read_repo_file, repo_file, repo_root,
)


class ResolutionDeLaRacineTests(SimpleTestCase):

    def test_la_racine_est_trouvee_dans_cet_environnement(self):
        racine = repo_root()
        for marqueur in MARKERS:
            with self.subTest(marqueur=str(marqueur)):
                self.assertTrue((racine / marqueur).exists())

    def test_les_fichiers_de_livraison_attendus_sont_atteignables(self):
        # La liste exacte des fichiers que les autres tests consultent.
        # Si l'un devient invisible, l'échec est ici, une seule fois, avec
        # un message clair — plutôt que dispersé en cinq symptômes.
        attendus = (
            "Makefile",
            "docker-compose.yml",
            "docker-compose.prod.yml",
            "docker-compose.jitsi.yml",
            "docker-compose.jitsi.prod.yml",
            ".env.example",
            ".env.dev.example",
            ".env.prod.example",
            ".env.jitsi.example",
            "KNOWN_LIMITATIONS.md",
            "scripts/jitsi_up.sh",
            "scripts/jitsi_config_check.sh",
            "nginx/nginx.prod.conf",
            "frontend/nginx.prod.conf",
        )
        manquants = [nom for nom in attendus if not repo_file(nom).exists()]
        self.assertEqual(
            manquants, [],
            f"Fichiers de livraison introuvables depuis {repo_root()} : "
            f"{manquants}")

    def test_la_variable_d_environnement_est_honoree(self):
        racine = str(repo_root())
        with self.settings():  # no-op : on isole seulement l'environnement
            ancien = os.environ.get(ENV_VAR)
            os.environ[ENV_VAR] = racine
            try:
                self.assertEqual(str(find_repo_root()), racine)
            finally:
                if ancien is None:
                    os.environ.pop(ENV_VAR, None)
                else:
                    os.environ[ENV_VAR] = ancien

    def test_une_variable_erronee_ne_masque_pas_les_autres_chemins(self):
        """
        Un `FEBA_REPO_ROOT` qui pointe ailleurs ne doit pas faire échouer
        la résolution : les deux autres chemins prennent le relais.

        Le troisième chemin (le montage du conteneur) est visé
        explicitement, sans supposer qu'une remontée d'arborescence
        aboutira. Dans le conteneur, elle n'aboutit justement pas : `/app`
        est `backend/`, et `/` ne porte aucun marqueur. C'est précisément
        pour cela que le montage existe.
        """
        import tests.repo_root as rr

        racine = str(repo_root())
        ancien_env = os.environ.get(ENV_VAR)
        ancien_mount = rr.CONTAINER_MOUNT
        os.environ[ENV_VAR] = "/chemin/qui/n/existe/pas"
        rr.CONTAINER_MOUNT = racine
        try:
            self.assertEqual(str(rr.find_repo_root()), racine)
        finally:
            rr.CONTAINER_MOUNT = ancien_mount
            if ancien_env is None:
                os.environ.pop(ENV_VAR, None)
            else:
                os.environ[ENV_VAR] = ancien_env

    def test_la_racine_introuvable_leve_au_lieu_de_se_taire(self):
        """
        LE POINT CENTRAL DE CE FICHIER.

        On exécute le module dans un interpréteur neuf, depuis une
        arborescence qui ne porte AUCUN marqueur et sans variable
        d'environnement — la situation qui produisait « skipped ». Le
        résultat attendu est une exception, pas un silence.
        """
        programme = textwrap.dedent(f"""
            import os, sys
            sys.path.insert(0, {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))!r})
            os.environ.pop({ENV_VAR!r}, None)
            import tests.repo_root as rr
            # Neutralise les trois chemins de résolution.
            rr.MARKERS = (__import__("pathlib").Path("marqueur-absent"),)
            rr.CONTAINER_MOUNT = "/chemin/de/montage/absent"
            try:
                rr.repo_root()
            except AssertionError as exc:
                print("LEVEE")
                assert "docker-compose.yml" in str(exc), "message peu actionnable"
                sys.exit(0)
            print("SILENCE")
            sys.exit(1)
        """)
        resultat = subprocess.run(
            [sys.executable, "-c", programme],
            capture_output=True, text=True,
        )
        self.assertEqual(
            resultat.returncode, 0,
            "Racine introuvable : le module doit LEVER, pas retourner un "
            f"chemin bancal.\nsortie: {resultat.stdout}\n{resultat.stderr}")
        self.assertIn("LEVEE", resultat.stdout)


class MontageDuConteneurTests(SimpleTestCase):
    """
    Le service `backend-dev` doit monter le dépôt.

    Sans ce montage, la résolution ci-dessus ne peut rien : c'est la
    moitié infrastructure du correctif, et elle se perd d'un simple
    « nettoyage » de docker-compose.yml.
    """

    def _service_backend_dev(self):
        import yaml
        return yaml.safe_load(read_repo_file("docker-compose.yml"))["services"]["backend-dev"]

    def test_le_depot_est_monte_en_lecture_seule(self):
        volumes = self._service_backend_dev().get("volumes") or []
        attendu = f".:{CONTAINER_MOUNT}:ro"
        self.assertIn(
            attendu, volumes,
            "Le service backend-dev ne monte plus la racine du dépôt. "
            "Les tests de configuration redeviendraient invisibles — et "
            "silencieux. Volumes actuels : " + repr(volumes))

    def test_le_montage_est_bien_en_lecture_seule(self):
        # Le conteneur ne doit pas pouvoir modifier le dépôt de l'hôte.
        volumes = self._service_backend_dev().get("volumes") or []
        montages = [v for v in volumes if v.split(":")[1:2] == [CONTAINER_MOUNT]]
        self.assertTrue(montages, "aucun montage sur " + CONTAINER_MOUNT)
        for montage in montages:
            with self.subTest(montage=montage):
                self.assertTrue(montage.endswith(":ro"), montage)

    def test_la_variable_est_transmise_au_conteneur(self):
        env = self._service_backend_dev().get("environment") or {}
        if isinstance(env, list):
            env = dict(e.split("=", 1) for e in env if "=" in e)
        self.assertEqual(env.get(ENV_VAR), CONTAINER_MOUNT)

    def test_aucun_montage_fichier_par_fichier_ne_subsiste(self):
        """
        La liste nommée était le défaut, pas la solution.

        Monter KNOWN_LIMITATIONS.md seul avait l'air de marcher et
        laissait six autres fichiers invisibles. Le dépôt entier est monté
        une fois ; on refuse le retour des montages ponctuels, qui
        redonneraient une liste à tenir à jour à chaque nouveau test.
        """
        volumes = self._service_backend_dev().get("volumes") or []
        ponctuels = [
            v for v in volumes
            if v.startswith("./") and v.split(":")[0].endswith(
                (".md", ".yml", ".yaml", ".example", ".conf", ".txt"))
        ]
        self.assertEqual(
            ponctuels, [],
            f"Montages fichier par fichier réapparus : {ponctuels}. "
            f"Le montage « .:{CONTAINER_MOUNT}:ro » les rend inutiles.")


class AucunSilenceDansLesTestsDeConfigurationTests(SimpleTestCase):
    """
    Aucun test de configuration ne doit s'ignorer faute de trouver un
    fichier. C'est la règle qui a été enfreinte, et elle se réintroduit
    d'une seule ligne.
    """

    FICHIERS = (
        "test_env_dev_email_config.py",
        "test_jitsi_production_domain.py",
        "test_production_settings.py",
    )

    def test_aucun_skip_conditionne_a_l_existence_d_un_fichier(self):
        import re

        coupables = []
        dossier = os.path.dirname(os.path.abspath(__file__))
        motifs = (
            re.compile(r"skipTest\([^)]*introuvable", re.I),
            re.compile(r"skipUnless\(\s*os\.path\.exists"),
            re.compile(r"skipIf\(\s*not\s+os\.path\.exists"),
        )
        for nom in self.FICHIERS:
            contenu = open(os.path.join(dossier, nom), encoding="utf-8").read()
            for motif in motifs:
                if motif.search(contenu):
                    coupables.append(f"{nom} → {motif.pattern}")
        self.assertEqual(
            coupables, [],
            "Un test de configuration s'ignore quand un fichier manque : "
            f"{coupables}. Un fichier de livraison invisible est un DÉFAUT "
            "à corriger, pas une condition d'exécution — voir "
            "tests/repo_root.py.")


class MailpitEstReellementConfigureTests(SimpleTestCase):
    """
    Le service que `.env.dev.example` désigne doit exister pour de bon.

    Les tests de `test_env_dev_email_config.py` vérifient le gabarit ;
    celui-ci ferme la boucle côté infrastructure.
    """

    def test_le_gabarit_pointe_le_service_mailpit(self):
        valeurs = parse_env_file(".env.dev.example")
        self.assertEqual(valeurs.get("EMAIL_BACKEND"),
                         "django.core.mail.backends.smtp.EmailBackend")
        self.assertEqual(valeurs.get("EMAIL_HOST"), "mailpit")
        self.assertEqual(valeurs.get("EMAIL_PORT"), "1025")

    def test_le_service_mailpit_existe_et_expose_le_port_smtp(self):
        import yaml

        compose = yaml.safe_load(read_repo_file("docker-compose.yml"))
        self.assertIn("mailpit", compose["services"])
        mailpit = compose["services"]["mailpit"]
        ports = [str(p) for p in (mailpit.get("ports") or [])]
        self.assertTrue(
            any(p.split(":")[-1] == "1025" for p in ports),
            f"Le port SMTP 1025 n'est pas exposé par mailpit : {ports}")
        self.assertTrue(
            any(p.split(":")[-1] == "8025" for p in ports),
            f"L'interface Mailpit (8025) n'est pas exposée : {ports}")

    def test_le_backend_attend_mailpit_avant_de_demarrer(self):
        import yaml

        compose = yaml.safe_load(read_repo_file("docker-compose.yml"))
        depends = compose["services"]["backend-dev"].get("depends_on") or {}
        self.assertIn(
            "mailpit", depends,
            "backend-dev ne dépend pas de mailpit : un envoi lancé au "
            "démarrage échouerait sur un service pas encore prêt.")
