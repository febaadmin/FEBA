#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# Sûreté du dépôt : rien de secret, rien d'inutile.
#
# Ce contrôle tourne en CI sur chaque Pull Request. Il cherche ce qui ne
# doit jamais entrer dans le dépôt — un .env réel, une clé privée, un
# dump de base — et ce qui ne doit jamais y rester : node_modules, caches,
# journaux, artefacts de compilation.
#
# Il distingue explicitement les valeurs de DÉVELOPPEMENT, qui sont
# publiques par construction (mot de passe « feba_dev_pass » d'une base
# jetable), des vrais secrets. Confondre les deux rendrait le contrôle
# inutilisable : il crierait à chaque exécution, et on cesserait de le lire.
#
# Sortie 0 si le dépôt est sain, 1 sinon.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
FAILURES=0

ok()   { printf '  %sOK%s    %s\n' "$GREEN" "$OFF" "$1"; }
bad()  { printf '  %sÉCHEC%s %s\n' "$RED" "$OFF" "$1"; FAILURES=$((FAILURES+1)); }
note() { printf '  %sNOTE%s  %s\n' "$YELLOW" "$OFF" "$1"; }

# Fichiers réellement versionnés. Hors dépôt git (archive extraite), on
# retombe sur un parcours du disque en excluant ce qui n'est jamais livré.
if git rev-parse --git-dir >/dev/null 2>&1; then
  FILES="$(git ls-files)"
  SOURCE="fichiers suivis par git"
else
  FILES="$(find . -type f \
            -not -path './.git/*' \
            -not -path './frontend/node_modules/*' \
            -not -path '*/__pycache__/*' \
            -not -path './backend/venv/*' -not -path './backend/.venv/*' \
            | sed 's|^\./||')"
  SOURCE="parcours du disque (hors dépôt git)"
fi
printf '%sSûreté du dépôt%s  (%s)\n\n' "$BOLD" "$OFF" "$SOURCE"

# ── 1. Fichiers de configuration réels ───────────────────────────────
printf '%sFichiers de configuration%s\n' "$BOLD" "$OFF"
REAL_ENV="$(printf '%s\n' "$FILES" | grep -E '(^|/)\.env($|\.)' | grep -vE '\.example$' || true)"
if [ -n "$REAL_ENV" ]; then
  bad "fichiers .env réels présents :"; printf '        %s\n' $REAL_ENV
else
  ok "aucun .env réel (seuls des .env.*.example)"
fi

# ── 2. Clés privées et certificats ───────────────────────────────────
printf '\n%sClés et certificats%s\n' "$BOLD" "$OFF"
KEYS="$(printf '%s\n' "$FILES" | grep -E '\.(pem|key|p12|pfx|jks|keystore)$' || true)"
[ -n "$KEYS" ] && { bad "clés/certificats versionnés :"; printf '        %s\n' $KEYS; } \
               || ok "aucune clé privée ni certificat versionné"

INLINE="$(printf '%s\n' "$FILES" | xargs -r grep -lE 'BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY' 2>/dev/null || true)"
[ -n "$INLINE" ] && { bad "clé privée en clair dans :"; printf '        %s\n' $INLINE; } \
                 || ok "aucune clé privée en clair dans un fichier"

# ── 3. Secrets affectés en dur ───────────────────────────────────────
#
# On cible les AFFECTATIONS à valeur longue et non documentaire. Les
# valeurs de développement connues sont écartées nommément : elles sont
# publiques par construction, et les signaler noierait les vraies.
printf '\n%sSecrets en dur%s\n' "$BOLD" "$OFF"
SUSPECT="$(printf '%s\n' "$FILES" \
  | grep -E '\.(py|js|jsx|ts|tsx|yml|yaml|sh|conf|env)$' \
  | grep -vE '\.example$' \
  | xargs -r grep -nEI "(SECRET_KEY|_SECRET|_PASSWORD|_TOKEN|API_KEY)[[:space:]]*[=:][[:space:]]*['\"][A-Za-z0-9/+_-]{24,}['\"]" 2>/dev/null \
  | grep -vE 'feba_dev_pass|dev-secret-key-not-for-production|ci-secret-key-not-for-production' \
  | grep -vE 'CHANGE_ME|<[^>]+>|xxx+|\.\.\.|example|placeholder' \
  | grep -vE '(^|[:/])tests?/' \
  | grep -vE 'config\(|os\.environ|getenv' \
  `# Constantes LISIBLES en capitales-tirets (ex. « DELETE-PREVIOUS-USAGE-DATA »).` \
  `# Ce sont des phrases de confirmation, pas des secrets : aucune entropie,` \
  `# et tout leur intérêt est d'être lisibles. Les signaler ferait crier ce` \
  `# contrôle à chaque exécution — et on cesserait de le lire.` \
  | grep -vE "[=:][[:space:]]*['\"][A-Z][A-Z0-9]*(-[A-Z0-9]+)+['\"]" || true)"
if [ -n "$SUSPECT" ]; then
  bad "affectations suspectes :"; printf '        %s\n' "$SUSPECT"
else
  ok "aucun secret en dur (valeurs de développement identifiées, écartées)"
fi

# ── 4. Artefacts qui n'ont rien à faire dans un dépôt ────────────────
printf '\n%sArtefacts%s\n' "$BOLD" "$OFF"
ARTEFACTS=0
for motif in 'node_modules/' '__pycache__/' '\.pyc$' '\.pyo$' \
             '^backend/venv/' '^backend/\.venv/' '\.log$' \
             '\.sqlite3$' '\.dump$' '\.sql\.gz$' '^frontend/dist/' \
             '^backend/staticfiles/' '\.DS_Store$'; do
  HITS="$(printf '%s\n' "$FILES" | grep -E "$motif" | head -5 || true)"
  if [ -n "$HITS" ]; then
    bad "« $motif » présent :"; printf '        %s\n' $HITS
    ARTEFACTS=$((ARTEFACTS+1))
  fi
done
# Compteur LOCAL : le verdict de cette section ne doit pas dépendre des
# précédentes, sinon un échec plus haut la fait passer sous silence.
[ "$ARTEFACTS" -eq 0 ] && ok "aucun cache, dépendance, journal ni base locale"

# ── 5. Données personnelles ──────────────────────────────────────────
printf '\n%sDonnées personnelles%s\n' "$BOLD" "$OFF"
PRIV="$(printf '%s\n' "$FILES" | grep -E '^backend/(private_)?media/' || true)"
[ -n "$PRIV" ] && { bad "documents d'utilisateurs versionnés :"; printf '        %s\n' $PRIV; } \
               || ok "aucun document d'élève ou de famille versionné"

# ── 6. Le .gitignore couvre-t-il ce qu'il doit ? ─────────────────────
printf '\n%sCouverture du .gitignore%s\n' "$BOLD" "$OFF"
MISSING=""
for motif in '.env' 'node_modules' '__pycache__' 'private_media' 'staticfiles'; do
  grep -qF "$motif" .gitignore 2>/dev/null || MISSING="$MISSING $motif"
done
[ -n "$MISSING" ] && note "motifs absents du .gitignore :$MISSING" \
                  || ok ".gitignore couvre .env, node_modules, caches, médias privés"

printf '\n'
if [ "$FAILURES" -gt 0 ]; then
  printf '%s%d problème(s) de sûreté%s\n' "$RED" "$FAILURES" "$OFF"
  exit 1
fi
printf '%sDépôt sain%s\n' "$GREEN" "$OFF"
exit 0
