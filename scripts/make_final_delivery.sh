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
NOM="${1:-FEBA_VERSION_CORRIGEE_AUDIT_COMPLET}"
SORTIE="${2:-$(dirname "$ROOT")}"
STAGE="$(mktemp -d)"
# Le dossier racine porte le MÊME nom que l'archive. En V8 il était
# resté « feba_v6_… » dans une archive « …_production_ready.zip » : deux
# noms pour une seule livraison, et une ambiguïté de plus au moment de
# réintégrer le dépôt.
CIBLE="$STAGE/$NOM"

trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$CIBLE"

# ── Source de l'archive ───────────────────────────────────────────────
# Dans un dépôt Git, l'archive est construite depuis le COMMIT courant
# (`git archive HEAD`) : elle contient exactement la version validée, et
# rien de ce que les tests ou un poste de développement laissent traîner
# (médias générés, bases SQLite, captures, caches). Un arbre de travail
# modifié est refusé : on ne livre pas un état qui n'existe nulle part
# dans l'historique.
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -n "$(git -C "$ROOT" status --porcelain --untracked-files=no)" ]; then
    echo "ÉCHEC : modifications non validées dans le dépôt — validez-les avant de livrer."
    git -C "$ROOT" status --short --untracked-files=no
    exit 1
  fi
  echo "Source : commit $(git -C "$ROOT" rev-parse --short HEAD) ($(git -C "$ROOT" rev-parse --abbrev-ref HEAD))"
  git -C "$ROOT" archive --format=tar HEAD | tar -xf - -C "$CIBLE"
  git -C "$ROOT" log -1 --format='commit %H%nbranche '"$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"'%ndate %ci%n%s' > "$CIBLE/SOURCE_COMMIT.txt"
else
tar -C "$ROOT" \
    --exclude='./.git' \
    --exclude='./.claude' \
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
    --exclude='*.sqlite3' \
    --exclude='*.log' \
    --exclude='./.env' \
    --exclude='./.env.dev' \
    --exclude='./.env.prod' \
    --exclude='./.env.jitsi' \
    --exclude='./.env.local' \
    --exclude='./backend/.env' \
    --exclude='.DS_Store' \
    -cf - . | tar -xf - -C "$CIBLE"
fi

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
              FINAL_REPORT.md .env.example .env.prod.example \
              .env.dev.example .env.jitsi.example \
              backend/tests/repo_root.py \
              docker-compose.jitsi.behind-proxy.yml \
              nginx/sites-available/meet.globalfeba.com.conf \
              nginx/sites-enabled/.gitkeep \
              scripts/repo_safety_check.sh scripts/compose_config_check.sh \
              .github/workflows/ci.yml .github/workflows/deploy.yml \
              backend/apps/schools/academic_year.py \
              backend/apps/schools/migrations/0016_activate_orphan_school_years.py \
              backend/apps/classes/migrations/0003_class_language_track.py \
              backend/apps/virtualclass/migrations/0003_virtualroom_target_roles.py \
              backend/tests/test_v10_academy_scope_and_rooms.py \
              backend/tests/test_bulletin_language_track.py \
              frontend/src/pages/shared/VirtualRoomSession.jsx \
              frontend/src/pages/shared/VirtualRoomSession.test.jsx \
              frontend/src/pages/shared/VirtualRooms.test.jsx \
              frontend/src/components/JitsiMeeting.test.jsx \
              V10_REPORT.md JITSI_AUDIT_REPORT.md \
              CLASS_LANGUAGE_MODEL_REPORT.md MULTI_ACADEMY_AUDIT.md \
              VIRTUAL_CLASS_REPORT.md TEST_REPORT_V10.md \
              KNOWN_LIMITATIONS_V10.md MANUAL_PRODUCTION_ACTIONS_V10.md \
              docs/v10-parcours/README.md docs/v10-parcours/parcours.mjs \
              backend/apps/classes/subject_rules.py \
              backend/apps/classes/migrations/0004_audit_language_tracks.py \
              backend/tests/test_v11_class_language_rules.py \
              backend/tests/test_v11_jitsi_moderators_and_jwt.py \
              backend/tests/test_v11_jitsi_health_checks.py \
              frontend/src/utils/classLanguage.js \
              frontend/src/utils/classLanguage.test.js \
              CLASS_TYPE_BUSINESS_RULES_REPORT.md \
              FEBA_FHA_CLASS_VALIDATION_REPORT.md \
              DEPLOYMENT_CHECKLIST.md \
              jitsi/nginx-custom/feba-security-headers.conf \
              backend/tests/test_v12_jitsi_production_headers.py \
              JITSI_PRODUCTION_ACTIONS.md JITSI_REAL_WORLD_TEST_PLAN.md \
              TURN_DECISION.md JITSI_PRODUCTION_FINAL_REPORT.md \
              scripts/deploy_production.sh scripts/production_health.sh \
              backend/tests/test_v13_deploiement_production.py \
              ROLLBACK_GUIDE.md PRODUCTION_CHECKLIST.md \
              TURN_DEPLOYMENT_GUIDE.md \
              EMAIL_CONFIGURATION_GUIDE.md PAYMENT_REMINDERS_GUIDE.md \
              AUDIT_CORRECTIONS_REPORT.md VALIDATION_REPORT.md \
              backend/apps/core/age.py \
              backend/apps/notifications/campaigns.py \
              backend/apps/notifications/campaign_models.py \
              backend/apps/notifications/tasks.py \
              backend/apps/payments/reminders.py \
              backend/apps/payments/schedule_models.py \
              backend/apps/payments/fee_plans/feba_2026_2027.json \
              backend/apps/payments/management/commands/load_fee_plan.py \
              backend/apps/payments/migrations/0011_backfill_payment_paid_at.py \
              backend/apps/payments/migrations/0013_optional_services_not_mandatory.py \
              backend/tests/test_audit_p1_student_age.py \
              backend/tests/test_audit_p1_payment_datetime.py \
              backend/tests/test_audit_p1_mass_email.py \
              backend/tests/test_audit_p1_payment_reminders.py \
              backend/tests/test_audit_p1_confirmation_emails.py \
              backend/tests/test_audit_cross_academy_writes.py \
              backend/tests/test_audit_role_escalation.py \
              frontend/src/pages/admin/MassEmail.jsx \
              frontend/src/pages/admin/PaymentReminders.jsx \
              frontend/src/utils/age.jsx frontend/src/utils/datetime.js; do
  [ -e "$CIBLE/$requis" ] || { echo "  ÉCHEC : « $requis » manquant"; exit 1; }
done
echo "  OK    tous les fichiers attendus sont présents"

# Les scripts doivent rester EXÉCUTABLES à travers l'archive : un test
# vérifie leur bit +x, et « zip » le préserve sur Unix — mais seulement
# si les fichiers l'ont au départ.
for script in "$CIBLE"/scripts/*.sh; do
  [ -f "$script" ] && chmod +x "$script"
done
non_exec="$(find "$CIBLE/scripts" -name '*.sh' ! -perm -u+x -print 2>/dev/null)"
if [ -n "$non_exec" ]; then
  echo "  ÉCHEC : scripts non exécutables :"; echo "$non_exec"; exit 1
fi
echo "  OK    tous les scripts .sh sont exécutables"

# Empreinte de CHAQUE fichier du projet, déposée dans l'archive. Elle
# permet de vérifier un fichier isolé après extraction, là où l'empreinte
# de l'archive ne dit que « intacte ou non » en bloc.
#
# Le fichier s'exclut lui-même du calcul : s'y inclure changerait son
# contenu et invaliderait sa propre ligne.
(cd "$CIBLE" && find . -type f ! -name SHA256SUMS.txt -print0 \
   | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
echo "  OK    SHA256SUMS.txt ($(wc -l < "$CIBLE/SHA256SUMS.txt") fichiers)"

ARCHIVE="$SORTIE/${NOM}.zip"
rm -f "$ARCHIVE"
(cd "$STAGE" && zip -qr "$ARCHIVE" "$NOM")

# Empreinte déposée À CÔTÉ de l'archive : un fichier ne peut pas contenir
# sa propre empreinte (l'y écrire la changerait). SHA256SUMS.txt, à
# l'intérieur, couvre les fichiers du projet.
sha256sum "$ARCHIVE" | sed "s#$SORTIE/##" > "$ARCHIVE.sha256"

echo ""
echo "Archive : $ARCHIVE"
echo "Taille  : $(du -h "$ARCHIVE" | cut -f1) ($(wc -c < "$ARCHIVE" | tr -d ' ') octets)"
echo "SHA-256 : $(sha256sum "$ARCHIVE" | cut -d' ' -f1)"
echo "Fichiers: $(unzip -l "$ARCHIVE" | tail -1 | awk '{print $2}')"
echo "Empreinte déposée dans : $ARCHIVE.sha256"
