#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# FEBA — Restauration (base et/ou médias) avec vérification checksum.
#
#   ./scripts/restore_backup.sh db    /backups/feba/daily/feba_db_2026-07-06.sql.gz
#   ./scripts/restore_backup.sh media /backups/feba/daily/feba_media_2026-07-06.tar.gz
#
# Procédure complète : docs/DISASTER_RECOVERY.md
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

KIND="${1:?Usage: restore_backup.sh <db|media> <archive>}"
ARCHIVE="${2:?Archive requise}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
# Mêmes noms que docker-compose.prod.yml et scripts/deploy_feba.sh. Les
# valeurs précédentes (« backend », « postgres », base « feba ») ne
# correspondaient à aucun service ni à aucune base de la composition de
# production : la tâche cron documentée échouait à chaque exécution.
ENV_FILE="${ENV_FILE:-.env.prod}"
PROJECT="${FEBA_PROJECT:-}"
dc() { docker compose ${PROJECT:+-p "$PROJECT"} $( [ -f "$ENV_FILE" ] && echo --env-file "$ENV_FILE" ) -f "$COMPOSE_FILE" "$@"; }
PG_SERVICE="${PG_SERVICE:-postgres-prod}"
PG_USER="${PG_USER:-feba_user}"
PG_DB="${PG_DB:-feba_prod}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend-prod}"

[ -f "$ARCHIVE" ] || { echo "✗ Archive introuvable : $ARCHIVE"; exit 1; }
if [ -f "$ARCHIVE.sha256" ]; then
    echo "Vérification checksum…"
    sha256sum -c "$ARCHIVE.sha256" || { echo "✗ Checksum invalide — archive corrompue."; exit 1; }
else
    echo "⚠ Pas de fichier .sha256 — poursuite sans vérification."
fi

read -r -p "⚠ RESTAURATION $KIND depuis $ARCHIVE — les données actuelles seront remplacées. Continuer ? (oui/non) " ANSWER
[ "$ANSWER" = "oui" ] || { echo "Annulé."; exit 0; }

case "$KIND" in
  db)
    echo "1/4 Arrêt des services applicatifs…"
    dc stop "$BACKEND_SERVICE" celery-prod celery-beat 2>/dev/null || true
    echo "2/4 Recréation de la base…"
    dc exec -T "$PG_SERVICE" \
        psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d postgres \
        -c "DROP DATABASE IF EXISTS $PG_DB WITH (FORCE);" \
        -c "CREATE DATABASE $PG_DB OWNER $PG_USER;"
    # Deux -c séparés : réunies dans une seule chaîne, les deux commandes
    # partaient en un bloc transactionnel, que PostgreSQL refuse pour
    # DROP DATABASE — et le script s'arrêtait en laissant le backend arrêté.
    echo "3/4 Import du dump…"
    gunzip -c "$ARCHIVE" | dc exec -T "$PG_SERVICE" \
        psql -U "$PG_USER" -d "$PG_DB" -q
    echo "4/4 Redémarrage…"
    dc start "$BACKEND_SERVICE" celery-prod celery-beat 2>/dev/null || \
        dc up -d
    echo "✔ Base restaurée. Vérifiez /api/health/ puis un parcours de connexion."
    ;;
  media)
    # Seuls les répertoires PRÉSENTS dans l'archive sont remplacés : une
    # archive antérieure (médias seuls) ne doit pas effacer les fichiers
    # privés — diplômes délivrés, gabarits — qu'elle ne contient pas.
    DIRS=$(tar tzf "$ARCHIVE" | cut -d/ -f1 | sort -u | grep -Ex 'media|private_media' | tr '\n' ' ')
    [ -n "$DIRS" ] || { echo "✗ Archive sans répertoire media/ ni private_media/"; exit 1; }
    echo "Restauration de : $DIRS"
    cat "$ARCHIVE" | dc exec -T "$BACKEND_SERVICE" \
        sh -c "cd /app && for d in $DIRS; do mkdir -p \$d && find \$d -mindepth 1 -delete; done && tar xzf - -C /app"
    # On VIDE les répertoires sans les supprimer : en production ce sont des
    # points de montage de volumes, que « rm -rf » ne peut pas retirer
    # (« Device or resource busy ») — la restauration échouait.
    echo "✔ Fichiers restaurés ($DIRS)."
    ;;
  *) echo "✗ Type inconnu : $KIND (db|media)"; exit 1 ;;
esac
