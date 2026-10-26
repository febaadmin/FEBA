"""
Sauvegarde et restauration des fichiers : `media` ET `private_media`.

Défaut corrigé (audit des gabarits, 26/10/2026) : `scripts/backup_files.sh`
n'archivait que `/app/media`. Les diplômes et certificats délivrés, les
gabarits officiels téléversés, les dossiers FHA et les rapports mensuels
vivent dans `/app/private_media` : après un sinistre, ils étaient perdus.

Les scripts sont EXÉCUTÉS, pas relus : un faux `docker` placé en tête du
PATH exécute la commande destinée au conteneur sur un répertoire
temporaire qui joue le rôle de `/app`.
"""
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

SHIM = """#!/usr/bin/env bash
# Faux docker : « docker compose -f F exec -T SERVICE cmd… » → cmd… avec /app → $FAKE_APP
args=("$@")
for i in "${!args[@]}"; do
  if [ "${args[$i]}" = "-T" ]; then start=$((i + 2)); break; fi
done
cmd=()
for a in "${args[@]:$start}"; do cmd+=("${a//\\/app/$FAKE_APP}"); done
exec "${cmd[@]}"
"""


@unittest.skipUnless((SCRIPTS / "backup_files.sh").exists() and shutil.which("bash"),
                     "scripts de sauvegarde absents de cet environnement")
class BackupPrivateMediaTests(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="feba-backup-"))
        self.app = self.root / "app"
        (self.app / "media" / "photos").mkdir(parents=True)
        (self.app / "media" / "photos" / "eleve.jpg").write_bytes(b"photo")
        diploma = self.app / "private_media" / "academy_templates" / "3" / "diploma"
        diploma.mkdir(parents=True)
        (diploma / "a1b2.pdf").write_bytes(b"%PDF-gabarit")
        issued = self.app / "private_media" / "3" / "diploma_upload"
        issued.mkdir(parents=True)
        (issued / "7-20261026.pdf").write_bytes(b"%PDF-diplome-delivre")
        shim_dir = self.root / "bin"
        shim_dir.mkdir()
        (shim_dir / "docker").write_text(SHIM)
        (shim_dir / "docker").chmod(0o755)
        self.env = dict(os.environ, FAKE_APP=str(self.app),
                        PATH=f"{shim_dir}{os.pathsep}{os.environ['PATH']}")
        self.backups = self.root / "backups"

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_script(self, *args, stdin=""):
        return subprocess.run(["bash", *args], cwd=self.root, env=self.env, input=stdin,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def backup(self):
        result = self.run_script(str(SCRIPTS / "backup_files.sh"), str(self.backups))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        archives = sorted((self.backups / "daily").glob("feba_media_*.tar.gz"))
        self.assertEqual(len(archives), 1)
        return archives[0]

    def test_l_archive_contient_les_fichiers_prives(self):
        archive = self.backup()
        with tarfile.open(archive) as tar:
            names = tar.getnames()
        self.assertIn("media/photos/eleve.jpg", names)
        self.assertIn("private_media/academy_templates/3/diploma/a1b2.pdf", names)
        self.assertIn("private_media/3/diploma_upload/7-20261026.pdf", names)
        self.assertTrue(Path(f"{archive}.sha256").exists())

    def test_restauration_complete(self):
        archive = self.backup()
        shutil.rmtree(self.app / "private_media")
        (self.app / "media" / "photos" / "eleve.jpg").write_bytes(b"altere")
        result = self.run_script(str(SCRIPTS / "restore_backup.sh"), "media", str(archive),
                                 stdin="oui\n")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((self.app / "private_media" / "3" / "diploma_upload" / "7-20261026.pdf")
                         .read_bytes(), b"%PDF-diplome-delivre")
        self.assertEqual((self.app / "media" / "photos" / "eleve.jpg").read_bytes(), b"photo")

    def test_une_ancienne_archive_n_efface_pas_les_fichiers_prives(self):
        old = self.root / "feba_media_ancienne.tar.gz"
        with tarfile.open(old, "w:gz") as tar:
            tar.add(self.app / "media", arcname="media")
        result = self.run_script(str(SCRIPTS / "restore_backup.sh"), "media", str(old),
                                 stdin="oui\n")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("media", result.stdout)
        self.assertTrue((self.app / "private_media" / "academy_templates" / "3" / "diploma"
                         / "a1b2.pdf").exists())

    def test_installation_sans_fichier_prive(self):
        shutil.rmtree(self.app / "private_media")
        archive = self.backup()
        with tarfile.open(archive) as tar:
            names = tar.getnames()
        self.assertIn("media/photos/eleve.jpg", names)
        self.assertFalse(any(n.startswith("private_media") for n in names), names)


@unittest.skipUnless((SCRIPTS / "backup_database.sh").exists() and shutil.which("bash"),
                     "scripts de sauvegarde absents de cet environnement")
class BackupReachesOffsiteCopyTests(unittest.TestCase):
    """
    Défaut corrigé : avec `pipefail`, la rotation d'un dossier encore vide
    (hebdomadaire avant le premier dimanche, mensuel avant le 1er) faisait
    échouer le script AVANT la copie hors site. Un faux `rclone` prouve
    ici que la copie est atteinte dès la première nuit.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="feba-backup-db-"))
        shim_dir = self.root / "bin"
        shim_dir.mkdir()
        (shim_dir / "docker").write_text("#!/usr/bin/env bash\necho 'CREATE TABLE t();'\n")
        (shim_dir / "rclone").write_text(f"#!/usr/bin/env bash\necho \"$@\" >> {self.root}/rclone.log\n")
        for name in ("docker", "rclone"):
            (shim_dir / name).chmod(0o755)
        self.env = dict(os.environ, RCLONE_REMOTE="distant:feba",
                        PATH=f"{shim_dir}{os.pathsep}{os.environ['PATH']}")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_premiere_sauvegarde_de_la_base_copiee_hors_site(self):
        result = subprocess.run(["bash", str(SCRIPTS / "backup_database.sh"), str(self.root / "b")],
                                env=self.env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("copie distante", result.stdout)
        self.assertIn("distant:feba", (self.root / "rclone.log").read_text())
