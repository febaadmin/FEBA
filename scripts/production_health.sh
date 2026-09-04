#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# make production-health — état de bout en bout de la production.
#
# POURQUOI CE SCRIPT EST SÉPARÉ DE jitsi-health
# ---------------------------------------------
# `jitsi-health` répond à une question : « l'instance de visioconférence
# est-elle joignable et correctement configurée ? ». Celui-ci en pose une
# plus large : « l'établissement peut-il travailler ce matin ? ».
#
# Les deux pannes ne se diagnostiquent pas au même endroit. Une
# application debout avec Jitsi éteint laisse les cours en ligne à
# l'arrêt ; un Jitsi impeccable devant une base de données inaccessible
# ne sert à rien. Un seul « OK » global masquerait celle des deux qui
# compte aujourd'hui.
#
# CE SCRIPT NE MODIFIE RIEN. Il peut être lancé à tout moment, y compris
# pendant un cours.
#
# Sortie : 0 si tout est opérationnel, 1 si quelque chose est dégradé.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
DEGRADES=0
INDISPONIBLES=0

SITE="${FEBA_SITE:-https://globalfeba.com}"
JITSI="${JITSI_TARGET:-meet.globalfeba.com}"
DELAI="${HEALTH_TIMEOUT:-10}"

titre() { printf '\n%s%s%s\n' "$BOLD" "$1" "$OFF"; }
ok()    { printf '  %sOK%s            %s\n' "$GREEN" "$OFF" "$1"; }
degr()  { printf '  %sDÉGRADÉ%s       %s\n' "$YELLOW" "$OFF" "$1"; DEGRADES=$((DEGRADES+1)); }
indis() { printf '  %sINDISPONIBLE%s  %s\n' "$RED" "$OFF" "$1"; INDISPONIBLES=$((INDISPONIBLES+1)); }

# `curl` renvoie 000 quand il n'a pas pu se connecter. On distingue donc
# « le service répond mal » de « le service ne répond pas » : ce ne sont
# pas les mêmes gestes.
code_http() {
  curl -sS -o /dev/null -w "%{http_code}" --max-time "$DELAI" "$1" 2>/dev/null || echo "000"
}

# ── Application ──────────────────────────────────────────────────────
titre "Application"
CODE="$(code_http "$SITE/")"
case "$CODE" in
  200|30[1278]) ok "site public : HTTP $CODE" ;;
  000)          indis "site public injoignable ($SITE)" ;;
  *)            degr "site public : HTTP $CODE" ;;
esac

CODE="$(code_http "$SITE/api/")"
case "$CODE" in
  # 404 sur la racine de l'API est NORMAL : aucune vue n'y est montée.
  # C'est même la preuve que Django répond plutôt qu'un serveur statique.
  200|401|403|404) ok "API : HTTP $CODE (Django répond)" ;;
  000)             indis "API injoignable" ;;
  5*)              indis "API : HTTP $CODE — erreur serveur" ;;
  *)               degr "API : HTTP $CODE" ;;
esac

# ── Services locaux, si ce script tourne sur le serveur ──────────────
titre "Services locaux"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  for service in postgres-prod redis-prod backend-prod celery-prod celery-beat-prod; do
    etat="$(docker ps --filter "name=$service" --format '{{.Status}}' 2>/dev/null | head -1)"
    if [ -z "$etat" ]; then
      degr "$service : conteneur absent (normal hors du serveur de production)"
    elif printf '%s' "$etat" | grep -qi "^up"; then
      ok "$service : $etat"
    else
      indis "$service : $etat"
    fi
  done
else
  degr "Docker indisponible ici — contrôle des conteneurs impossible (lancez ce script sur le serveur)"
fi

# ── Visioconférence ──────────────────────────────────────────────────
titre "Visioconférence"
CODE="$(code_http "https://$JITSI/")"
case "$CODE" in
  200) ok "$JITSI : HTTP 200" ;;
  000) indis "$JITSI injoignable" ;;
  *)   degr "$JITSI : HTTP $CODE" ;;
esac

CODE="$(code_http "https://$JITSI/external_api.js")"
if [ "$CODE" = "200" ]; then
  ok "external_api.js servi"
else
  # Sans ce fichier, le navigateur ne peut ouvrir aucune conférence,
  # alors que la page d'accueil répond parfaitement.
  indis "external_api.js : HTTP $CODE — aucune conférence ne pourra s'ouvrir"
fi

CODE="$(code_http "https://$JITSI/xmpp-websocket")"
if [ "$CODE" = "404" ]; then
  indis "/xmpp-websocket : 404 — le proxy n'a aucune règle pour la signalisation"
elif [ "$CODE" = "000" ]; then
  degr "/xmpp-websocket injoignable"
else
  # 101, 200, 400, 426 ou 501 prouvent qu'une règle existe. Seul 404
  # signifie son absence. La poignée de main réelle demande un client
  # WebSocket — voir JITSI_REAL_WORLD_TEST_PLAN.md.
  ok "/xmpp-websocket : HTTP $CODE (une règle de proxy existe)"
fi

titre "En-têtes de sécurité servis"
ENTETES="$(curl -sSI --max-time "$DELAI" "https://$JITSI/" 2>/dev/null)"
if [ -z "$ENTETES" ]; then
  degr "en-têtes non lisibles"
else
  for h in strict-transport-security x-content-type-options referrer-policy content-security-policy; do
    if printf '%s' "$ENTETES" | grep -qi "^$h:"; then
      ok "$h"
    else
      degr "$h absent — voir JITSI_PRODUCTION_ACTIONS.md"
    fi
  done
fi

titre "Aucun repli vers une instance publique"
if printf '%s' "$JITSI" | grep -qiE "meet\.jit\.si|jitsi\.riot\.im"; then
  indis "le domaine visé EST une instance publique : les cours y seraient hébergés hors de FEBA"
else
  ok "$JITSI n'est pas une instance publique"
fi

# ── Bilan ────────────────────────────────────────────────────────────
titre "Bilan"
if [ "$INDISPONIBLES" -gt 0 ]; then
  printf '  %sUNAVAILABLE%s — %d point(s) hors service, %d dégradé(s)\n' \
    "$RED" "$OFF" "$INDISPONIBLES" "$DEGRADES"
  exit 1
elif [ "$DEGRADES" -gt 0 ]; then
  printf '  %sDEGRADED%s — %d point(s) dégradé(s), aucun hors service\n' \
    "$YELLOW" "$OFF" "$DEGRADES"
  exit 1
fi
printf '  %sREADY%s — tous les contrôles sont au vert\n' "$GREEN" "$OFF"
exit 0
