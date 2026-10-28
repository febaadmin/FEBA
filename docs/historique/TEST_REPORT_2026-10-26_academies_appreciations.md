> **DOCUMENT HISTORIQUE** — version « académies typées, fiche FHA, appréciations ». Voir `FINAL_REPORT.md` pour la version en cours.

# FEBA — Rapport de tests : fiche FHA, académies typées, appréciations, isolation

26 octobre 2026, branche `feat/academies-inscriptions-appreciations`, **en local
uniquement**. Version précédente : `docs/historique/TEST_REPORT_2026-10-26_bulletins_branding.md`.
Statuts : PASS · FAIL · BLOCKED · NOT RUN · SIMULATED. Un test ignoré n'est
jamais compté comme réussi. Vérification depuis l'archive extraite :
`DELIVERY_VERIFICATION_ACADEMIES.txt`, livré à côté du ZIP.

## 1. Tests automatisés (dépôt, code final, commit 40c8078)

| Suite | Résultat | Statut |
|---|---|---|
| Backend PostgreSQL 16 + Mailpit SMTP + plugNmeet v2.5.3 réel | **1814 réussis, 0 ignoré, 0 échec** | PASS |
| Backend SQLite | 1804 réussis, **10 ignorés** (PostgreSQL, Mailpit ou plugNmeet requis — tous exécutés et réussis sur PostgreSQL), 0 échec | PASS |
| Frontend Vitest | 352 / 352 (46 fichiers) | PASS |
| ESLint | 0 erreur (74 avertissements antérieurs, aucun ajouté) | PASS |
| Build Vite | réussi | PASS |
| `makemigrations --check` · `build_branding_assets.py --check` | aucune migration manquante · dérivés conformes | PASS |
| Migrations 0012 / 0020 / 0013 : retour arrière puis réapplication (pile locale, données de démonstration) | aller-retour sans erreur, reclassement identique | PASS |

Nouveaux tests :
- `test_fha_child_gender.py` (12) : sexe obligatoire, vide / inconnu refusés,
  F et M enregistrés, API liste et détail, autre académie 404, fiche PDF
  relue (Féminin / Masculin), correction puis régénération, dossier
  antérieur lisible et « Non renseigné », migration sans valeur inventée,
  alerte e-mail ; + `test_fha_enrollment_workflow` (chaque champ envoyé
  enregistré, sexe compris).
- `test_academy_types_creation.py` (29) : création des trois types (niveaux,
  cycles, `entity_type`, fonctionnalités), barème copié et indépendant,
  aucune donnée copiée, première année, académies existantes intactes,
  académie proposée et sélectionnable, validations (champs, type, code
  en double / invalide, nom, fuseau, année), rôles non autorisés (403),
  code immuable, non classée avec motif, classement refusé / accepté selon
  les niveaux, type et `entity_type` cohérents, désactivation, suppression
  (409 / 204), cycles des niveaux et barèmes /10 /20, migration de classement.
- `test_appreciation_rules.py` (18) : lecture, rôles, isolation, ajout /
  modification / suppression persistés, 8 cas de validation, appréciation
  utilisée protégée et désactivable, réinitialisation confirmée, bornes
  exactes sur 20 et sur 10, aperçu (même pourcentage, barème non
  enregistré), libellés anglais, matière non notée, **PDF** (libellé imprimé,
  moyennes et lettres inchangées, /10 et /20, barème de cycle, bulletin émis
  inchangé), API des notes.
- `test_isolation_2_7_19_academies.py` (3 tests × 3 tailles) : voir § 2.
- `test_audit_academies_2026_10_26.py` (7) : e-mail-config, identité des
  documents d'une nouvelle académie (aucun nom, adresse ou numéro du groupe
  FEBA), diplômes d'autres académies refusés, seed complet, barème installé
  par `init_academies`, académie sans logo (favicons générés, jamais 404).
- `test_branding_source.py` (+2) : numéro propre d'une académie indépendante.
- Frontend : `fhaEnrollGender.test.jsx` (6), `Academies.test.jsx` (3),
  `Appreciations.test.jsx` (9), `Settings.academy.test.jsx` (2),
  `AcademyLogo.test.jsx` (3).

## 2. Isolation multi-académies (tests backend, API réelle)

| Académies (types alternés) | Requêtes vérifiées | Fuites | Erreurs 5xx | Écritures croisées abouties | Statut |
|---|---|---|---|---|---|
| 2 | 2 528 | 0 | 0 | 0 | PASS |
| 7 | 6 500 | 0 | 0 | 0 | PASS |
| 19 | 11 388 | 0 | 0 | 0 | PASS |

Première exécution à 2 académies : **1 fuite** (`/api/notifications/email-config/`),
corrigée puis relancée.

## 3. Validations réelles (local, Chrome)

| Contrôle | Résultat | Statut |
|---|---|---|
| Fiche FHA : options, blocage sans sexe, brouillon restauré, 12 étapes, envoi, liste et détail admin, fiche PDF « Sexe : Féminin » | conforme | PASS |
| Création par l'écran d'une académie en ligne, primaire, secondaire ; « Configuration restante » ; FEBA « non classée » avec motif | conforme | PASS |
| Niveaux du lycée (Collège · /20, Lycée · /20), cycles proposés, niveau créé sans cycle → collège | conforme | PASS |
| Appréciations : libellé modifié, relu après rechargement, autre académie intacte, aperçu 13,5/20, incohérence bloquée | conforme | PASS |
| Bulletin FEBA réel : libellés configurés imprimés, moyennes identiques avant / après | conforme | PASS |
| Académie sans logo : monogramme, aucune image cassée, favicon 200 | conforme | PASS |
| Suppression : académies vides 204, FEBA (données) 409 | conforme | PASS |
| Scénarios e2e (8) | tous verts | PASS |

## 4. Non exécuté ou bloqué

| Contrôle | Statut |
|---|---|
| Hetzner, préproduction, plugNmeet de production | BLOCKED (SSH refusé) |
| SMTP Hostinger, Twilio | BLOCKED |
| Partage d'écran, réunion entre réseaux distincts | NOT RUN |
| CDN et navigation privée en production | NOT RUN |
