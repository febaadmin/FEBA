# KNOWN_LIMITATIONS.md — Missions V4 → V8

## Ajouts V8 (26/07/2026)

1. **Migrations non rejouables sur la SQLite embarquée.** Une migration
   *historique* utilise une syntaxe refusée par SQLite 3.53 (« near EXISTS »).
   Les tests SQLite tournent donc avec `--no-migrations` — limitation
   **pré-existante** (vérifiée sur un test antérieur à la V8), pas une
   conséquence des migrations V8. **La chaîne complète est validée sur
   PostgreSQL 16** (406/406) et la logique des migrations de données est en
   outre testée directement (`tests/test_data_migrations.py`).

2. **Barème /10 appliqué au bulletin PDF.** Les écrans ERP (tableaux de bord,
   listes de notes, espaces Parent/Élève) affichent toujours l'échelle interne
   /20. Les fonctions centrales (`get_grading_scale`,
   `convert_average_for_scale`) sont prêtes à y être branchées.

3. **Anciens poids d'évaluation non reconstituables.** La migration ramène tous
   les poids à 1 sans conserver les valeurs précédentes : seul un dump antérieur
   permet de les retrouver (cf. `RESTORE_GUIDE.md`).

4. **Notifications d'incident : paliers fixes** (1, 5, 25, 100, 500), non
   configurables depuis l'interface.

5. **Pas de service externe d'erreurs** (type Sentry) configuré : le système
   interne fonctionne seul. Un connecteur s'ajouterait dans `report_incident()`.

6. **63 avertissements ESLint** hérités (hooks, variables inutilisées) —
   **0 erreur**. Non traités pour ne pas élargir le périmètre.

7. **Base de démonstration : migrations de données rejouées explicitement.**
   Les réglages `dev_sqlite` neutralisent la chaîne de migrations ; la commande
   `bootstrap_demo` rejoue donc les migrations de **données** V8 à la main puis
   **vérifie** l'invariant (aucun poids ≠ 1). Sur PostgreSQL, la chaîne
   s'applique normalement et la commande se contente de vérifier. Toute
   nouvelle migration de données devra être ajoutée à `DATA_MIGRATIONS` dans
   cette commande.

8. **Installation depuis PyPI non rejouée de bout en bout.** Sur la machine de
   validation, le réseau sortant est coupé et seul Python 3.14 est disponible
   (le projet cible 3.12+). Deux blocages ont été trouvés et corrigés
   (`psycopg2-binary` 2.9.9 → 2.9.12, ajout de `PyMuPDF`), mais un
   `pip install -r requirements/dev.txt` complet reste à confirmer sur une
   machine connectée.

9. **Node 20 requis pour la suite frontend.** Sous Node 26, jsdom est masqué
   par le `localStorage` global expérimental de Node et `i18n.test.js` échoue
   (`Cannot read properties of undefined (reading 'getItem')`). Utiliser la
   version du projet (`.nvmrc` / v20.20.2).


## Ajouts V7 (25/07/2026)
- Cachet : fichier statique unique packagé (défaut fourni) ; gestion fine par établissement
  (activation/taille/position, réservée aux profils autorisés) = évolution possible. Dégradation
  gracieuse si fichier absent.
- Vérification navigateur du site public via le volet intégré ; la lecture programmatique de la
  vidéo est bloquée en arrière-plan (économie d'énergie) — `readyState=4` prouve la disponibilité.
- Captures headless Chrome parfois indisponibles (mise à jour Chrome en attente sur la machine) :
  la vérification s'appuie alors sur le volet intégré + assertions DOM + rendus PDF réels.


## Ajouts V6 (20/07/2026)

- **Vérification de la sauvegarde via l'UI groupée.** Le flux de sauvegarde du
  `BulkGradeModal` est verrouillé par un **test composant déterministe**
  (`BulkGradeModal.test.jsx`, 6 cas) plutôt que par un clic manuel : le volet
  navigateur intégré ré-hydrate l'authentification de façon instable au rechar-
  gement (redirige vers l'écran de connexion), ce qui rend un clic-à-clic
  authentifié peu fiable. Le **contrat backend** (là où se situe le risque :
  atomicité, permissions, IDOR, erreurs indexées) est prouvé par 16 tests
  unitaires **et** un E2E sur session enseignant réelle (201 / 400-interdit /
  400-rollback). Le rendu du modal a été confirmé par capture dans l'UI
  enseignant réelle. L'ajout de Playwright/Cypress pour un clic-à-clic
  authentifié automatisé reste une amélioration possible.
- **Re-vérification navigateur des tableaux de bord authentifiés (parent,
  notes).** Pour la même raison d'instabilité d'auth du volet intégré, la
  non-régression des correctifs V4/V5 authentifiés repose sur les suites
  automatisées vertes (`test_parent_averages_missing_period`,
  `test_note_types_appreciations`, `test_password_reset`, `parent/Home.test.jsx`)
  et sur la vérification navigateur de la page notes enseignant (appréciations
  V4). Le site **public** (P1–P6) a, lui, été vérifié en navigateur à
  375/1280/1920 sans contrainte d'auth.
- **Avertissements eslint (62).** Base du projet (bonnes pratiques hooks,
  variables inutilisées) — 0 **erreur**. Non traités dans cette mission pour ne
  pas élargir le périmètre.



0. **Tests visuels automatisés (V5).** Playwright/Cypress/Storybook ne sont
   pas installés dans le projet ; la non-régression visuelle repose sur
   (a) le test structurel `mediaMeta.test.js` (cohérence points focaux ↔
   fichiers réels) et (b) les captures de référence versionnées dans la
   livraison (`captures/avant`, `captures/apres`, `captures/breakpoints`).
   L'ajout de Playwright pour des comparaisons de screenshots automatiques
   reste une amélioration possible.

1. **Suite de tests PostgreSQL non rejouée pendant cette mission.**
   Docker n'était pas disponible sur la machine. La suite SQLite complète
   passe (280 tests + 46 subtests) ; un unique test de concurrence
   multi-threads est skippé (verrou global SQLite) et doit être validé sur
   PostgreSQL :
   ```bash
   docker compose -f docker-compose.dev.yml up -d postgres-dev
   cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres \
     .venv-test/bin/python -m pytest -q
   ```

2. **Coordonnées et statistiques du site vitrine volontairement vides.**
   Conformément à la règle « aucune donnée fictive », téléphone, WhatsApp,
   email, horaires, réseaux sociaux et chiffres (élèves, enseignants,
   années, taux de réussite) ne sont PAS pré-remplis : le site masque ces
   blocs tant que l'administration ne les a pas saisis (écran ERP
   « Site vitrine » → Paramètres, ou /django-admin/). Idem pour les
   actualités : aucune fausse publication n'est seedée.

3. **Section « natation » absente de la vie scolaire.** Le cahier des
   charges la mentionne, mais l'archive médias fournie ne contient aucune
   image de natation (inventaire complet dans MEDIA_INVENTORY.md). Seules
   les activités réellement illustrées sont présentées. Ajouter la
   photo réelle puis un item d'activité suffira.

4. **Slides du carrousel et galerie : gestion via admin Django ou API.**
   L'écran React « Site vitrine » couvre messages, préinscriptions,
   actualités/événements et paramètres. Slides et albums restent
   administrables via `/django-admin/` (CRUD complet, inline pour les
   médias d'album) ou l'API `/api/website/admin/**` — sans recompilation.

5. **Révocation de session et access tokens.** Après réinitialisation d'un
   mot de passe, tous les refresh tokens de la cible sont blacklistés :
   plus aucune session ne peut se renouveler et l'ancien mot de passe est
   inutilisable immédiatement. Un access token déjà émis reste
   techniquement valide jusqu'à son expiration (60 min par défaut,
   `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` pour réduire) — limitation
   structurelle des JWT sans vérification en base à chaque requête.

6. **Sitemap à domaine fixe.** `frontend/public/sitemap.xml` référence un
   domaine d'exemple (`https://www.feba.bj`) à remplacer par le domaine
   réel au déploiement (voir guide de déploiement).

7. **Version anglaise du site vitrine.** L'ERP est bilingue (i18n FR/EN) ;
   le site public est publié en français (langue de communication de
   l'école). L'infrastructure i18n existante permet une traduction
   ultérieure si souhaitée.

8. **Mode démo SQLite.** `settings.dev_sqlite` crée le schéma avec
   `migrate --run-syncdb` (certaines migrations historiques v29
   contiennent du SQL PostgreSQL). La production utilise PostgreSQL avec
   la chaîne de migrations complète — y compris les nouvelles migrations
   V4 (`accounts/0005`, `grades/0010`, `bulletins/0005`, `website/0001`).
