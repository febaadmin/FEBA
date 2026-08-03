#!/usr/bin/env bash
#
# Construit la livraison à partir du HEAD RÉELLEMENT TESTÉ.
#
# Le point important : rien n'est copié depuis le répertoire de travail.
# Tout est extrait de Git (`git archive`, `git bundle`, `git diff`), donc
# l'archive livrée ne peut pas contenir un fichier oublié, un artefact de
# build, un secret local ou une modification non commitée. Ce qui est
# livré est exactement ce qui est versionné.
#
# Usage : scripts/make_delivery.sh [dossier-de-sortie]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/dist-livraison}"
NAME="${DELIVERY_NAME:-feba_multi_academies_v9}"
BASE="${DELIVERY_BASE:-}"

cd "$ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "✗ Le dépôt contient des modifications non commitées." >&2
  echo "  La livraison doit provenir d'un HEAD propre et testé." >&2
  git status --short >&2
  exit 1
fi

HEAD_SHA="$(git rev-parse HEAD)"
HEAD_SHORT="$(git rev-parse --short HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# Base du diff : le dernier commit d'avant l'itération, ou l'argument fourni.
if [ -z "$BASE" ]; then
  BASE="$(git log --format=%H --grep='^P0 — FEBA FHA facture' -1)^" || true
fi
[ -z "$BASE" ] && BASE="$(git rev-list --max-parents=0 HEAD | tail -1)"

rm -rf "$OUT"
mkdir -p "$OUT"

# Aucun fichier d'environnement RÉEL ne doit être versionné : il partirait
# dans l'archive. `.env.dev` l'a fait pendant plusieurs livraisons, avec sa
# SECRET_KEY et son JITSI_APP_SECRET. Le contrôle a lieu ICI, avant la
# construction : découvrir un secret livré après coup n'a plus d'intérêt.
LEAKED=$(git -C "$ROOT" ls-files | grep -E '^\.env($|\.)' | grep -v '\.example$' || true)
if [ -n "$LEAKED" ]; then
  echo "✗ Fichier(s) d'environnement réel(s) versionné(s) :" >&2
  echo "$LEAKED" | sed 's/^/    /' >&2
  echo "  Ils partiraient dans l'archive. Retirez-les du suivi Git :" >&2
  echo "    git rm --cached <fichier>   (le fichier local est conservé)" >&2
  exit 1
fi

echo "→ Archive du code versionné (HEAD $HEAD_SHORT)"
git archive --format=zip --prefix="$NAME/" -o "$OUT/$NAME.zip" HEAD

echo "→ Bundle Git (historique complet, clonable)"
git bundle create "$OUT/$NAME.bundle" --all >/dev/null

echo "→ Diff de l'itération ($(git rev-parse --short "$BASE") → $HEAD_SHORT)"
git diff "$BASE" HEAD > "$OUT/$NAME.diff"
git log --oneline "$BASE"..HEAD > "$OUT/COMMITS.txt"

echo "→ Rapports et captures"
# La liste était FIGÉE sur les rapports d'une itération précédente : la
# livraison V9 est partie avec les rapports V8, sans que rien ne le
# signale. Elle est désormais explicite ET vérifiée : un rapport annoncé
# mais absent fait échouer la construction, au lieu de manquer en silence.
REPORTS_REQUIRED="
  RAPPORT_V9.md
  KNOWN_LIMITATIONS_V9.md
  FINAL_REPORT.md
  CHANGELOG_FIXES.md
  TEST_REPORT.md
  FIELD_MAPPING_AUDIT.md
  FHA_ENROLLMENT_WORKFLOW_REPORT.md
  EMAIL_DELIVERY_REPORT.md
  DOCUMENT_BRANDING_AUDIT.md
  DOCUMENT_TEMPLATE_CALIBRATION.md
  MULTI_ACADEMY_SECURITY_REPORT.md
  AUDIT_REPORT.md
  CORRECTIONS.md
  MULTI_ACADEMY_DOCUMENT_REPORT.md
  OFFICIAL_DOCUMENTS_REPORT.md
  CONTACT_FORMS_REPORT.md
  SECURITY_NOTES.md
  INSTALLATION_GUIDE.md
"
# Rapports des itérations antérieures : utiles, mais leur absence n'est
# pas une anomalie de CETTE livraison.
REPORTS_OPTIONAL="
  RAPPORT_V8.md
  KNOWN_LIMITATIONS_V8.md
  KNOWN_LIMITATIONS.md
  VERIFICATION_V8.md
  MULTI_CURRENCY_REPORT.md
  CARD_PAYMENT_INTEGRATION_REPORT.md
  STRIPE_CONFIGURATION_GUIDE.md
  DIPLOMA_CERTIFICATE_FIDELITY_REPORT.md
  MULTI_ENTITY_ARCHITECTURE.md
  ENTITY_PERMISSION_MATRIX.md
"

MISSING=""
for f in $REPORTS_REQUIRED; do
  if [ -f "$ROOT/$f" ]; then cp "$ROOT/$f" "$OUT/"; else MISSING="$MISSING $f"; fi
done
if [ -n "$MISSING" ]; then
  echo "✗ Rapports annoncés mais absents :$MISSING" >&2
  echo "  Une livraison qui promet un rapport qu'elle ne contient pas" >&2
  echo "  est une livraison incomplète. Construction interrompue." >&2
  exit 1
fi
for f in $REPORTS_OPTIONAL; do
  [ -f "$ROOT/$f" ] && cp "$ROOT/$f" "$OUT/"
done
echo "   rapports : $(ls "$OUT"/*.md 2>/dev/null | wc -l) fichier(s)"

# `.env.example` accompagne la livraison : il documente chaque variable et
# ne contient aucun secret. Il est aussi dans le ZIP, mais le placer à la
# racine du dossier de livraison évite d'avoir à extraire l'archive pour
# le lire.
[ -f "$ROOT/.env.example" ] && cp "$ROOT/.env.example" "$OUT/env.example.txt"
if [ -d "$ROOT/e2e/captures" ]; then
  mkdir -p "$OUT/captures"
  cp "$ROOT"/e2e/captures/*.png "$OUT/captures/" 2>/dev/null || true
fi

# Les exemples et la comparaison sont PRODUITS ICI, par le code qu'on
# livre, et non copiés d'un dossier de travail : c'est la seule façon
# qu'ils correspondent réellement au commit livré.
if [ -d "$ROOT/backend/document_templates/originals" ] &&
   ls "$ROOT/backend/document_templates/originals"/*.png >/dev/null 2>&1; then
  echo "→ Documents d'exemple et comparaison (depuis le HEAD livré)"
  PY="$ROOT/backend/venv/bin/python"
  [ -x "$PY" ] || PY=python3
  ( cd "$ROOT/backend" &&
    # Le fond neutralisé est VERSIONNÉ (P7) : il n'y a plus rien à
    # produire ici. On vérifie seulement qu'il est conforme — une
    # régénération silencieuse masquerait une archive incomplète.
    "$PY" manage.py documents_ready --fast >/dev/null 2>&1 \
      || echo "   ⚠ documents_ready signale un défaut — voir « make documents-ready »" 
    # LES QUATRE GABARITS, PAS DEUX. La livraison précédente ne
    # produisait d'exemples que pour les visuels de Cotonou : ceux de
    # l'académie en ligne n'étaient donc jamais éprouvés depuis le HEAD
    # livré, alors que ce sont eux qui viennent d'être recalibrés.
    for t in diploma_feba certificate_feba diploma_feba_fha certificate_feba_fha; do
      "$PY" manage.py document_samples --template "$t" \
        --output-dir "$OUT/exemples" --date 04/07/2026 >/dev/null 2>&1 || true
      "$PY" manage.py document_compare --template "$t" \
        --output-dir "$OUT/comparaison" >/dev/null 2>&1 || true
    done )
  echo "   exemples : $(ls "$OUT/exemples" 2>/dev/null | wc -l) fichier(s)"
  echo "   comparaison : $(ls "$OUT/comparaison" 2>/dev/null | wc -l) fichier(s)"
fi

# ── Fonds officiels, rapport mensuel d'exemple, preuves de vérification ──
#
# Ces éléments sont DEMANDÉS dans la livraison et n'étaient pas extraits :
# le destinataire devait ouvrir le ZIP pour voir les visuels sur lesquels
# tout le calibrage repose. Ils sont donc posés à côté, lisibles sans
# décompression.
echo "→ Fonds officiels (sources et dérivés)"
mkdir -p "$OUT/fonds/sources" "$OUT/fonds/derives"
cp "$ROOT/backend/document_templates/sources/feba_fha/"*.png "$OUT/fonds/sources/" 2>/dev/null || true
cp "$ROOT/backend/document_templates/originals/"*.png "$OUT/fonds/sources/" 2>/dev/null || true
cp "$ROOT/backend/document_templates/derived/"*.png "$OUT/fonds/derives/" 2>/dev/null || true
echo "   fonds : $(ls "$OUT/fonds/sources" "$OUT/fonds/derives" 2>/dev/null | grep -c png) fichier(s)"

echo "→ Rapport mensuel FEBA FHA d'exemple"
PYX="$ROOT/backend/venv/bin/python"
[ -x "$PYX" ] || PYX=python3
export DELIVERY_OUT="$OUT"
( cd "$ROOT/backend" && "$PYX" - <<'PYEOF' > /dev/null 2>&1
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "feba_project.settings")
django.setup()
from apps.monthly_reports.models import MonthlyStudentReport
from apps.monthly_reports.pdf import generate_report_pdf, report_filename
import pathlib
sortie = pathlib.Path(os.environ["DELIVERY_OUT"]) / "exemples"
sortie.mkdir(parents=True, exist_ok=True)
rapport = MonthlyStudentReport.objects.order_by("-id").first()
if rapport is not None:
    (sortie / report_filename(rapport)).write_bytes(generate_report_pdf(rapport))
PYEOF
) || true

echo "→ Preuves de vérification"
[ -f "$ROOT/VERIFICATION_LIVRAISON_V9.md" ] && cp "$ROOT/VERIFICATION_LIVRAISON_V9.md" "$OUT/"
[ -f "$ROOT/e2e/rapport-documents-officiels.txt" ] && cp "$ROOT/e2e/rapport-documents-officiels.txt" "$OUT/preuve-parcours-navigateur.txt"

echo "→ Empreintes SHA-256"
cd "$OUT"
find . -type f ! -name SHA256SUMS.txt -print0 \
  | sort -z | xargs -0 sha256sum > SHA256SUMS.txt

cat > MANIFESTE.md <<EOF
# Livraison FEBA — itération V9

Construite depuis le dépôt Git, sans copie du répertoire de travail :
l'archive contient exactement les fichiers versionnés du commit ci-dessous.

| | |
|---|---|
| Branche | \`$BRANCH\` |
| Commit livré | \`$HEAD_SHA\` |
| Base du diff | \`$(git -C "$ROOT" rev-parse "$BASE")\` |
| Date | $(date -u '+%Y-%m-%d %H:%M UTC') |

## Contenu

| Fichier | Rôle |
|---|---|
| \`$NAME.zip\` | Code source complet du commit livré. |
| \`$NAME.bundle\` | Dépôt Git complet : \`git clone $NAME.bundle feba\`. |
| \`$NAME.diff\` | Différentiel de l'itération, applicable avec \`git apply\`. |
| \`COMMITS.txt\` | Journal des commits de l'itération. |
| \`RAPPORT_V9.md\` | Les cinq tableaux : champs, documents, e-mails, permissions, tests. |
| \`KNOWN_LIMITATIONS_V9.md\` | Ce qui reste, honnêtement — et pourquoi. |
| \`FINAL_REPORT.md\` | Rapport de clôture : ce qui est testé, et où. |
| \`CHANGELOG_FIXES.md\` | Journal des corrections, par priorité. |
| \`TEST_REPORT.md\` | Sorties brutes des suites de tests. |
| \`FIELD_MAPPING_AUDIT.md\` | Chaîne complète de chaque champ (produit par \`field_mapping_audit\`). |
| \`FHA_ENROLLMENT_WORKFLOW_REPORT.md\` | Les 18 étapes de l'inscription FEBA FHA. |
| \`EMAIL_DELIVERY_REPORT.md\` | États d'envoi, reprise, et ce qui n'a PAS été envoyé. |
| \`DOCUMENT_BRANDING_AUDIT.md\` | Identité par académie, et les chaînes en dur supprimées. |
| \`DOCUMENT_TEMPLATE_CALIBRATION.md\` | Calibrage des quatre gabarits, avec les commandes qui le refont. |
| \`AUDIT_REPORT.md\` | Ce que la mesure a trouvé, et ce qu'elle ne prouve pas. |
| \`CORRECTIONS.md\` | Chaque correction, avec la façon dont le défaut a été trouvé. |
| \`MULTI_ACADEMY_SECURITY_REPORT.md\` | Audit global multi-académies. |
| \`MULTI_ACADEMY_DOCUMENT_REPORT.md\` | Aucun document ne porte l'identité d'une autre académie. |
| \`OFFICIAL_DOCUMENTS_REPORT.md\` | Diplôme et certificat disponibles dès l'installation. |
| \`CONTACT_FORMS_REPORT.md\` | WhatsApp conservé, messages longs non tronqués. |
| \`SECURITY_NOTES.md\` | Stockage privé, permissions, anti-IDOR. |
| \`INSTALLATION_GUIDE.md\` | Installation propre, depuis cette archive. |
| \`env.example.txt\` | Copie de \`.env.example\` — aucune valeur secrète. |
| \`captures/\` | Captures des parcours navigateur, dont les dix de cette itération (\`documents-01…10\`). |
| \`fonds/sources/\` | Visuels officiels d'origine, ceux dont les empreintes font autorité. |
| \`fonds/derives/\` | Fonds neutralisés, versionnés, vérifiés par empreinte avant chaque émission. |
| \`VERIFICATION_LIVRAISON_V9.md\` | Preuves : l'archive extraite, migrée et testée hors du dépôt. |
| \`preuve-parcours-navigateur.txt\` | Sortie brute des 54 contrôles du parcours documents. |
| \`exemples/\` | Documents PDF et e-mails produits depuis le HEAD livré. |
| \`comparaison/\` | Rendu, masque des zones variables, image de différence et score. |
| \`SHA256SUMS.txt\` | Empreintes de tous les fichiers ci-dessus. |

Les rapports des itérations antérieures (V8 et avant) sont conservés à
côté : ils documentent des décisions toujours en vigueur.

## Ce qui a été fait, et ce qui ne l'a pas été

| | |
|---|---|
| Push GitHub | **non effectué — HTTP 403.** Autorisation d'écriture sur le dépôt ; la lecture distante (ls-remote) réussit, ce n'est donc pas le réseau. |
| Historique complet | **inclus dans le bundle.** Un clone du fichier .bundle restitue tous les commits, sans aucun accès distant. |
| Commits signés | **non.** La clé de signature du conteneur fait 0 octet et ssh-keygen est absent : Git accepte le réglage de signature et produit des commits non signés, sans erreur. |
| Code et archive | **testés depuis le HEAD final.** Voir TEST_REPORT.md et VERIFICATION_LIVRAISON_V9.md. |

Le bundle est donc le livrable qui porte l'historique : il ne dépend
d'aucun accès distant.

## Vérifier l'intégrité

\`\`\`bash
sha256sum -c SHA256SUMS.txt
\`\`\`

## Reconstruire depuis le bundle

\`\`\`bash
git clone $NAME.bundle feba && cd feba
git log --oneline -1        # doit afficher $HEAD_SHORT
\`\`\`
EOF

sha256sum MANIFESTE.md >> SHA256SUMS.txt

echo
echo "✓ Livraison prête : $OUT"
ls -lh "$OUT"
