# DELIVERY_MANIFEST — contenu de la livraison

## Origine

| Élément | Valeur |
|---|---|
| Dossier source | `V1` — `1zFPv27HZePcRD1wPPE4Uzmi_cO6jYM0f` |
| Archive source | `feba_multi_academies_v9_application_CORRIGE.zip` |
| Identifiant Drive | `1V4WkjR-2c8YGXDIJnzNiFiRzqM0x8Tlh` |
| SHA-256 source | `8ee116a9066314b57fbe964b351c0410fd52da0da2058bb35596f0daee59bff4` |

Aucun fichier ne provient de GitHub, d'une copie locale préexistante ni d'une
autre version. Voir `SOURCE_ARCHIVE_REPORT.md`.

## Fichiers ajoutés

| Fichier | Objet |
|---|---|
| `backend/apps/core/management/commands/clean_previous_usage_data.py` | Commande de nettoyage (P2) |
| `backend/tests/test_clean_previous_usage_data.py` | 26 tests (P2) |
| `backend/apps/website/migrations/0011_fhaenrollmentapplication_desired_plan.py` | Champ formule (P4) |
| `frontend/src/site/fhaPlans.js` | Formules et chemin du flyer (P4) |
| `frontend/public/images/feba-fha/feba-fha-flyer.jpeg` | Flyer officiel (P4) |
| `frontend/src/context/academyBoot.test.jsx` | 10 tests (P1) |
| `frontend/src/site/mobileLangSwitcher.test.jsx` | 6 tests (P9) |

## Fichiers modifiés

| Fichier | Objet |
|---|---|
| `frontend/src/context/AcademyContext.jsx` | Cycle de démarrage, déduplication (P1) |
| `frontend/src/components/AcademyScopedOutlet.jsx` | Garde de portée (P1) |
| `frontend/src/pages/superadmin/Dashboard.jsx` | Trois états, clé de portée (P1) |
| `frontend/src/api/academyScope.js` | Génération de portée, `isCanceledError` (P1) |
| `frontend/src/hooks/useAuth.js` | Nettoyage au login/logout (P1) |
| `frontend/src/i18n/translations.js` | Traduction du message d'erreur (P1) |
| `frontend/src/site/SiteLayout.jsx` | Sélecteur EN/FR mobile (P9) |
| `frontend/src/site/pages/FhaEnrollPage.jsx` | Titres d'étapes, formule, récapitulatif (P3, P4) |
| `frontend/src/site/pages/FhaPage.jsx` | Formules, flyer, cohérence tarifs (P4) |
| `backend/apps/website/models.py` | Champ `desired_plan` (P4) |
| `backend/apps/website/fha_serializers.py` | Exposition de `desired_plan` (P4) |

## Rapports

Ajoutés : `SOURCE_ARCHIVE_REPORT.md`, `ACADEMY_SCOPE_RACE_REPORT.md`,
`PREVIOUS_USAGE_CLEANUP.md`, `PREVIOUS_USAGE_MODELS_AUDIT.md`,
`FHA_PUBLIC_PAGE_REPORT.md`, `FHA_ENROLLMENT_FORM_REPORT.md`,
`FHA_ADMISSIONS_DOWNLOAD_REPORT.md`, `MONTHLY_REPORTS_FIX.md`,
`RESPONSIVE_I18N_REPORT.md`, `INSTALLATION.md`, `DELIVERY_MANIFEST.md`.

Réécrits pour ce cycle : `CORRECTIONS.md`, `TEST_REPORT.md`,
`KNOWN_LIMITATIONS.md`.

Conservés de l'archive source : `README.md`, `AUDIT_REPORT.md`,
`SECURITY_NOTES.md`, `MULTI_CURRENCY_REPORT.md`, `SCHEDULE_PARITY_REPORT.md`,
`CHANGELOG_FIXES.md`, `RESTORE_GUIDE.md` et les rapports historiques.

## Exclusions de l'archive livrée

Retirés avant compression : `node_modules/`, `frontend/dist/`,
environnements virtuels, `__pycache__/`, `.pytest_cache/`, `*.pyc`,
bases SQLite locales, logs, fichiers temporaires, `.git/`.

Aucun fichier `.env` réel n'était présent dans l'archive source et aucun n'a
été ajouté : seuls les `*.example` sont livrés.

## Résultats de test

Backend **1 112 passants**, 1 ignoré. Frontend **179 passants**.
Lint 0 erreur. Build Vite réussi. Aucune migration manquante.
