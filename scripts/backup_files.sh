#!/usr/bin/env bash
# FEBA — Sauvegarde des fichiers (photos, documents, bulletins,
# justificatifs, reçus) avec rotation 7/4/12 et checksum.
#
# DEUX RÉPERTOIRES, PAS UN
# ------------------------
# `/app/media` (public) ET `/app/private_media` (volume privé : diplômes et
# certificats délivrés, gabarits officiels téléversés par les académies,
# dossiers FHA, rapports mensuels, pièces jointes). Seul le premier était
# archivé : une restauration après sinistre aurait rendu une application
# sans aucun document officiel délivré ni gabarit.
# Cron : 15 2 * * * cd /opt/feba && ./scripts/backup_files.sh /backups/feba
set -euo pipefail

BACKUP_ROOT="${1:-./backups}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
# Mêmes noms que docker-compose.prod.yml et scripts/deploy_feba.sh. Les
# valeurs précédentes (« backend », « postgres », base « feba ») ne
# correspondaient à aucun service ni à aucune base de la composition de
# production : la tâche cron documentée échouait à chaque exécution.
ENV_FILE="${ENV_FILE:-.env.prod}"
PROJECT="${FEBA_PROJECT:-}"
dc() { docker compose ${PROJECT:+-p "$PROJECT"} $( [ -f "$ENV_FILE" ] && echo --env-file "$ENV_FILE" ) -f "$COMPOSE_FILE" "$@"; }
BACKEND_SERVICE="${BACKEND_SERVICE:-backend-prod}"
STAMP=$(date +%F)
DOW=$(date +%u); DOM=$(date +%d)

mkdir -p "$BACKUP_ROOT"/{daily,weekly,monthly}
ARCHIVE="$BACKUP_ROOT/daily/feba_media_${STAMP}.tar.gz"

echo "[$(date '+%F %T')] Sauvegarde médias et fichiers privés…"
# `private_media` n'est ajouté que s'il existe : une installation qui n'a
# encore produit aucun fichier privé reste sauvegardable.
dc exec -T "$BACKEND_SERVICE" \
    sh -c 'cd /app && if [ -d private_media ]; then tar czf - media private_media; else tar czf - media; fi' \
    | cat > "$ARCHIVE"
# Une archive vide ou tronquée ne doit pas passer pour une sauvegarde :
# elle est relue entièrement avant d'être déclarée réussie.
tar tzf "$ARCHIVE" > /dev/null
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
echo "  ✔ $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

[ "$DOW" = "7" ]  && cp "$ARCHIVE" "$ARCHIVE.sha256" "$BACKUP_ROOT/weekly/" 2>/dev/null || true
[ "$DOM" = "01" ] && cp "$ARCHIVE" "$ARCHIVE.sha256" "$BACKUP_ROOT/monthly/" 2>/dev/null || true

# `|| true` : avec `pipefail`, un dossier encore vide (aucune archive
# hebdomadaire avant le premier dimanche, aucune mensuelle avant le 1er)
# faisait échouer `ls`, et le script s'arrêtait AVANT la copie hors site.
ls -1t "$BACKUP_ROOT"/daily/feba_media_*.tar.gz   2>/dev/null | tail -n +8  | xargs -r -I{} rm -f {} {}.sha256 || true
ls -1t "$BACKUP_ROOT"/weekly/feba_media_*.tar.gz  2>/dev/null | tail -n +5  | xargs -r -I{} rm -f {} {}.sha256 || true
ls -1t "$BACKUP_ROOT"/monthly/feba_media_*.tar.gz 2>/dev/null | tail -n +13 | xargs -r -I{} rm -f {} {}.sha256 || true

if [ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null; then
    rclone copy "$BACKUP_ROOT" "$RCLONE_REMOTE" --include "feba_media_${STAMP}*"
fi
echo "[$(date '+%F %T')] Sauvegarde médias terminée."
