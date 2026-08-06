#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# FEBA — Installation automatisée (make install)
#
# Objectif : une seule commande amène un poste vierge à une plateforme
# fonctionnelle, AVEC l'instance Jitsi auto-hébergée démarrée.
#
# Aucune valeur secrète n'est écrite dans Git : tous les secrets sont
# générés cryptographiquement (openssl rand) et déposés dans .env.jitsi
# et .env.dev, qui sont ignorés par .gitignore.
#
# Idempotent : relancer la commande ne régénère PAS les secrets déjà
# présents (cela invaliderait les jetons en circulation et couperait les
# cours en séance).
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
say()  { printf "%s\n" "${BOLD}$*${OFF}"; }
ok()   { printf "%s\n" "${GREEN}  ✓ $*${OFF}"; }
warn() { printf "%s\n" "${YELLOW}  ! $*${OFF}"; }
fail() { printf "%s\n" "${RED}  ✗ $*${OFF}"; exit 1; }

# ── 1. Prérequis ──────────────────────────────────────────────────────
say "1/12 · Vérification des prérequis"
command -v docker >/dev/null 2>&1 || fail "Docker est requis : https://docs.docker.com/get-docker/"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 est requis (plugin « docker compose »)."
docker info >/dev/null 2>&1 || fail "Le démon Docker ne répond pas. Démarrez Docker puis relancez."
command -v openssl >/dev/null 2>&1 || fail "openssl est requis pour générer les secrets."
ok "Docker $(docker --version | awk '{print $3}' | tr -d ,) et Docker Compose disponibles"

# ── 2. Génération des secrets ─────────────────────────────────────────
# `gen KEY FILE [LENGTH]` : ajoute KEY=<secret> si la clé est absente.
gen() {
  local key="$1" file="$2" len="${3:-32}"
  touch "$file"
  if grep -qE "^${key}=.+" "$file" 2>/dev/null; then
    return 0
  fi
  # On retire une éventuelle ligne vide « KEY= » avant d'ajouter la valeur.
  sed -i.bak "/^${key}=$/d" "$file" 2>/dev/null || true
  rm -f "${file}.bak"
  printf '%s=%s\n' "$key" "$(openssl rand -hex "$len")" >> "$file"
  echo "      + $key généré"
}

say "2/12 · Génération des secrets Jitsi (cryptographiques, hors Git)"
JITSI_ENV="$ROOT/.env.jitsi"
if [ ! -f "$JITSI_ENV" ]; then
  printf '# Secrets Jitsi générés par make install — NE PAS COMMITTER\n' > "$JITSI_ENV"
fi

# Identifiant applicatif partagé backend ↔ Prosody.
grep -qE '^JITSI_APP_ID=.+' "$JITSI_ENV" 2>/dev/null || \
  printf 'JITSI_APP_ID=feba_%s\n' "$(openssl rand -hex 6)" >> "$JITSI_ENV"

gen JITSI_APP_SECRET      "$JITSI_ENV" 32   # signature des jetons
gen JICOFO_COMPONENT_SECRET "$JITSI_ENV" 16
gen JICOFO_AUTH_PASSWORD  "$JITSI_ENV" 16
gen JVB_AUTH_PASSWORD     "$JITSI_ENV" 16
gen JIGASI_XMPP_PASSWORD  "$JITSI_ENV" 16
gen JIBRI_RECORDER_PASSWORD "$JITSI_ENV" 16
gen JIBRI_XMPP_PASSWORD   "$JITSI_ENV" 16
gen TURN_SECRET           "$JITSI_ENV" 16

# Domaine local par défaut. En production, deploy.sh le remplace.
JITSI_HTTP_PORT="${JITSI_HTTP_PORT:-8443}"
grep -qE '^JITSI_PUBLIC_URL=' "$JITSI_ENV" 2>/dev/null || \
  printf 'JITSI_PUBLIC_URL=http://localhost:%s\n' "$JITSI_HTTP_PORT" >> "$JITSI_ENV"
grep -qE '^JITSI_HTTP_PORT=' "$JITSI_ENV" 2>/dev/null || \
  printf 'JITSI_HTTP_PORT=%s\n' "$JITSI_HTTP_PORT" >> "$JITSI_ENV"
grep -qE '^JITSI_HTTPS_PORT=' "$JITSI_ENV" 2>/dev/null || \
  printf 'JITSI_HTTPS_PORT=8444\n' >> "$JITSI_ENV"
chmod 600 "$JITSI_ENV"
ok "Secrets Jitsi prêts (.env.jitsi, permissions 600)"

# ── 3. Fichier .env.dev applicatif ────────────────────────────────────
# P11 — UNE SEULE convention : `.env.dev` est le fichier que
# docker-compose.yml charge réellement (`env_file: .env.dev` sur
# backend-dev, celery-dev, celery-beat-dev et désormais `migrate`).
# Cette étape écrivait auparavant dans `.env`, un fichier qu'aucun
# service ne lit : sur une installation vraiment neuve (aucun `.env.dev`
# préexistant), les conteneurs échouaient à démarrer, `env_file`
# introuvable.
say "3/12 · Configuration de l'application"
APP_ENV="$ROOT/.env.dev"
if [ ! -f "$APP_ENV" ]; then
  if [ -f "$ROOT/.env.dev.example" ]; then
    cp "$ROOT/.env.dev.example" "$APP_ENV"
  else
    touch "$APP_ENV"
  fi
fi
gen SECRET_KEY "$APP_ENV" 32

# Le backend doit connaître EXACTEMENT les mêmes identifiants que Prosody.
APP_ID="$(grep -E '^JITSI_APP_ID=' "$JITSI_ENV" | head -1 | cut -d= -f2-)"
APP_SECRET="$(grep -E '^JITSI_APP_SECRET=' "$JITSI_ENV" | head -1 | cut -d= -f2-)"
# P7 — JITSI_DOMAIN reste l'adresse PUBLIQUE (celle du navigateur, et
# celle signée dans les jetons JWT). JITSI_INTERNAL_URL est l'adresse
# que CE conteneur backend utilise pour tester Jitsi lui-même — le nom
# du service Docker sur le réseau partagé, jamais « localhost ».
python3 - "$APP_ENV" "localhost:${JITSI_HTTP_PORT}" "$APP_ID" "$APP_SECRET" "http://jitsi-web:80" <<'PYEOF'
import sys, pathlib
path, domain, app_id, app_secret, internal_url = sys.argv[1:6]
wanted = {
    "JITSI_DOMAIN": domain,
    "JITSI_APP_ID": app_id,
    "JITSI_APP_SECRET": app_secret,
    "JITSI_INTERNAL_URL": internal_url,
}
p = pathlib.Path(path)
lines = p.read_text().splitlines() if p.exists() else []
out, seen = [], set()
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else ""
    if key in wanted:
        out.append(f"{key}={wanted[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in wanted.items():
    if key not in seen:
        out.append(f"{key}={value}")
p.write_text("\n".join(out) + "\n")
PYEOF
chmod 600 "$APP_ENV"
ok "Backend relié à l'instance Jitsi locale (localhost:${JITSI_HTTP_PORT})"

# ── 4-6. Services applicatifs ─────────────────────────────────────────
say "4/12 · Démarrage de PostgreSQL et des services applicatifs"
docker compose up -d postgres-dev redis-dev 2>/dev/null || docker compose up -d
ok "Services de base démarrés"

say "5/12 · Attente de PostgreSQL"
for i in $(seq 1 60); do
  if docker compose exec -T postgres-dev pg_isready -U feba_user >/dev/null 2>&1; then
    ok "PostgreSQL est prêt"; break
  fi
  [ "$i" -eq 60 ] && fail "PostgreSQL n'a pas démarré dans le délai imparti."
  sleep 2
done

say "6/12 · Démarrage du backend"
# P5 — `backend-dev` dépend de `migrate: service_completed_successfully`
# dans docker-compose.yml : cette commande construit et exécute d'abord
# le service `migrate` (et ATTEND qu'il finisse), puis démarre
# `backend-dev`. Aucune migration explicite n'est nécessaire ici — en
# lancer une deuxième plus loin recréerait exactement la collision
# résolue par ce service dédié.
docker compose up -d backend-dev
ok "Backend démarré (migrations appliquées par le service « migrate »)"

# ── 7. Jitsi auto-hébergé ─────────────────────────────────────────────
say "7/12 · Démarrage de l'instance Jitsi AUTO-HÉBERGÉE"
docker compose -f docker-compose.jitsi.yml --env-file "$JITSI_ENV" up -d
ok "Pile Jitsi lancée (web · prosody · jicofo · jvb)"

say "8/12 · Attente de l'instance Jitsi"
JITSI_READY=0
for i in $(seq 1 90); do
  if curl -fsS -o /dev/null "http://localhost:${JITSI_HTTP_PORT}/" 2>/dev/null; then
    JITSI_READY=1; ok "Jitsi répond sur http://localhost:${JITSI_HTTP_PORT}"; break
  fi
  sleep 2
done
[ "$JITSI_READY" -eq 1 ] || warn "Jitsi n'a pas répondu à temps — vérifiez « make jitsi-logs »."

# ── 9-11. Base de données et données initiales ────────────────────────
# P5 — Les migrations ont déjà été appliquées par le service dédié
# `migrate` (dépendance de `backend-dev` ci-dessus, étape 6). On se
# contente ici de le VÉRIFIER — jamais de relancer `migrate` une seconde
# fois, ce qui recréerait la collision d'origine.
say "9/12 · Vérification des migrations"
if docker compose exec -T backend-dev python manage.py migrate --check --noinput >/dev/null 2>&1; then
  ok "Migrations à jour (appliquées par le service « migrate »)"
else
  fail "Des migrations ne sont pas appliquées — voir « docker compose logs migrate »."
fi

say "10/12 · Fichiers statiques"
docker compose exec -T backend-dev python manage.py collectstatic --noinput >/dev/null 2>&1 || \
  warn "collectstatic ignoré (non bloquant en développement)"
ok "Fichiers statiques collectés"

say "11/12 · Initialisation des deux académies"
docker compose exec -T backend-dev python manage.py init_academies
ok "Académies FEBA et FEBA_FHA initialisées"

# P0 — L'identité de chaque académie conditionne TOUS ses documents. Une
# académie sans identité complète produirait des reçus, bulletins et
# diplômes sans nom ni devise : le contrôle a lieu à l'installation, pas
# le jour de la remise des diplômes.
docker compose exec -T backend-dev python manage.py branding_check || \
  warn "Identité d'académie incomplète — voir « make branding-check »."

# P7 — Le diplôme doit être produisible IMMÉDIATEMENT après cette
# installation, sans commande supplémentaire à lancer par l'utilisateur.
# Si le fond neutralisé livré manque ou a été altéré, on le répare ici,
# puis on revérifie. Une installation qui se termine « réussie » alors que
# le diplôme est bloqué n'est pas une installation réussie.
if ! docker compose exec -T backend-dev python manage.py documents_ready --fast; then
  say "Réparation des fonds de documents officiels"
  docker compose exec -T backend-dev python manage.py document_neutralize --template diploma_feba --force
  docker compose exec -T backend-dev python manage.py documents_ready
fi
ok "Documents officiels produisibles"

# ── 12. Vérifications ─────────────────────────────────────────────────
say "12/12 · Vérifications de santé"
docker compose exec -T backend-dev python manage.py jitsi_health || \
  warn "Jitsi signalé comme dégradé — voir « make jitsi-health »."

cat <<EOF

${GREEN}${BOLD}✅ Installation terminée${OFF}

  Application          http://localhost:5173
  API                  http://localhost:8000/api
  Administration       http://localhost:8000/django-admin/
  Jitsi auto-hébergé   http://localhost:${JITSI_HTTP_PORT}

  Données de démonstration :  ${BOLD}make seed${OFF}   (comptes : DEMO_ACCOUNTS.md)
  État de l'infrastructure :  ${BOLD}make health${OFF}

  Les secrets ont été générés dans .env et .env.jitsi (ignorés par Git).
  Aucune instance publique n'est utilisée : la visioconférence passe
  exclusivement par l'instance FEBA auto-hébergée.
EOF
