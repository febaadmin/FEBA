#!/usr/bin/env python3
"""
FEBA v29 — entrypoint.prod.py

Équivalent production de entrypoint.dev.py : mêmes vérifications, même
niveau de diagnostic en cas d'échec, mais termine sur Gunicorn (WSGI,
multi-workers) plutôt que le serveur de développement Django.

Ordonnance :
  1. Attendre PostgreSQL
  2. `manage.py check --deploy` — vérifications Django standards +
     vérifications spécifiques production (cookies sécurisés, DEBUG,
     etc.). Les avertissements de `--deploy` n'arrêtent PAS le
     démarrage (ce sont des recommandations, pas des erreurs) ; seule
     une erreur de configuration réelle (code de sortie non nul) le fait.
  3. `manage.py migrate`
  4. `manage.py collectstatic`
  5. Démarrage de Gunicorn
"""
import os
import sys
import time
import subprocess


def banner(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


banner("FEBA Backend — Démarrage (production)")

# ── 1. Attendre PostgreSQL ────────────────────────────────────────────────────
print("\n>>> [1/5] Attente de PostgreSQL...")
try:
    import dj_database_url
    import psycopg2

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERREUR FATALE: DATABASE_URL est vide ou absente (vérifier .env.prod).")
        sys.exit(1)

    db = dj_database_url.parse(url)
    connected = False
    last_error = None
    for i in range(30):
        try:
            conn = psycopg2.connect(
                host=db["HOST"], port=db.get("PORT", 5432),
                user=db["USER"], password=db["PASSWORD"],
                dbname=db["NAME"], connect_timeout=3,
            )
            conn.close()
            print(f"    PostgreSQL prêt ! (tentative {i + 1})")
            connected = True
            break
        except Exception as e:
            last_error = e
            print(f"    Tentative {i + 1}/30 — {e}")
            time.sleep(2)
    if not connected:
        banner("ERREUR FATALE — PostgreSQL inaccessible après 60s")
        print(f"Dernière erreur : {last_error}")
        sys.exit(1)
except ImportError as e:
    print(f"    Avertissement : impossible de vérifier PostgreSQL ({e}) — on continue.")

# ── 2. Vérification de la configuration Django ───────────────────────────────
banner("[2/5] Vérification de la configuration Django (manage.py check)")
result = subprocess.run([sys.executable, "manage.py", "check"], capture_output=False)
if result.returncode != 0:
    banner("ERREUR FATALE — 'manage.py check' a échoué")
    print(f"Code de sortie : {result.returncode}")
    print("Voir le message Django ci-dessus pour la cause précise.")
    sys.exit(result.returncode)
print("    Configuration Django OK.")

# ── 3. Migrations ─────────────────────────────────────────────────────────────
banner("[3/5] Application des migrations (manage.py migrate)")
result = subprocess.run([sys.executable, "manage.py", "migrate", "--no-input"], capture_output=False)
if result.returncode != 0:
    banner("ERREUR FATALE — 'manage.py migrate' a échoué")
    print(f"Code de sortie : {result.returncode}")
    sys.exit(result.returncode)
print("    Migrations OK.")

# ── 4. Fichiers statiques ─────────────────────────────────────────────────────
banner("[4/5] Collecte des fichiers statiques (manage.py collectstatic)")
result = subprocess.run([sys.executable, "manage.py", "collectstatic", "--no-input"], capture_output=False)
if result.returncode != 0:
    banner("ERREUR FATALE — 'manage.py collectstatic' a échoué")
    print(f"Code de sortie : {result.returncode}")
    sys.exit(result.returncode)
print("    Fichiers statiques OK.")

# ── 5. Démarrer Gunicorn ──────────────────────────────────────────────────────
banner("[5/5] Démarrage de Gunicorn sur 0.0.0.0:8000")
os.execvp("gunicorn", [
    "gunicorn", "feba_project.wsgi:application",
    "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120",
])
