#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# FEBA — make doctor
#
# Étape 1/12 du pipeline d'installation (voir scripts/bootstrap.sh) :
# vérifie les prérequis et la cohérence de la configuration AVANT de
# toucher à Docker. Peut aussi être lancé seul, à tout moment, pour
# diagnostiquer une configuration douteuse sans rien démarrer.
#
# P11 — Convention .env UNIQUE : ce script dit explicitement quel
# fichier sera réellement utilisé par docker-compose.yml (`.env.dev`),
# et signale tout `.env` isolé qui pourrait laisser croire le contraire.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
ISSUES=0
say()  { printf "%s\n" "${BOLD}$*${OFF}"; }
ok()   { printf "%s\n" "${GREEN}  ✓ $*${OFF}"; }
warn() { printf "%s\n" "${YELLOW}  ! $*${OFF}"; ISSUES=$((ISSUES + 1)); }
fail() { printf "%s\n" "${RED}  ✗ $*${OFF}"; ISSUES=$((ISSUES + 1)); }

say "FEBA — make doctor"
echo ""

# ── Prérequis ────────────────────────────────────────────────────────
say "Prérequis"
command -v docker >/dev/null 2>&1 && ok "docker présent ($(docker --version 2>/dev/null))" \
  || fail "docker introuvable — https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 && ok "docker compose (plugin v2) présent" \
  || fail "docker compose v2 introuvable (le plugin, pas 'docker-compose' v1)"
docker info >/dev/null 2>&1 && ok "le démon Docker répond" \
  || fail "le démon Docker ne répond pas — démarrez Docker Desktop / dockerd"
command -v openssl >/dev/null 2>&1 && ok "openssl présent (génération des secrets)" \
  || fail "openssl introuvable — requis pour générer les secrets Jitsi"
echo ""

# ── Fichier .env réellement utilisé ─────────────────────────────────
say "Fichiers d'environnement"
if [ -L ".env.dev" ] && [ ! -e ".env.dev" ]; then
  fail ".env.dev est un lien symbolique CASSÉ (cible absente)"
elif [ -f ".env.dev" ]; then
  ok ".env.dev présent — c'est le fichier que docker-compose.yml charge réellement"
else
  warn ".env.dev absent — 'make install' le créera depuis .env.dev.example"
fi

if [ -f ".env" ] && [ ! -L ".env" ]; then
  warn ".env existe aussi, à la racine — AUCUN service ne le charge (docker-compose.yml lit .env.dev)." \
       " Si vous y avez mis des valeurs à la main, elles sont ignorées : reportez-les dans .env.dev."
fi

if [ -f ".env.jitsi" ]; then
  ok ".env.jitsi présent"
else
  warn ".env.jitsi absent — 'make install' le créera (secrets Jitsi générés automatiquement)"
fi
echo ""

# ── Cohérence des variables (si .env.dev existe) ────────────────────
if [ -f ".env.dev" ]; then
  say "Cohérence de .env.dev"

  # Base de données : DATABASE_URL doit pointer vers le service Docker
  # (« postgres-dev »), pas vers localhost — depuis l'INTÉRIEUR d'un
  # conteneur, localhost désigne le conteneur lui-même, pas Postgres.
  DB_URL="$(grep -E '^DATABASE_URL=' .env.dev | tail -1 | cut -d= -f2-)"
  if [ -z "$DB_URL" ]; then
    warn "DATABASE_URL absent de .env.dev"
  elif echo "$DB_URL" | grep -qE '@(localhost|127\.0\.0\.1)[:/]'; then
    fail "DATABASE_URL pointe vers localhost — depuis backend-dev, ce n'est pas Postgres." \
         " Utilisez l'hôte du service Docker : postgres-dev."
  else
    ok "DATABASE_URL pointe hors de localhost"
  fi

  # Redis : même remarque.
  REDIS_URL="$(grep -E '^REDIS_URL=' .env.dev | tail -1 | cut -d= -f2-)"
  if [ -z "$REDIS_URL" ]; then
    warn "REDIS_URL absent de .env.dev"
  elif echo "$REDIS_URL" | grep -qE '://(localhost|127\.0\.0\.1)[:/]'; then
    fail "REDIS_URL pointe vers localhost — depuis backend-dev/celery-dev, utilisez redis-dev."
  else
    ok "REDIS_URL pointe hors de localhost"
  fi

  # Courrier : backend local (console/locmem/filebased) sans que Mailpit
  # soit ciblé = tout « Envoyer » échouera par conception (voir
  # apps/monthly_reports/emails.py — LOCAL_BACKENDS). Ce n'est pas une
  # erreur en soi, mais si Mailpit tourne et n'est pas utilisé, personne
  # ne peut vérifier un envoi.
  EMAIL_BACKEND_VAL="$(grep -E '^EMAIL_BACKEND=' .env.dev | tail -1 | cut -d= -f2-)"
  EMAIL_HOST_VAL="$(grep -E '^EMAIL_HOST=' .env.dev | tail -1 | cut -d= -f2-)"
  case "$EMAIL_BACKEND_VAL" in
    *console.EmailBackend*|*locmem.EmailBackend*|*dummy.EmailBackend*)
      warn "EMAIL_BACKEND=$EMAIL_BACKEND_VAL — Mailpit tourne mais n'est pas utilisé." \
           " Un clic sur « Envoyer » échouera intentionnellement (message capturé, jamais un mensonge de succès)." \
           " Pour utiliser Mailpit : EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend, EMAIL_HOST=mailpit, EMAIL_PORT=1025."
      ;;
    *smtp.EmailBackend*)
      if [ "$EMAIL_HOST_VAL" = "mailpit" ]; then
        ok "EMAIL_BACKEND est en SMTP vers mailpit — les envois seront vérifiables sur http://localhost:8025"
      else
        ok "EMAIL_BACKEND est en SMTP vers ${EMAIL_HOST_VAL:-<EMAIL_HOST non défini>}"
      fi
      ;;
    "")
      warn "EMAIL_BACKEND absent de .env.dev (Django utilisera le backend console par défaut)"
      ;;
  esac

  # Jitsi : le navigateur et le backend ne doivent PAS viser la même URL
  # quand elle contient « localhost » — depuis le conteneur backend,
  # localhost désigne le conteneur lui-même, jamais Jitsi (P7).
  JITSI_PUBLIC="$(grep -E '^JITSI_PUBLIC_URL=' .env.jitsi 2>/dev/null | tail -1 | cut -d= -f2-)"
  JITSI_INTERNAL="$(grep -E '^JITSI_INTERNAL_URL=' .env.dev | tail -1 | cut -d= -f2-)"
  if [ -n "$JITSI_PUBLIC" ] && [ -z "$JITSI_INTERNAL" ]; then
    warn "JITSI_INTERNAL_URL absent de .env.dev — le backend risque d'utiliser JITSI_PUBLIC_URL" \
         " ($JITSI_PUBLIC_URL), injoignable depuis l'intérieur d'un conteneur. Voir 'make jitsi-health'."
  elif [ -n "$JITSI_INTERNAL" ] && echo "$JITSI_INTERNAL" | grep -qE '^https?://localhost'; then
    fail "JITSI_INTERNAL_URL=$JITSI_INTERNAL — localhost, depuis backend-dev, ne désigne PAS Jitsi."
  elif [ -n "$JITSI_INTERNAL" ]; then
    ok "JITSI_INTERNAL_URL est distinct de localhost ($JITSI_INTERNAL)"
  fi

  # Permissions : un fichier de secrets lisible par tous sur un poste
  # partagé est un vrai risque, pas un détail.
  PERMS="$(stat -c '%a' .env.dev 2>/dev/null || stat -f '%Lp' .env.dev 2>/dev/null || echo '')"
  if [ -n "$PERMS" ] && [ "$PERMS" != "600" ] && [ "$PERMS" != "640" ]; then
    warn ".env.dev a les permissions $PERMS (recommandé : 600) — chmod 600 .env.dev"
  fi
fi
echo ""

# ── Résumé ───────────────────────────────────────────────────────────
if [ "$ISSUES" -eq 0 ]; then
  say "${GREEN}✅ Aucun problème détecté.${OFF}"
  exit 0
else
  say "${YELLOW}⚠ $ISSUES point(s) à vérifier ci-dessus.${OFF}"
  exit 1
fi
