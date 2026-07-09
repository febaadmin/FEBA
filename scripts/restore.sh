#!/bin/bash
# Restaurer un backup PostgreSQL
BACKUP_FILE="$1"
CONTAINER="feba_postgres_prod"
DB_NAME="feba_prod"
DB_USER="feba_user"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

echo "⚠️  ATTENTION: Cette opération va écraser la base de données actuelle!"
read -p "Continuer? (oui/non): " confirm
if [ "$confirm" != "oui" ]; then
    echo "Annulé."
    exit 0
fi

echo "Restauration de $BACKUP_FILE..."
gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"

if [ $? -eq 0 ]; then
    echo "✅ Restauration réussie!"
else
    echo "❌ Erreur lors de la restauration!" >&2
    exit 1
fi