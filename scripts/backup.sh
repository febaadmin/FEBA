#!/bin/bash
# Backup PostgreSQL quotidien
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/feba/backups"
CONTAINER="feba_postgres_prod"
DB_NAME="feba_prod"
DB_USER="feba_user"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

echo "[$DATE] Démarrage du backup..."
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_DIR/feba_${DATE}.sql.gz"

if [ $? -eq 0 ]; then
    echo "[$DATE] Backup réussi : feba_${DATE}.sql.gz"
else
    echo "[$DATE] ERREUR: Backup échoué!" >&2
    exit 1
fi

# Nettoyage des vieux backups
find "$BACKUP_DIR" -name "feba_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "[$DATE] Backups de plus de $RETENTION_DAYS jours supprimés."