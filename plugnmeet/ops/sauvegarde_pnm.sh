#!/usr/bin/env bash
# Sauvegarde quotidienne de plugNmeet sur le serveur vidéo (minuteur systemd
# feba-pnm-sauvegarde.timer). Lecture seule sur les services.
#
#   /root/backups/pnm/<horodatage>/
#     plugnmeet.sql.gz      base MariaDB (salles, enregistrements, analyses)
#     runtime.tgz           configuration générée ET secrets (mode 600)
#     SHA256SUMS
#
# Vérification à chaque passage : restauration de la base dans un conteneur
# MariaDB jetable, sans réseau, puis comptage des tables. Rétention : 14.
# Le mot de passe passe par MYSQL_PWD (environnement), jamais en argument.
set -uo pipefail

PNM=/opt/feba/pnm/FEBA
DB=feba-pnm-pnm-db-1
IMG=mariadb:11.4.12@sha256:4f1d8d202fcf7bcb3902f63af09f9c1a050c2922a89652f22abaec0d4f015e83
RACINE=/root/backups/pnm
GARDER=14
TS=$(date -u +%Y%m%dT%H%M%SZ)
B=$RACINE/$TS
umask 077
install -d -m 700 "$B"

docker exec "$DB" sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" exec mariadb-dump -uroot --single-transaction --routines --databases "$MARIADB_DATABASE"' \
  | gzip -6 > "$B/plugnmeet.sql.gz" || { echo "ÉCHEC : export de la base"; exit 1; }
tar czf "$B/runtime.tgz" --exclude runtime/client -C "$PNM/plugnmeet" runtime || { echo "ÉCHEC : configuration"; exit 1; }
(cd "$B" && sha256sum plugnmeet.sql.gz runtime.tgz > SHA256SUMS)

# Restauration d'essai, isolée.
V=claude-pnm-verif-$TS
docker run -d --name "$V" --network none --memory 512m --pull never \
  -e MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1 "$IMG" >/dev/null || { echo "ÉCHEC : conteneur d'essai"; exit 1; }
pret=1
for _ in $(seq 1 60); do
  docker exec "$V" mariadb -uroot -e 'select 1' >/dev/null 2>&1 && { pret=0; break; }
  sleep 2
done
tables=0
if [ $pret -eq 0 ] && gunzip -c "$B/plugnmeet.sql.gz" | docker exec -i "$V" mariadb -uroot; then
  tables=$(docker exec "$V" mariadb -uroot -N -e "select count(*) from information_schema.tables where table_schema='plugnmeet'")
fi
docker rm -fv "$V" >/dev/null
[ "$tables" -ge 4 ] || { echo "ÉCHEC : restauration d'essai ($tables table(s))"; exit 1; }
echo "$tables" > "$B/tables_restaurees"

# Rétention : les GARDER plus récentes ; jamais d'autre dossier que $RACINE/<horodatage>.
ls -1d "$RACINE"/2*Z 2>/dev/null | sort | head -n -"$GARDER" | while read -r ancien; do rm -rf -- "$ancien"; done
echo "Sauvegarde plugNmeet VALIDE : $B ($(du -sh "$B" | cut -f1), $tables tables restaurées)"
