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
PG_SERVICE="${PG_SERVICE:-postgres}"
PG_USER="${PG_USER:-feba}"
PG_DB="${PG_DB:-feba}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"

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
    docker compose -f "$COMPOSE_FILE" stop backend celery celery-beat 2>/dev/null || true
    echo "2/4 Recréation de la base…"
    docker compose -f "$COMPOSE_FILE" exec -T "$PG_SERVICE" \
        psql -U "$PG_USER" -d postgres -c "DROP DATABASE IF EXISTS $PG_DB; CREATE DATABASE $PG_DB OWNER $PG_USER;"
    echo "3/4 Import du dump…"
    gunzip -c "$ARCHIVE" | docker compose -f "$COMPOSE_FILE" exec -T "$PG_SERVICE" \
        psql -U "$PG_USER" -d "$PG_DB" -q
    echo "4/4 Redémarrage…"
    docker compose -f "$COMPOSE_FILE" start backend celery celery-beat 2>/dev/null || \
        docker compose -f "$COMPOSE_FILE" up -d
    echo "✔ Base restaurée. Vérifiez /api/health/ puis un parcours de connexion."
    ;;
  media)
    echo "Restauration des médias…"
    cat "$ARCHIVE" | docker compose -f "$COMPOSE_FILE" exec -T "$BACKEND_SERVICE" \
        sh -c "rm -rf /app/media && tar xzf - -C /app"
    echo "✔ Médias restaurés."
    ;;
  *) echo "✗ Type inconnu : $KIND (db|media)"; exit 1 ;;
esac
