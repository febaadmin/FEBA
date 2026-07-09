#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# FEBA — Sauvegarde PostgreSQL avec rotation 7 quotidiennes / 4 hebdo /
# 12 mensuelles + checksum + copie distante optionnelle (rclone).
#
# Usage (depuis la racine du projet, cron recommandé à 02h00) :
#   ./scripts/backup_database.sh [dossier_sauvegardes]
# Cron :
#   0 2 * * * cd /opt/feba && ./scripts/backup_database.sh /backups/feba >> /var/log/feba-backup.log 2>&1
# Copie distante (S3/NAS…) : définir RCLONE_REMOTE (ex: "s3feba:feba-backups")
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

BACKUP_ROOT="${1:-./backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
PG_SERVICE="${PG_SERVICE:-postgres}"
PG_USER="${PG_USER:-feba}"
PG_DB="${PG_DB:-feba}"
STAMP=$(date +%F)
DOW=$(date +%u)    # 1..7 (7 = dimanche)
DOM=$(date +%d)    # jour du mois

mkdir -p "$BACKUP_ROOT"/{daily,weekly,monthly}

echo "[$(date '+%F %T')] Sauvegarde base $PG_DB…"
DUMP="$BACKUP_ROOT/daily/feba_db_${STAMP}.sql.gz"
docker compose -f "$COMPOSE_FILE" exec -T "$PG_SERVICE" \
    pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$DUMP"

sha256sum "$DUMP" > "$DUMP.sha256"
echo "  ✔ $DUMP ($(du -h "$DUMP" | cut -f1)) + checksum"

# Promotion hebdomadaire (dimanche) et mensuelle (1er du mois)
[ "$DOW" = "7" ]  && cp "$DUMP" "$BACKUP_ROOT/weekly/"  && cp "$DUMP.sha256" "$BACKUP_ROOT/weekly/"
[ "$DOM" = "01" ] && cp "$DUMP" "$BACKUP_ROOT/monthly/" && cp "$DUMP.sha256" "$BACKUP_ROOT/monthly/"

# Rotation : 7 quotidiennes, 4 hebdomadaires, 12 mensuelles
ls -1t "$BACKUP_ROOT"/daily/feba_db_*.sql.gz   2>/dev/null | tail -n +8  | xargs -r -I{} rm -f {} {}.sha256
ls -1t "$BACKUP_ROOT"/weekly/feba_db_*.sql.gz  2>/dev/null | tail -n +5  | xargs -r -I{} rm -f {} {}.sha256
ls -1t "$BACKUP_ROOT"/monthly/feba_db_*.sql.gz 2>/dev/null | tail -n +13 | xargs -r -I{} rm -f {} {}.sha256

# Copie distante (jamais uniquement sur le serveur principal)
if [ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null; then
    rclone copy "$BACKUP_ROOT" "$RCLONE_REMOTE" --include "feba_db_${STAMP}*"
    echo "  ✔ copie distante → $RCLONE_REMOTE"
else
    echo "  ⚠ RCLONE_REMOTE non défini : pensez à une copie hors site (S3/NAS)."
fi

echo "[$(date '+%F %T')] Sauvegarde base terminée."
