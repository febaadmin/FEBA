# CHANGELOG_FIXES — FEBA V3 bilingue auditée

## HOTFIX (16/07/2026, soir) — page blanche /parent/home « t2 is not a function »

**Symptôme** : après connexion Parent, `/parent/home` restait entièrement
blanche ; console : `Uncaught TypeError: t2 is not a function`
(Home.jsx:76–78, Array.map, ParentHome).

**Cause racine** : dans `frontend/src/pages/parent/Home.jsx`, le rendu des
moyennes trimestrielles utilisait un destructuring
`.map(([t, v]) => …)` — la variable locale `t` (libellé « T1 »/« T2 »/« T3 »)
**masquait la fonction de traduction `t`** importée de `src/i18n`. L'appel
`t("Moy.")` introduit par la passe i18n tombait donc sur la chaîne « T1 »
(pas une fonction) → crash du rendu React → page blanche. `t2` est le nom
que Vite donne à l'un des deux identifiants en collision dans le module
transformé.

**Correction (cause racine, pas de contournement)** :
- renommage du paramètre destructuré : `.map(([per, v]) => …)` +
  `key={per}` + `{t("Moy.")} {per}` — la fonction de traduction n'est plus
  masquée et le libellé de période reste affiché ;
- balayage automatisé de TOUT le frontend à la recherche d'autres liaisons
  locales nommées `t` dans les fichiers important `{ t }` (16 motifs :
  params de callback, destructuring tableau/objet, const/let/var, catch,
  for) → un seul autre cas, bénin, uniformisé (`AdminLayout`) ;
- **garde-fou permanent** : test statique
  `frontend/src/test/no-t-shadowing.test.js` qui fait échouer la suite si
  un shadowing de `t` est réintroduit.

**Renforts ajoutés en même temps** :
- Error Boundary global (`frontend/src/components/ErrorBoundary.jsx`,
  monté dans `App.jsx`) : plus jamais de page entièrement blanche — écran
  d'erreur bilingue avec « Réessayer / Retour », erreur d'origine toujours
  tracée en console ;
- infrastructure de tests frontend (Vitest + Testing Library + jsdom) ;
- `frontend/src/pages/parent/Home.test.jsx` : 10 tests de rendu de
  ParentHome (données valides mono/multi-enfants, moyennes T1/T2/T3 — le
  scénario exact du crash —, valeurs null, children absent/vide, erreur
  API, chargement, annonces, bascule EN) ;
- `frontend/src/i18n/i18n.test.js` : 12 tests unitaires i18n (traduction,
  repli, interpolation, tBoth, persistance, langue non supportée) ;
- dernières chaînes non traduites de ParentHome (« Aucune note »,
  « Progression T1 → T2 : ») passées par t().

**Vérifié dans le navigateur (identifiants réels, serveur local)** :
connexion parent1@feba.bj → `/parent/home` s'affiche (2 enfants, moyennes
générale/T1/T2/T3/FR/EN, progression) ; console : 0 erreur ; rechargement
direct par URL OK ; navigation `/parent/grades` ↔ retour OK (cartes de
moyennes remplies) ; clic sur une notification réelle → `/parent/grades`
sans déconnexion ; déconnexion UI OK ; reconnexion élève →
`/student/home` complet ; bascule FR↔EN immédiate.

---


Modifications réalisées sur la base V3 (`feba_v1.zip`), classées par catégorie.

## Bilinguisme

- **Nouveau système i18n centralisé** `frontend/src/i18n/` :
  - `index.js` — état de langue (module + `useSyncExternalStore`), `t()` global,
    `useI18n()` réactif, `tBoth()` (affichage « FR / EN » simultané),
    `translate()`, `getLang()/setLang()`, `dateLocale()` ;
  - `translations.js` — dictionnaire FR→EN (~1 050 entrées), la chaîne
    française est la clé (modèle gettext), repli automatique sur le français.
- **Page de connexion bilingue simultanée** (`pages/LoginPage.jsx`) : titres,
  sous-titre, labels, placeholders, bouton (état de chargement inclus),
  erreurs zod, messages d'échec serveur, aria-labels — tous en « FR / EN ».
- **Sélecteur de langue FR | EN** (`components/ui/LanguageSwitcher.jsx`)
  intégré à l'en-tête des 5 layouts (superadmin, admin, teacher, parent,
  student). Application immédiate : `App.jsx` remonte l'arbre
  (`<AppRouter key={lang} />`) sans déconnexion ni perte de route.
- **Persistance** : localStorage `feba-lang` + champ serveur
  `preferred_language` (PATCH `/api/auth/me/` au changement ; ré-appliqué en
  priorité au login — `hooks/useAuth.js`).
- **Traduction de toutes les pages** : 56 pages + 5 layouts + 12 composants
  (~1 500 chaînes enveloppées dans `t()` : nœuds JSX, attributs UI,
  toasts, ternaires, colonnes de tableaux, sous-titres interpolés
  `{n} élève(s)`, etc.).
- **Messages backend traduits à l'affichage** : `utils/errors.js`
  (`extractApiError/extractApiErrors`) passe tous les messages par `t()` ;
  les messages métier français fréquents du backend sont au dictionnaire.
- **Négociation de langue HTTP** : axios envoie `Accept-Language` ;
  `LocaleMiddleware` + `LANGUAGES=[fr,en]` côté Django (messages du
  framework localisés).
- **Dates et calendrier** : `dateLocale()` (fr-FR/en-GB) remplace les locales
  codées en dur (`toLocaleDateString("fr-FR")` × 16), date-fns localisé
  (VirtualRooms), jours de semaine et mois abrégés des graphiques traduits.

## Interface

- Sélecteur de langue accessible (aria-pressed, aria-label, `lang=`).
- `StatusBadge` : traduction appliquée au rendu (plus de libellés figés à la
  langue de chargement).
- `ConfirmDialog` : titres/messages par défaut et boutons traduits.
- Suppression de code mort : `allRoomTypeOptions` (Settings).
- Renommage de variables locales `t` qui masquaient la fonction de
  traduction (Teachers, Schedule, Grades ×2, Settings).

## Backend

- `CustomUser.preferred_language` (choices fr/en, défaut fr) + migration
  `accounts/0004_customuser_preferred_language.py` ; exposé dans
  `UserSerializer`, modifiable via la liste blanche du PATCH `/auth/me/`.
- `feba_project/urls.py` : import de `debug_toolbar` conditionné à sa
  présence dans `INSTALLED_APPS` (plantage si DEBUG=True sans le paquet).
- Nouveau settings `feba_project/settings/dev_sqlite.py` : exécution locale
  complète sans Docker/PostgreSQL/Redis (SQLite fichier, Celery eager,
  channels mémoire, schéma dérivé des modèles `migrate --run-syncdb`).
- `feba_project/settings/test_postgres.py` : identifiants configurables par
  variables d'environnement `TEST_DB_*` (défauts = stack docker dev).

## Base de données

- Migration additive `accounts.0004` (`preferred_language`) — non
  destructive, défaut `fr`.
- `apps/announcements/utils.py::filter_targets_role()` — filtrage par rôle
  destinataire portable : lookup JSON natif sur PostgreSQL, cast texte
  ailleurs (SQLite). Appliqué dans `announcements/views.py` et
  `dashboard/views.py` (dashboard élève).

## Logique métier

- **Emploi du temps** (`schedule/serializers.py`) : heure de fin > heure de
  début ; refus des chevauchements (même jour + même année scolaire) pour la
  classe, l'enseignant et la salle.
- **Présences** (`attendance/serializers.py`) : date future refusée ;
  doublon (élève + date + matière) refusé, mises à jour exclues du contrôle.

## Authentification

- Préférence de langue restaurée en priorité à la reconnexion.
- Vérifié (tests existants + nouveau test) : le PATCH `/auth/me/` ne permet
  pas de modifier `role`/`is_active`/`school` (liste blanche).

## Permissions

- Pas de faille détectée : écritures sensibles réservées aux rôles adéquats
  côté serveur (ex. paiements admin+), isolation multi-établissements
  couverte par `test_tenant_security.py` (réexécuté vert).

## Sécurité

- Validations serveur renforcées (voir Logique métier + Paiements).
- Paiements : montant strictement positif, date non future
  (`payments/serializers.py`).
- Confirmé : secrets prod hors dépôt, HSTS/SSL/cookies Secure en prod,
  rate-limit login, rotation+blacklist des refresh tokens.

## Performances

- Aucune régression introduite ; pas d'optimisation risquée réalisée.
  Les listes admin utilisent la pagination existante (`FlexiblePagination`).

## Tests

- `tests/test_i18n_preferences.py` (nouveau, 7 tests) : préférence de langue
  (défaut, PATCH, rejet de langue non supportée, restauration après
  reconnexion, isolation par utilisateur, liste blanche du PATCH).
- `tests/test_audit_validations.py` (nouveau, 11 tests) : paiements
  (négatif/zéro/date future/valide), présences (date future, doublon,
  mise à jour), emploi du temps (fin<début, chevauchements classe/salle,
  non-chevauchement accepté).
- `tests/test_parent_student.py` : test de concurrence marqué `skipIf`
  SQLite avec justification (vert sur PostgreSQL).
- `tests/test_priority_fixes.py` : dates de test corrigées (étaient dans le
  futur, incompatibles avec la nouvelle validation).
- Résultats : **220/220 sur PostgreSQL** (migrations incluses),
  **219 + 1 skip documenté sur SQLite**.

## Documentation

- `README.md` mis à jour (mode local sans Docker, sélecteur de langue,
  variables d'environnement).
- `.env.example` documenté à la racine.
- `AUDIT_REPORT.md`, `VERIFICATION_CHECKLIST.md`, `CORRECTIONS.md` ajoutés.
