#!/usr/bin/env bash
# Test de restauration FEBA dans un PostgreSQL jetable, sans réseau.
# À lancer une fois, en root, sur le serveur FEBA. Procédure : docs/RESTAURATION_ISOLEE.md
#
# Ne touche jamais à la production : la base de production n'est lue que par
# des SELECT count(*). Tout ce qui est créé (dossier, conteneur) porte le nom
# feba-restauration-* et est supprimé à la fin. N'affiche aucun secret.
set -euo pipefail

SOURCE_ENV="${SOURCE_ENV:-/opt/feba/scripts/backup-local-restic.sh}"
PROD_PG="${PROD_PG:-feba_postgres_prod}"
PROD_MEDIA="${PROD_MEDIA:-feba_backend_prod:/app/media}"
JETON="$(date -u +%Y%m%dT%H%M%SZ)"
DOSSIER="/var/tmp/feba-restauration-$JETON"
CONTENEUR="feba-restauration-$JETON"
RAPPORT="/root/feba-restauration-$JETON.txt"

nettoyer() {
  docker rm -f "$CONTENEUR" >/dev/null 2>&1 || true
  rm -rf "$DOSSIER"
}
trap nettoyer EXIT
[ "$(id -u)" = 0 ] || { echo "À lancer en root."; exit 2; }

# Le dépôt et le mot de passe sont ceux du script de sauvegarde, sans être affichés.
eval "$(grep -E '^(export +)?RESTIC_(REPOSITORY|PASSWORD_FILE|REPOSITORY_FILE|PASSWORD_COMMAND)=' "$SOURCE_ENV" || true)"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE RESTIC_REPOSITORY_FILE RESTIC_PASSWORD_COMMAND 2>/dev/null || true
[ -n "${RESTIC_REPOSITORY:-}${RESTIC_REPOSITORY_FILE:-}" ] || {
  echo "Dépôt Restic introuvable dans $SOURCE_ENV : indiquez RESTIC_REPOSITORY et RESTIC_PASSWORD_FILE."; exit 3; }

exec > >(tee "$RAPPORT") 2>&1
LIBRE=$(df --output=avail -BG /var/tmp | tail -1 | tr -dc 0-9)
echo "== Espace libre /var/tmp : ${LIBRE} Go"
[ "$LIBRE" -ge 10 ] || { echo "Moins de 10 Go libres : arrêt."; exit 4; }

echo "== Contrôle du dépôt (5 % des données)"
restic check --read-data-subset=5%

echo "== Dernier instantané"
restic snapshots --latest 1 --compact
mkdir -p "$DOSSIER"
chmod 700 "$DOSSIER"
restic restore latest --target "$DOSSIER" >/dev/null

DUMP=$(find "$DOSSIER" -type f \( -name '*.sql' -o -name '*.sql.gz' -o -name '*.dump' \) -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
[ -n "$DUMP" ] || { echo "Aucun dump dans l'instantané. Fichiers :"; find "$DOSSIER" -maxdepth 4 | head -40; exit 5; }
echo "== Dump : $(basename "$DUMP") ($(du -h "$DUMP" | cut -f1))"

IMAGE=$(docker inspect --format '{{.Config.Image}}' "$PROD_PG")
docker run -d --name "$CONTENEUR" --network none -e POSTGRES_PASSWORD=jetable -e POSTGRES_DB=feba_prod \
  -e POSTGRES_USER=feba_user "$IMAGE" >/dev/null
for _ in $(seq 1 60); do docker exec "$CONTENEUR" pg_isready -U feba_user -d feba_prod >/dev/null 2>&1 && break; sleep 2; done

echo "== Chargement dans le conteneur jetable"
case "$DUMP" in
  *.gz)   gunzip -c "$DUMP" | docker exec -i "$CONTENEUR" psql -q -v ON_ERROR_STOP=1 -U feba_user -d feba_prod >/dev/null ;;
  *.dump) docker exec -i "$CONTENEUR" pg_restore -U feba_user -d feba_prod --no-owner <"$DUMP" ;;
  *)      docker exec -i "$CONTENEUR" psql -q -v ON_ERROR_STOP=1 -U feba_user -d feba_prod <"$DUMP" >/dev/null ;;
esac

REQUETE="SELECT 'SELECT '''||tablename||''' t, count(*) n FROM public.\"'||tablename||'\"' FROM pg_tables WHERE schemaname='public' ORDER BY 1"
compter() { # conteneur → « table nombre »
  docker exec "$1" sh -c "psql -At -U feba_user -d feba_prod -c \"$REQUETE\" | sed 's/\$/;/' | psql -At -F ' ' -U feba_user -d feba_prod"
}
compter "$CONTENEUR" | sort >"$DOSSIER/restauree.txt"
compter "$PROD_PG" | sort >"$DOSSIER/production.txt"

echo "== Tables restaurées : $(wc -l <"$DOSSIER/restauree.txt") ; en production : $(wc -l <"$DOSSIER/production.txt")"
for t in accounts_customuser students_student grades_grade payments_payment bulletins_bulletin; do
  echo "   $t restaurée=$(grep "^$t " "$DOSSIER/restauree.txt" | cut -d' ' -f2) production=$(grep "^$t " "$DOSSIER/production.txt" | cut -d' ' -f2)"
done
echo "== Tables différentes (écarts normaux : écritures depuis la sauvegarde)"
diff "$DOSSIER/restauree.txt" "$DOSSIER/production.txt" | grep '^[<>]' | head -40 || true

echo "== Médias restaurés"
for d in bulletins receipts students user_files; do
  echo "   $d instantané=$(find "$DOSSIER" -type f -path "*/media/$d/*" | wc -l) production=$(docker exec "${PROD_MEDIA%%:*}" sh -c "find ${PROD_MEDIA#*:}/$d -type f 2>/dev/null | wc -l")"
done
echo "== Terminé. Rapport : $RAPPORT. Nettoyage du dossier et du conteneur jetables."
