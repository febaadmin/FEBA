#!/usr/bin/env bash
# FEBA — Sauvegarde des fichiers médias (photos, documents, bulletins,
# justificatifs, reçus) avec rotation 7/4/12 et checksum.
# Cron : 15 2 * * * cd /opt/feba && ./scripts/backup_files.sh /backups/feba
set -euo pipefail

BACKUP_ROOT="${1:-./backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
STAMP=$(date +%F)
DOW=$(date +%u); DOM=$(date +%d)

mkdir -p "$BACKUP_ROOT"/{daily,weekly,monthly}
ARCHIVE="$BACKUP_ROOT/daily/feba_media_${STAMP}.tar.gz"

echo "[$(date '+%F %T')] Sauvegarde médias…"
docker compose -f "$COMPOSE_FILE" exec -T "$BACKEND_SERVICE" \
    tar czf - -C /app media | cat > "$ARCHIVE"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
echo "  ✔ $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

[ "$DOW" = "7" ]  && cp "$ARCHIVE" "$ARCHIVE.sha256" "$BACKUP_ROOT/weekly/" 2>/dev/null || true
[ "$DOM" = "01" ] && cp "$ARCHIVE" "$ARCHIVE.sha256" "$BACKUP_ROOT/monthly/" 2>/dev/null || true

ls -1t "$BACKUP_ROOT"/daily/feba_media_*.tar.gz   2>/dev/null | tail -n +8  | xargs -r -I{} rm -f {} {}.sha256
ls -1t "$BACKUP_ROOT"/weekly/feba_media_*.tar.gz  2>/dev/null | tail -n +5  | xargs -r -I{} rm -f {} {}.sha256
ls -1t "$BACKUP_ROOT"/monthly/feba_media_*.tar.gz 2>/dev/null | tail -n +13 | xargs -r -I{} rm -f {} {}.sha256

if [ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null; then
    rclone copy "$BACKUP_ROOT" "$RCLONE_REMOTE" --include "feba_media_${STAMP}*"
fi
echo "[$(date '+%F %T')] Sauvegarde médias terminée."
