#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# Validation de TOUS les fichiers Docker Compose livrés.
#
# POURQUOI CE SCRIPT PLUTÔT QU'UN SIMPLE `docker compose config`
# --------------------------------------------------------------
# Lancé nu, `docker compose config` échoue sur ce dépôt — et il a raison :
#
#   * docker-compose.yml et docker-compose.prod.yml déclarent
#     « env_file: .env.dev / .env.prod », qui ne sont pas versionnés
#     (ce sont les fichiers de configuration réels) ;
#   * les surcouches Jitsi utilisent « ${VAR:?message} » pour REFUSER de
#     démarrer sans IP publique ni secret — c'est une garantie voulue,
#     pas un défaut à contourner.
#
# Valider revient donc à fournir des valeurs de TEST, jetables, et à
# vérifier que l'assemblage tient. On ne désactive aucune exigence : on
# la satisfait avec des valeurs sans valeur.
#
# Les fichiers temporaires sont retirés à la sortie, y compris en cas
# d'interruption : un .env.prod oublié dans un dépôt est précisément ce
# que scripts/repo_safety_check.sh cherche.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN=$'\033[32m'; RED=$'\033[31m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
FAILURES=0
CREATED=()
JITSI_ENV="$(mktemp)"

cleanup() {
  for f in "${CREATED[@]:-}"; do [ -n "$f" ] && rm -f "$ROOT/$f"; done
  rm -f "$JITSI_ENV"
}
trap cleanup EXIT INT TERM

# Fichiers d'environnement de test, uniquement s'ils n'existent pas déjà :
# on ne veut surtout pas écraser la configuration réelle d'un serveur.
for pair in ".env.dev:.env.dev.example" ".env.prod:.env.prod.example"; do
  cible="${pair%%:*}"; modele="${pair##*:}"
  if [ ! -f "$cible" ] && [ -f "$modele" ]; then
    cp "$modele" "$cible"
    CREATED+=("$cible")
  fi
done

cat > "$JITSI_ENV" <<'EOF'
JITSI_APP_ID=feba_validation
JITSI_APP_SECRET=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
JITSI_DOMAIN=meet.globalfeba.com
JITSI_PUBLIC_URL=https://meet.globalfeba.com
LETSENCRYPT_EMAIL=validation@example.test
JVB_ADVERTISE_IPS=203.0.113.10
JITSI_PROXY_PORT=8443
JICOFO_COMPONENT_SECRET=validation
JICOFO_AUTH_PASSWORD=validation
JVB_AUTH_PASSWORD=validation
EOF

verifier() {
  local libelle="$1"; shift
  printf '  %-46s ' "$libelle"

  # Le CODE DE SORTIE de « docker compose » fait foi, et lui seul.
  #
  # Une première version chaînait « … | grep -v '^time=' » dans la
  # condition : `grep -v` sort 1 quand il ne reste plus une seule ligne,
  # c'est-à-dire précisément quand tout va bien. Les cinq assemblages
  # étaient déclarés invalides alors que les cinq étaient corrects.
  local sortie statut
  sortie="$(docker compose "$@" config --quiet 2>&1)"
  statut=$?
  # Les avertissements horodatés de Compose ne sont pas des erreurs.
  sortie="$(printf '%s\n' "$sortie" | grep -v '^time=' || true)"

  if [ "$statut" -eq 0 ]; then
    printf '%sOK%s\n' "$GREEN" "$OFF"
  else
    printf '%sÉCHEC%s\n' "$RED" "$OFF"
    printf '%s\n' "$sortie" | sed 's/^/        /' | head -5
    FAILURES=$((FAILURES+1))
  fi
}

printf '%sFichiers Docker Compose%s\n\n' "$BOLD" "$OFF"
verifier "développement"            -f docker-compose.yml
verifier "production"               -f docker-compose.prod.yml
verifier "Jitsi (base)"             --env-file "$JITSI_ENV" -f docker-compose.jitsi.yml
verifier "Jitsi + serveur dédié"    --env-file "$JITSI_ENV" -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml
verifier "Jitsi + derrière le proxy" --env-file "$JITSI_ENV" -f docker-compose.jitsi.yml -f docker-compose.jitsi.behind-proxy.yml

printf '\n'
if [ "$FAILURES" -gt 0 ]; then
  printf '%s%d fichier(s) invalide(s)%s\n' "$RED" "$FAILURES" "$OFF"
  exit 1
fi
printf '%sTous les assemblages Compose sont valides%s\n' "$GREEN" "$OFF"
exit 0
