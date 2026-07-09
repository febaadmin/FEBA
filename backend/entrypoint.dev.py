#!/usr/bin/env python3
"""
FEBA v29 — entrypoint.dev.py

Ordonnance le démarrage du backend en développement :
  1. Attendre que PostgreSQL accepte les connexions
  2. `manage.py check` — vérifie la configuration Django (apps,
     modèles, URLs...) AVANT toute opération sur la base. Si quelque
     chose dans le code est cassé (import, modèle mal défini, conflit
     de related_name, etc.), c'est ICI que ça doit apparaître, avec un
     message clair, plutôt que de laisser `migrate` échouer avec une
     erreur moins lisible — ou pire, planter le conteneur sans qu'on
     sache pourquoi.
  3. `manage.py migrate` — applique les migrations.
  4. Démarre le serveur de développement.

À chaque étape qui peut échouer, le script affiche une bannière
explicite ET le code de sortie réel, pour qu'un simple
`docker compose logs backend-dev` (ou `make logs`) suffise à
comprendre immédiatement ce qui ne va pas.
"""
import os
import sys
import time
import subprocess


def banner(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


banner("FEBA Backend — Démarrage (dev)")

# ── 1. Attendre PostgreSQL ────────────────────────────────────────────────────
print("\n>>> [1/4] Attente de PostgreSQL...")
try:
    import dj_database_url
    import psycopg2

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERREUR FATALE: la variable d'environnement DATABASE_URL est vide ou absente.")
        print("Vérifiez que '.env.dev' est bien chargé (env_file: .env.dev dans docker-compose.yml).")
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
        print("\nVérifications possibles :")
        print("  - Le conteneur postgres-dev est-il bien démarré et 'healthy' ?")
        print("    -> docker compose ps")
        print("  - DATABASE_URL dans .env.dev pointe-t-il vers le bon hôte ('postgres-dev') ?")
        sys.exit(1)
except ImportError as e:
    print(f"    Avertissement : impossible de vérifier PostgreSQL ({e}) — on continue, migrate échouera si besoin.")

# ── 2. Vérification de la configuration Django (check) ──────────────────────
banner("[2/4] Vérification de la configuration Django (manage.py check)")
result = subprocess.run([sys.executable, "manage.py", "check"], capture_output=False)
if result.returncode != 0:
    banner("ERREUR FATALE — 'manage.py check' a échoué")
    print(f"Code de sortie : {result.returncode}")
    print(
        "\nLe message d'erreur Django ci-dessus (juste au-dessus de cette "
        "bannière) indique la cause précise : import cassé, modèle mal "
        "défini, conflit de related_name, erreur dans urls.py, etc."
    )
    print(
        "Ce conteneur va maintenant s'arrêter intentionnellement. Pour "
        "relire ce message plus tard : `docker compose logs backend-dev` "
        "ou `make logs`."
    )
    sys.exit(result.returncode)
print("    Configuration Django OK.")

# ── 3. Migrations ─────────────────────────────────────────────────────────────
banner("[3/4] Application des migrations (manage.py migrate)")
result = subprocess.run(
    [sys.executable, "manage.py", "migrate", "--no-input"],
    capture_output=False,
)
if result.returncode != 0:
    banner("ERREUR FATALE — 'manage.py migrate' a échoué")
    print(f"Code de sortie : {result.returncode}")
    print(
        "\nCauses fréquentes : conflit entre migrations, contrainte "
        "violée par des données existantes, base de données dans un "
        "état incohérent suite à un arrêt précédent en plein milieu "
        "d'une migration."
    )
    print(
        "Si le problème persiste après une nouvelle tentative, "
        "réinitialiser la base en dev (perte des données dev) :\n"
        "    docker compose down -v && docker compose up --build -d"
    )
    sys.exit(result.returncode)
print("    Migrations OK.")

# ── 4. Démarrer le serveur ────────────────────────────────────────────────────
banner("[4/4] Démarrage du serveur Django sur 0.0.0.0:8000")
os.execvp(sys.executable, [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"])
