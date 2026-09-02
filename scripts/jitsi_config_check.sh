#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# make jitsi-config-check — cohérence de la configuration Jitsi.
#
# CE QUE CE CONTRÔLE FAIT, ET POURQUOI IL EST SÉPARÉ DE jitsi-health
# ------------------------------------------------------------------
# `jitsi-health` interroge le réseau : il dit si l'instance RÉPOND. Il ne
# peut donc rien dire tant que le DNS n'existe pas, et il est inutilisable
# en CI, où meet.globalfeba.com n'est de toute façon pas joignable.
#
# Ce script-ci ne touche pas au réseau. Il lit les FICHIERS et vérifie que
# ce qu'ils déclarent est cohérent : aucun domaine public, des secrets
# présents et de longueur suffisante, le même APP_ID des deux côtés, un
# domaine de production identique partout. Ce sont exactement les erreurs
# qui produisent un « ça ne marche pas » silencieux après déploiement.
#
# Sortie 0 si tout est cohérent, 1 sinon.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
FAILURES=0
WARNINGS=0

ok()   { printf '  %sOK%s    %s\n'    "$GREEN" "$OFF" "$1"; }
bad()  { printf '  %sÉCHEC%s %s\n'    "$RED"   "$OFF" "$1"; FAILURES=$((FAILURES+1)); }
warn() { printf '  %sNOTE%s  %s\n'    "$YELLOW" "$OFF" "$1"; WARNINGS=$((WARNINGS+1)); }

# Domaines publics interdits — même liste que JITSI_FORBIDDEN_DOMAINS
# (backend/feba_project/settings/base.py). Les cours de FEBA FHA sont
# donnés à des mineurs : un flux qui transite chez un tiers, sans
# authentification, n'est pas une option de repli.
FORBIDDEN='meet\.jit\.si|8x8\.vc|jitsi\.org'

# Valeur lue dans un fichier .env, sans exécuter le fichier.
envval() { [ -f "$1" ] && sed -n "s/^$2=//p" "$1" | tail -1 || true; }

printf '%sCohérence de la configuration Jitsi%s\n\n' "$BOLD" "$OFF"

# ── 1. Aucun domaine public déclaré dans un fichier de configuration ──
printf '%sDomaines publics interdits%s\n' "$BOLD" "$OFF"
OFFENDERS=""
for f in .env .env.dev .env.prod .env.example .env.dev.example .env.prod.example .env.jitsi .env.jitsi.example; do
  [ -f "$f" ] || continue
  # Uniquement les AFFECTATIONS : une mention en commentaire explique
  # justement pourquoi ces domaines sont proscrits, et doit rester.
  if grep -nE "^[A-Z_]*(DOMAIN|URL)=.*($FORBIDDEN)" "$f" >/dev/null 2>&1; then
    OFFENDERS="$OFFENDERS $f"
  fi
done
if [ -n "$OFFENDERS" ]; then
  bad "instance publique affectée dans :$OFFENDERS"
else
  ok "aucun fichier .env n'affecte d'instance publique"
fi

if grep -rnE "^[[:space:]]*JITSI_DOMAIN[[:space:]]*=[[:space:]]*['\"]?($FORBIDDEN)" \
     backend/feba_project backend/apps >/dev/null 2>&1; then
  bad "une instance publique est écrite en dur dans le code backend"
else
  ok "aucune instance publique en dur dans le code backend"
fi

# ── 2. Le domaine configuré ──────────────────────────────────────────
printf '\n%sDomaine configuré%s\n' "$BOLD" "$OFF"
ENVFILE=""
for f in .env.prod .env .env.dev; do [ -f "$f" ] && { ENVFILE="$f"; break; }; done

if [ -z "$ENVFILE" ]; then
  warn "aucun .env réel — contrôle sur les modèles .env.*.example uniquement"
  ENVFILE=".env.prod.example"
fi
DOMAIN="$(envval "$ENVFILE" JITSI_DOMAIN)"

if [ -z "$DOMAIN" ]; then
  warn "JITSI_DOMAIN vide dans $ENVFILE — la visioconférence restera indisponible (et c'est le comportement voulu tant que l'instance n'existe pas)"
elif printf '%s' "$DOMAIN" | grep -qE "$FORBIDDEN"; then
  bad "JITSI_DOMAIN=$DOMAIN est une instance PUBLIQUE interdite"
else
  ok "JITSI_DOMAIN=$DOMAIN ($ENVFILE)"
fi

# ── 3. Secrets ───────────────────────────────────────────────────────
printf '\n%sSecrets de signature%s\n' "$BOLD" "$OFF"
APP_ID="$(envval "$ENVFILE" JITSI_APP_ID)"
APP_SECRET="$(envval "$ENVFILE" JITSI_APP_SECRET)"

case "$APP_ID" in
  ""|CHANGE_ME*) warn "JITSI_APP_ID non renseigné dans $ENVFILE" ;;
  *)             ok "JITSI_APP_ID renseigné" ;;
esac

case "$APP_SECRET" in
  ""|CHANGE_ME*)
    warn "JITSI_APP_SECRET non renseigné dans $ENVFILE" ;;
  *)
    if [ "${#APP_SECRET}" -lt 32 ]; then
      bad "JITSI_APP_SECRET fait ${#APP_SECRET} caractères : trop court pour signer des jetons (openssl rand -hex 32)"
    else
      ok "JITSI_APP_SECRET de longueur suffisante (${#APP_SECRET} caractères)"
    fi ;;
esac

# ── 4. Le backend et la pile Jitsi partagent-ils le même APP_ID ? ────
# Un APP_ID différent des deux côtés produit le symptôme le plus
# déroutant qui soit : tout démarre, tout paraît sain, et chaque
# « Rejoindre » est refusé par Prosody sans explication côté FEBA.
if [ -f .env.jitsi ]; then
  printf '\n%sAccord backend ↔ pile Jitsi%s\n' "$BOLD" "$OFF"
  J_ID="$(envval .env.jitsi JITSI_APP_ID)"
  J_SECRET="$(envval .env.jitsi JITSI_APP_SECRET)"
  if [ -n "$APP_ID" ] && [ -n "$J_ID" ] && [ "$APP_ID" != "$J_ID" ]; then
    bad "JITSI_APP_ID diffère : « $APP_ID » ($ENVFILE) ≠ « $J_ID » (.env.jitsi)"
  elif [ -n "$J_ID" ]; then
    ok "JITSI_APP_ID identique des deux côtés"
  fi
  if [ -n "$APP_SECRET" ] && [ -n "$J_SECRET" ] && [ "$APP_SECRET" != "$J_SECRET" ]; then
    bad "JITSI_APP_SECRET diffère entre $ENVFILE et .env.jitsi : aucun jeton ne sera accepté"
  elif [ -n "$J_SECRET" ]; then
    ok "JITSI_APP_SECRET identique des deux côtés"
  fi

  PUBLIC_URL="$(envval .env.jitsi JITSI_PUBLIC_URL)"
  if [ -n "$PUBLIC_URL" ] && [ -n "$DOMAIN" ]; then
    case "$PUBLIC_URL" in
      *"$DOMAIN"*|http://localhost*|http://127.0.0.1*)
        ok "JITSI_PUBLIC_URL cohérent avec JITSI_DOMAIN" ;;
      *)
        bad "JITSI_PUBLIC_URL=$PUBLIC_URL ne correspond pas à JITSI_DOMAIN=$DOMAIN" ;;
    esac
  fi
else
  printf '\n'
  warn ".env.jitsi absent — la pile Jitsi n'a pas encore été initialisée (« make jitsi-up »)"
fi

# ── 5. Fichiers de déploiement présents ──────────────────────────────
printf '\n%sFichiers de déploiement%s\n' "$BOLD" "$OFF"
for f in docker-compose.jitsi.yml docker-compose.jitsi.prod.yml; do
  [ -f "$f" ] && ok "$f présent" || bad "$f manquant"
done

# ── Verdict ──────────────────────────────────────────────────────────
printf '\n'
if [ "$FAILURES" -gt 0 ]; then
  printf '%s%d incohérence(s) bloquante(s)%s'  "$RED" "$FAILURES" "$OFF"
  [ "$WARNINGS" -gt 0 ] && printf ', %d note(s)' "$WARNINGS"
  printf '\n'
  exit 1
fi
printf '%sConfiguration cohérente%s' "$GREEN" "$OFF"
[ "$WARNINGS" -gt 0 ] && printf ' — %d note(s) : voir ci-dessus' "$WARNINGS"
printf '\n'
exit 0
