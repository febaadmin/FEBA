# CORRECTIONS — cycle d'audit et de correction V6

Source : `feba_multi_academies_v9_application_CORRIGE.zip`
(SHA-256 `8ee116a9066314b57fbe964b351c0410fd52da0da2058bb35596f0daee59bff4`).
Voir `SOURCE_ARCHIVE_REPORT.md` pour la traçabilité complète.

Chaque ligne indique son niveau de preuve :
**EXÉCUTION** · **TEST AUTOMATISÉ** · **ANALYSE STATIQUE** · **VALIDATION DOCKER LOCALE REQUISE**.

---

## P1 — Tableau de bord Super Admin à zéro après actualisation — CORRIGÉ

**TEST AUTOMATISÉ.** Détail complet dans `ACADEMY_SCOPE_RACE_REPORT.md`.

Cause racine : les écrans métier se montaient avant que la portée d'académie
soit connue, émettaient leurs requêtes sous `X-Academy-Scope: UNKNOWN`, et ces
requêtes étaient avortées par la résolution du contexte. Non réessayées
(`retry: false` sur `ERR_CANCELED`), elles laissaient `data` à `undefined`,
que le tableau de bord repliait sur `[]` — d'où six zéros définitifs.

Fichiers corrigés :

- `frontend/src/context/AcademyContext.jsx` — machine d'états de démarrage,
  attente de l'hydratation, portée synchronisée pendant le rendu,
  déduplication de `entity-context`.
- `frontend/src/components/AcademyScopedOutlet.jsx` — garde `scopeReady` :
  aucun écran métier monté sous portée indéterminée.
- `frontend/src/pages/superadmin/Dashboard.jsx` — trois états distincts
  (attente / erreur / chargé), clé de requête incluant la portée, une requête
  annulée ne vide plus l'écran.
- `frontend/src/api/academyScope.js` — génération de portée,
  `isCanceledError()`.
- `frontend/src/hooks/useAuth.js` — purge complète du cache, annulation des
  requêtes en vol et remise à zéro de la portée au login et au logout.

Preuve de reproduction : 4 tests échouent contre le code d'origine, 10 passent
contre le code corrigé.

## P2 — Commande de nettoyage des données antérieures — LIVRÉ

**TEST AUTOMATISÉ.** Détail dans `PREVIOUS_USAGE_CLEANUP.md`.

`backend/apps/core/management/commands/clean_previous_usage_data.py` — 26
tests. La commande réelle n'a jamais été exécutée sur des données de
production.

Trouvaille notable : `Student.user` étant en `SET_NULL`, supprimer les comptes
laissait les profils élèves orphelins. Révélé par un test, pas par relecture.

## P3 — Titres de chaque étape de la fiche de renseignements — CORRIGÉ

**ANALYSE STATIQUE + build.** Détail dans `FHA_ENROLLMENT_FORM_REPORT.md`.

Les libellés n'existaient que dans la barre de progression, en petits
caractères, loin des champs. Les 12 étapes portent désormais un `<h2>`
sémantique posé directement au-dessus des champs, avec une phrase
d'introduction, la mention des champs obligatoires, et une version FR et EN.

Fichier : `frontend/src/site/pages/FhaEnrollPage.jsx` (`STEP_META`).

## P4 — Page FEBA FHA : formules et flyer — LIVRÉ

**ANALYSE STATIQUE + build + vérification d'empreinte.**
Détail dans `FHA_PUBLIC_PAGE_REPORT.md`.

- Formules Standard 699 $, Premium 999 $, Excellence 1 299 $ avec organisation
  et contenu détaillés, en FR et EN — source unique
  `frontend/src/site/fhaPlans.js`.
- Flyer installé en `frontend/public/images/feba-fha/feba-fha-flyer.jpeg`,
  **identique bit à bit** à l'original Drive
  (SHA-256 `4dedb347991c2e2972904a3a60651c06be118f48d5b41656898da7d9eec45ceb`),
  affiché sur la page avec « Voir en grand » et « Télécharger le flyer ».
- Champ « Formule souhaitée » (`STANDARD` / `PREMIUM` / `EXCELLENCE` /
  `UNDECIDED`) : modèle + migration `0011`, serializer de soumission,
  serializer de liste FHA Admissions avec libellé lisible, sélecteur dans le
  formulaire, restitution dans le récapitulatif.
- Récapitulatif enrichi : ville, langues, niveau de français, objectifs,
  WhatsApp, formule, besoins particuliers.
- Section « Tarifs » mise en cohérence : elle annonçait encore que le tarif
  n'était pas publié, ce qui aurait contredit les formules affichées plus haut.

## P5 — Total multidevise des paiements — DÉJÀ IMPLÉMENTÉ, VÉRIFIÉ

**EXÉCUTION.** `test_multi_currency.py` (23 tests) et
`test_payments_summary_consolidation.py` (12 tests) passent sur l'archive
source. La conversion est faite côté backend en `Decimal`. Aucune correction
nécessaire ; aucune modification apportée. Voir `MULTI_CURRENCY_REPORT.md`
(présent dans l'archive d'origine).

## P6 — Parité emploi du temps FEBA / FEBA FHA — DÉJÀ IMPLÉMENTÉ, VÉRIFIÉ

**EXÉCUTION.** `test_schedule_separation.py` (25 tests) et
`test_online_schedule_conflicts.py` (7 tests) passent. Aucune modification
apportée. Voir `SCHEDULE_PARITY_REPORT.md` (présent dans l'archive d'origine).

## P7 — Téléchargement des documents FHA — DÉJÀ IMPLÉMENTÉ, VÉRIFIÉ

**EXÉCUTION.** `test_fha_sheet_download_per_row.py` (4 tests) passe : le
téléchargement suit bien l'identifiant de la ligne. Aucune modification
apportée. Voir `FHA_ADMISSIONS_DOWNLOAD_REPORT.md`.

## P8 — Envoi du rapport mensuel — DÉJÀ IMPLÉMENTÉ, VÉRIFIÉ

**EXÉCUTION.** `test_monthly_reports.py` (65 tests) passe. Aucune modification
apportée. Voir `MONTHLY_REPORTS_FIX.md`.

## P9 — Bouton EN/FR visible sur mobile — CORRIGÉ

**TEST AUTOMATISÉ.** Détail dans `RESPONSIVE_I18N_REPORT.md`.

Le sélecteur n'était rendu que dans le bloc `min-[1200px]` et dans le menu
déroulant : sous 1200 px, changer de langue imposait d'ouvrir le hamburger.
Il est désormais dans la barre elle-même — disposition
`Logo | FEBA | EN/FR | Menu` — en réutilisant le **même** composant
`SiteLangSwitcher`. Le doublon du menu déroulant a été retiré.

Fichier : `frontend/src/site/SiteLayout.jsx`.
Preuve : 6 tests échouent contre le code d'origine, passent contre le corrigé.

## P10 — Audit global — PARTIEL

Voir `KNOWN_LIMITATIONS.md`, section « Portée réelle de cet audit ».
