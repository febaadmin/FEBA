#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# Construit l'archive de livraison.
#
# CE QUI EST EXCLU, ET POURQUOI
# -----------------------------
# Une archive de livraison n'est pas une copie du répertoire de travail.
# En sont retirés : les dépendances reconstructibles (node_modules,
# environnements virtuels), les caches, les artefacts de compilation, et
# surtout TOUT fichier de configuration réel — un `.env` de production
# livré par mégarde publie des mots de passe de base de données.
#
# Sont également exclus les documents produits pendant les essais
# (backend/media, backend/private_media) : ce sont des reçus et des
# fiches nominatives d'élèves de démonstration, mais leur place n'est pas
# dans une archive qui circule.
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NOM="${1:-feba_corrected_production_ready}"
SORTIE="${2:-$(dirname "$ROOT")}"
STAGE="$(mktemp -d)"
CIBLE="$STAGE/feba_v6_version_finale_corrigee"

trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$CIBLE"

tar -C "$ROOT" \
    --exclude='./.git' \
    --exclude='./frontend/node_modules' \
    --exclude='./frontend/dist' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='./backend/venv' \
    --exclude='./backend/.venv' \
    --exclude='./backend/staticfiles' \
    --exclude='./backend/media' \
    --exclude='./backend/private_media' \
    --exclude='./backend/db.sqlite3' \
    --exclude='*.log' \
    --exclude='./.env' \
    --exclude='./.env.dev' \
    --exclude='./.env.prod' \
    --exclude='./.env.jitsi' \
    --exclude='./.env.local' \
    --exclude='./backend/.env' \
    --exclude='.DS_Store' \
    -cf - . | tar -xf - -C "$CIBLE"

# ── Garde-fous : on VÉRIFIE, on ne suppose pas ────────────────────────
echo "Contrôles avant compression :"

fautifs="$(find "$CIBLE" \( -name '.env' -o -name '.env.prod' -o -name '.env.dev' \
             -o -name '.env.jitsi' -o -name '.env.local' \) -not -name '*.example' -print)"
if [ -n "$fautifs" ]; then
  echo "  ÉCHEC : fichiers de configuration réels présents :"; echo "$fautifs"; exit 1
fi
echo "  OK    aucun fichier .env réel"

for interdit in node_modules __pycache__ .pytest_cache venv; do
  if find "$CIBLE" -name "$interdit" -print -quit | grep -q .; then
    echo "  ÉCHEC : « $interdit » présent dans l'archive"; exit 1
  fi
done
echo "  OK    aucun cache ni dépendance reconstructible"

for requis in backend/manage.py frontend/package.json Makefile \
              docker-compose.yml docker-compose.prod.yml \
              docker-compose.jitsi.yml docker-compose.jitsi.prod.yml \
              nginx/nginx.prod.conf \
              backend/apps/schools/institution.py \
              frontend/public/images/feba-fha/feba-fha-flyer.pdf \
              frontend/src/site/components/FhaFlyerDownload.jsx \
              INSTALLATION_GUIDE.md DEPLOYMENT_PRODUCTION.md \
              JITSI_PRODUCTION_GUIDE.md MANUAL_PRODUCTION_ACTIONS.md \
              TEST_REPORT.md SECURITY_AUDIT.md KNOWN_LIMITATIONS.md \
              FINAL_REPORT.md .env.example .env.prod.example; do
  [ -e "$CIBLE/$requis" ] || { echo "  ÉCHEC : « $requis » manquant"; exit 1; }
done
echo "  OK    tous les fichiers attendus sont présents"

ARCHIVE="$SORTIE/${NOM}.zip"
rm -f "$ARCHIVE"
(cd "$STAGE" && zip -qr "$ARCHIVE" feba_v6_version_finale_corrigee)

# Empreinte déposée À CÔTÉ de l'archive : un fichier ne peut pas contenir
# sa propre empreinte (l'y écrire la changerait). SHA256SUMS.txt, à
# l'intérieur, couvre les fichiers du projet.
sha256sum "$ARCHIVE" | sed "s#$SORTIE/##" > "$ARCHIVE.sha256"

echo ""
echo "Archive : $ARCHIVE"
echo "Taille  : $(du -h "$ARCHIVE" | cut -f1) ($(stat -c%s "$ARCHIVE") octets)"
echo "SHA-256 : $(sha256sum "$ARCHIVE" | cut -d' ' -f1)"
echo "Fichiers: $(unzip -l "$ARCHIVE" | tail -1 | awk '{print $2}')"
echo "Empreinte déposée dans : $ARCHIVE.sha256"
