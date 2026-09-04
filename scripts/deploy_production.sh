#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# Déploiement de FEBA sur le serveur de production.
#
# CE QUE CE SCRIPT REFUSE DE FAIRE
# --------------------------------
# Il ne suppose rien. En particulier, il ne suppose PAS que l'image
# `jitsi/web` déployée honore le point d'extension `nginx-custom` : il le
# VÉRIFIE dans le conteneur en service, et le dit clairement si ce n'est
# pas le cas. Un déploiement qui annonce des en-têtes de sécurité sans
# les poser est pire qu'un déploiement qui prévient.
#
# Il ne touche à AUCUN secret. Les valeurs réelles restent sur le serveur,
# dans les fichiers `.env*` que ce script sauvegarde sans les lire.
#
# TOPOLOGIE VISÉE — celle réellement en service
# ---------------------------------------------
#   répertoire   : /opt/feba/app
#   projet       : app
#   Compose      : docker-compose.jitsi.yml + docker-compose.jitsi.prod.yml
#   Jitsi Web    : publie 80 et 443 DIRECTEMENT (nginx du conteneur)
#   JVB          : UDP/10000, JVB_ADVERTISE_IPS=89.167.63.1
#   Réseaux      : app_jitsi + feba_jitsi_shared
#
# USAGE
#   bash scripts/deploy_production.sh --check     # rien n'est modifié
#   bash scripts/deploy_production.sh             # déploie
#   bash scripts/deploy_production.sh --rollback  # revient en arrière
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
HORODATAGE="$(date +%Y%m%d-%H%M%S)"
SAUVEGARDES="${FEBA_BACKUP_DIR:-/root/feba-sauvegardes}"
JITSI_COMPOSE="-f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml"
ECHECS=0
MODE="deploy"

case "${1:-}" in
  --check)    MODE="check" ;;
  --rollback) MODE="rollback" ;;
  "")         MODE="deploy" ;;
  *) echo "Usage : $0 [--check|--rollback]"; exit 2 ;;
esac

titre()  { printf '\n%s%s%s\n' "$BOLD" "$1" "$OFF"; }
ok()     { printf '  %sOK%s    %s\n' "$GREEN" "$OFF" "$1"; }
avert()  { printf '  %sATTENTION%s  %s\n' "$YELLOW" "$OFF" "$1"; }
echec()  { printf '  %sÉCHEC%s  %s\n' "$RED" "$OFF" "$1"; ECHECS=$((ECHECS+1)); }

# ── 0. Prérequis ─────────────────────────────────────────────────────
titre "Prérequis"
command -v docker >/dev/null 2>&1 || { echec "Docker est requis."; exit 1; }
docker info >/dev/null 2>&1 || { echec "Le démon Docker ne répond pas."; exit 1; }
docker compose version >/dev/null 2>&1 || { echec "Docker Compose v2 est requis."; exit 1; }
ok "Docker $(docker version --format '{{.Server.Version}}') et Compose disponibles"

# ── ROLLBACK ─────────────────────────────────────────────────────────
if [ "$MODE" = "rollback" ]; then
  titre "Retour arrière"
  DERNIERE="$(ls -1d "$SAUVEGARDES"/* 2>/dev/null | tail -1)"
  if [ -z "$DERNIERE" ]; then
    echec "Aucune sauvegarde dans $SAUVEGARDES — rien à restaurer."
    exit 1
  fi
  echo "  Sauvegarde utilisée : $DERNIERE"
  if [ -f "$DERNIERE/HEAD" ]; then
    COMMIT="$(cat "$DERNIERE/HEAD")"
    echo "  Retour au commit $COMMIT"
    git checkout "$COMMIT" 2>&1 | tail -2
  fi
  for f in .env .env.jitsi backend/.env; do
    [ -f "$DERNIERE/$(basename "$f")" ] && cp "$DERNIERE/$(basename "$f")" "$f" && ok "restauré : $f"
  done
  docker compose $JITSI_COMPOSE up -d
  echo
  echo "Retour arrière appliqué. Contrôlez : make jitsi-health"
  exit 0
fi

# ── 1. Sauvegarde ────────────────────────────────────────────────────
titre "Sauvegarde avant modification"
DESTINATION="$SAUVEGARDES/$HORODATAGE"
if [ "$MODE" = "deploy" ]; then
  mkdir -p "$DESTINATION"
  git rev-parse HEAD > "$DESTINATION/HEAD" 2>/dev/null && ok "commit courant noté : $(cat "$DESTINATION/HEAD")"
  # Les .env sont COPIÉS sans être lus : ils contiennent les secrets réels.
  for f in .env .env.jitsi backend/.env; do
    [ -f "$f" ] && cp "$f" "$DESTINATION/$(basename "$f")" && ok "sauvegardé : $f"
  done
  docker compose $JITSI_COMPOSE config > "$DESTINATION/compose-resolu.yml" 2>/dev/null \
    && ok "configuration Compose résolue sauvegardée"
  docker compose $JITSI_COMPOSE images > "$DESTINATION/images.txt" 2>/dev/null \
    && ok "versions d'images notées"
  docker compose $JITSI_COMPOSE ps > "$DESTINATION/conteneurs.txt" 2>/dev/null
  ok "sauvegarde dans $DESTINATION"
else
  avert "mode --check : aucune sauvegarde effectuée"
fi

# ── 2. Fichiers d'environnement ──────────────────────────────────────
titre "Fichiers d'environnement"
for f in .env.jitsi; do
  if [ -f "$f" ]; then ok "$f présent"
  else echec "$f absent — copiez $f.example et renseignez-le"; fi
done

# Les variables que le code EXIGE réellement. On vérifie leur présence,
# jamais leur valeur : un secret ne se journalise pas.
if [ -f .env.jitsi ]; then
  for v in JITSI_DOMAIN JITSI_APP_ID JITSI_APP_SECRET JVB_ADVERTISE_IPS; do
    if grep -qE "^${v}=.+" .env.jitsi; then ok "$v renseignée"
    else echec "$v absente ou vide dans .env.jitsi"; fi
  done
  # Cette valeur a été vérifiée sur le serveur : ne pas la changer sans
  # preuve d'un défaut.
  if grep -qE "^JVB_ADVERTISE_IPS=89\.167\.63\.1" .env.jitsi; then
    ok "JVB_ADVERTISE_IPS = 89.167.63.1 (valeur vérifiée en production)"
  else
    avert "JVB_ADVERTISE_IPS diffère de 89.167.63.1 — vérifiez l'IP publique réelle"
  fi
fi

# ── 3. Réseau partagé ────────────────────────────────────────────────
titre "Réseau partagé"
if docker network inspect feba_jitsi_shared >/dev/null 2>&1; then
  ok "feba_jitsi_shared existe déjà"
elif [ "$MODE" = "deploy" ]; then
  docker network create feba_jitsi_shared >/dev/null && ok "feba_jitsi_shared créé"
else
  avert "feba_jitsi_shared absent — serait créé par le déploiement"
fi

# ── 4. Assemblage Compose ────────────────────────────────────────────
titre "Assemblage Compose"
if docker compose $JITSI_COMPOSE config >/dev/null 2>&1; then
  ok "docker-compose.jitsi.yml + prod.yml : assemblage valide"
else
  echec "assemblage Compose invalide :"
  docker compose $JITSI_COMPOSE config 2>&1 | tail -5
fi

if docker compose $JITSI_COMPOSE config 2>/dev/null | grep -q "nginx-custom"; then
  ok "le montage nginx-custom figure dans l'assemblage"
else
  echec "le montage nginx-custom est ABSENT de l'assemblage"
fi

if [ -f jitsi/nginx-custom/feba-security-headers.conf ]; then
  ok "jitsi/nginx-custom/feba-security-headers.conf présent"
else
  echec "le fichier d'en-têtes est absent du dépôt"
fi

[ "$MODE" = "check" ] && { titre "Bilan"; [ "$ECHECS" -eq 0 ] && { ok "prêt à déployer"; exit 0; } || { echec "$ECHECS point(s) à corriger"; exit 1; }; }
[ "$ECHECS" -gt 0 ] && { titre "Bilan"; echec "$ECHECS point(s) bloquant(s) — déploiement interrompu, rien n'a été modifié."; exit 1; }

# ── 5. Démarrage ─────────────────────────────────────────────────────
titre "Démarrage de la pile Jitsi"
docker compose $JITSI_COMPOSE up -d 2>&1 | tail -6
sleep 10

# ── 6. LE CONTRÔLE QUI NE SUPPOSE RIEN ───────────────────────────────
#
# L'image `jitsi/web` inclut, dans le gabarit de son vhost :
#
#     include /run/web/config/nginx-custom/*.conf;
#
# C'est le point d'extension sur lequel repose toute la configuration des
# en-têtes. Il est présent dans le gabarit publié par Jitsi, mais l'image
# `:stable` déployée peut être plus ancienne. On ne le suppose donc pas :
# on regarde la configuration RÉELLEMENT chargée par nginx.
titre "Point d'extension nginx-custom — vérification dans le conteneur"
SERVICE="jitsi-web"

if docker compose $JITSI_COMPOSE exec -T "$SERVICE" test -d /run/web/config/nginx-custom 2>/dev/null; then
  ok "/run/web/config/nginx-custom est monté dans le conteneur"
else
  echec "/run/web/config/nginx-custom ABSENT du conteneur — le montage n'a pas pris"
fi

if docker compose $JITSI_COMPOSE exec -T "$SERVICE" \
     grep -q "nginx-custom" /defaults/meet.conf 2>/dev/null; then
  ok "le gabarit de l'image contient bien l'inclusion nginx-custom"
else
  echec "le gabarit de l'image N'INCLUT PAS nginx-custom : cette version de
        jitsi/web ne connaît pas ce point d'extension. Voir la solution de
        repli dans JITSI_PRODUCTION_ACTIONS.md §5 bis, et prévoyez une mise
        à jour de l'image."
fi

if docker compose $JITSI_COMPOSE exec -T "$SERVICE" nginx -T 2>/dev/null \
     | grep -q "Referrer-Policy"; then
  ok "Referrer-Policy figure dans la configuration nginx CHARGÉE"
else
  echec "Referrer-Policy absent de la configuration chargée — les en-têtes
        ne seront pas servis. C'est le symptôme du point ci-dessus."
fi

if docker compose $JITSI_COMPOSE exec -T "$SERVICE" nginx -t 2>&1 | grep -q "successful"; then
  ok "nginx -t : configuration syntaxiquement valide"
else
  echec "nginx -t échoue dans le conteneur :"
  docker compose $JITSI_COMPOSE exec -T "$SERVICE" nginx -t 2>&1 | tail -4
fi

# ── 7. Contrôle depuis l'extérieur ───────────────────────────────────
titre "Réponse réelle de l'instance"
DOMAINE="$(grep -E '^JITSI_DOMAIN=' .env.jitsi 2>/dev/null | cut -d= -f2)"
DOMAINE="${DOMAINE:-meet.globalfeba.com}"
ENTETES="$(curl -sSI "https://$DOMAINE/" 2>/dev/null)"
for h in strict-transport-security x-content-type-options referrer-policy content-security-policy; do
  if printf '%s' "$ENTETES" | grep -qi "^$h:"; then ok "$h servi"
  else echec "$h ABSENT de la réponse de https://$DOMAINE/"; fi
done

# ── 8. Bilan ─────────────────────────────────────────────────────────
titre "Bilan"
if [ "$ECHECS" -eq 0 ]; then
  ok "Déploiement appliqué et vérifié."
  echo
  echo "  Contrôle complet  : make jitsi-health JITSI_TARGET=$DOMAINE"
  echo "  Tests réels       : JITSI_REAL_WORLD_TEST_PLAN.md"
  exit 0
fi

echec "$ECHECS point(s) en échec."
echo
echo "  Sauvegarde        : $DESTINATION"
echo "  Retour arrière    : bash scripts/deploy_production.sh --rollback"
exit 1
