#!/usr/bin/env bash
# FEBA — Sauvegarde de la pile Jitsi auto-hébergée : configuration des
# 4 services (web, prosody — comptes & JWT —, jicofo, jvb) + .env.jitsi.
# Cron : 30 2 * * 0 cd /opt/feba && ./scripts/backup_jitsi.sh /backups/feba
set -euo pipefail

BACKUP_ROOT="${1:-./backups}"
STAMP=$(date +%F)
mkdir -p "$BACKUP_ROOT/jitsi"
ARCHIVE="$BACKUP_ROOT/jitsi/feba_jitsi_${STAMP}.tar.gz"

echo "[$(date '+%F %T')] Sauvegarde configuration Jitsi…"
TMP=$(mktemp -d)
for vol in jitsi-web-config jitsi-prosody-config jitsi-jicofo-config jitsi-jvb-config; do
    full=$(docker volume ls -q | grep -E "${vol}$" | head -1 || true)
    if [ -n "$full" ]; then
        mkdir -p "$TMP/$vol"
        docker run --rm -v "$full":/src -v "$TMP/$vol":/dst alpine sh -c "cp -a /src/. /dst/"
    fi
done
[ -f .env.jitsi ] && cp .env.jitsi "$TMP/env.jitsi"
tar czf "$ARCHIVE" -C "$TMP" .
rm -rf "$TMP"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"

ls -1t "$BACKUP_ROOT"/jitsi/feba_jitsi_*.tar.gz 2>/dev/null | tail -n +9 | xargs -r -I{} rm -f {} {}.sha256
[ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null && \
    rclone copy "$BACKUP_ROOT/jitsi" "$RCLONE_REMOTE/jitsi" --include "feba_jitsi_${STAMP}*"
echo "  ✔ $ARCHIVE"
