# Rapport de la phase 7 — FEBA

Date : 05/11/2026. Six chantiers, plus un audit transversal. Les détails et preuves sont dans :
[RAPPORT_BULLETINS_PDF.md](RAPPORT_BULLETINS_PDF.md), [RAPPORT_VALIDATION_PAIEMENTS.md](RAPPORT_VALIDATION_PAIEMENTS.md),
[RAPPORT_MESSAGERIE_EMAILS.md](RAPPORT_MESSAGERIE_EMAILS.md), [RAPPORT_AUDIT_GLOBAL.md](RAPPORT_AUDIT_GLOBAL.md).

## Synthèse par chantier

| Chantier | Cause racine / constat | Correction | PR | Niveau de validation |
|---|---|---|---|---|
| A. Aperçu des bulletins | worker pdf.js `.mjs` servi en `application/octet-stream` + `nosniff` par nginx 1.28 | build en `.js`, contrôle MIME en CI | #99 | Production : moteur PDF vérifié ; parcours connecté non vérifié (compte) |
| B. Graphique des paiements | périodes et granularités limitées, types/modes en choix unique cachés, indicateurs partiels | 14 périodes, granularité heure/jour/semaine/mois, choix multiples d'après les données réelles, moyenne, payeurs, répartitions | #100 | CI + production (lecture seule) |
| C. Page Paiements | tout chargé dans le navigateur, recherche sur 3 champs | recherche sans accents sur 10 critères, filtres combinables, tri et pagination serveur, totaux, export Excel | #100 | CI + production (lecture seule) |
| D. E-mails groupés | pas d'adresse libre, ni Cc / Cci, ni mise en forme, ni brouillon | À / Cc / Cci, message commun ou individuel, HTML nettoyé, brouillons avec pièces jointes, signature, suivi des envois | #101 | CI ; production après déploiement |
| E. Messagerie interne | 2 personnes par conversation, pas d'états personnels, 4 écrans dupliqués | dossiers personnels, groupes, pièces jointes multiples, brouillons, recherche, nouvelle interface | #102 | CI ; production après déploiement |
| F. Paiement par carte | seul prestataire Stripe, inaccessible au Bénin | FedaPay (XOF), webhook signé + relecture serveur, rapprochement, verrou anti double encaissement | #103 | Local + CI en réseau simulé ; **bloqué** : compte marchand |

## Fichiers principaux
- Bulletins : `frontend/vite.config.js`, `frontend/scripts/verifier_types_assets.mjs`, `.github/workflows/ci.yml`, `frontend/src/components/ui/ApercuPdf.jsx`.
- Paiements : `backend/apps/payments/tableau_bord.py`, `recherche.py`, `views.py`, `urls.py` ; `frontend/src/components/dashboard/GraphiquePaiements.jsx`, `components/payments/RecherchePaiements.jsx`, `components/ui/ChoixMultiple.jsx`, `pages/admin/Payments.jsx`.
- E-mails : `backend/apps/notifications/{campaign_models,campaigns,campaign_views,campaign_urls,mailer,email_models,html_securise}.py`, migration `0010_phase7_emails` ; `frontend/src/pages/admin/MassEmail.jsx`, `components/email/{ChampAdresses,EditeurMessage}.jsx`.
- Messagerie : `backend/apps/messaging/{models,services,views,urls}.py`, migration `0005_phase7_messagerie` ; `frontend/src/pages/shared/Messagerie.jsx`.
- Carte : `backend/apps/payments/{providers,card_views,tasks,urls}.py`, `feba_project/settings/base.py` ; `frontend/src/components/payments/RetourPaiementCarte.jsx`, `pages/admin/CardTransactions.jsx`.
- Tests : `backend/tests/test_paiements_recherche.py`, `test_emails_composition.py`, `test_messagerie_phase7.py`, `test_paiement_carte_fedapay.py` ; E2E `e2e/ci/scenarios/{paiements,emails,messagerie}.mjs`.

## Migrations
- `notifications.0010_phase7_emails`, `messaging.0005_phase7_messagerie` : **ajouts uniquement** (champs avec valeur par défaut, nouvelles tables). Aucune donnée modifiée ni supprimée.

## Données de production
Aucune donnée de production modifiée. Toutes les vérifications en production ont été faites en lecture seule.

## Déploiements
Voir [SUIVI_REPRISE_PHASE7.md](../cloture/SUIVI_REPRISE_PHASE7.md) pour les commits déployés et l'état final.
