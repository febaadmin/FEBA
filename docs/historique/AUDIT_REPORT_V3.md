# AUDIT_REPORT — FEBA School Management (V3 → V3 bilingue auditée)

Date : 16 juillet 2026
Branche : `claude/v3-bilingual-audit` (base : import du zip V3 `feba_v1.zip` du 15/07/2026)

---

## 1. Architecture identifiée

| Couche | Technologie | Détails |
|---|---|---|
| Backend | Django 5 + Django REST Framework | 21 apps métier (`backend/apps/*`), authentification JWT (SimpleJWT, rotation + blacklist), multi-tenant par établissement (`school` FK + `IsSameTenant`), Channels (WebSocket), Celery + Redis (tâches) |
| Frontend | React 18 + Vite | Zustand (état auth persisté), React Query (données serveur), react-hook-form + zod (formulaires), Tailwind CSS, React Router 6 (espaces par rôle : `/superadmin`, `/admin`, `/teacher`, `/parent`, `/student`) |
| Base de données | PostgreSQL 16 (prod/dev docker) | SQLite possible en mode démo local (`settings.dev_sqlite`) |
| PDF | Génération bulletins via `apps/bulletins/pdf_generator.py` | Bulletins bilingues FR/EN, formule 60/40 |
| Visio | Jitsi Meet (mode démo ou auto-hébergé JWT) | `docker-compose.jitsi.yml` |
| Déploiement | Docker Compose (dev + prod), Nginx, WhiteNoise | `docker-compose.yml`, `docker-compose.prod.yml` |

Modules analysés : accounts, announcements, attendance, bulletins, classes, core (tenancy/plateforme), dashboard, grades, homework, messaging, notifications, parents, payments, schedule, schools, students, subjects, teachers, user_files, virtualclass — plus les 56 pages frontend, 5 layouts, 12 composants UI.

## 2. Bilinguisme (PRIORITÉ Nº 1) — réalisé

Voir `CHANGELOG_FIXES.md` § Bilinguisme pour le détail. Résumé :

- **Architecture i18n centralisée unique** : `frontend/src/i18n/` — modèle « gettext » (la chaîne française EST la clé), dictionnaire FR→EN de ~1 050 entrées (`translations.js`), repli automatique sur le français (aucune clé technique ne peut apparaître à l'écran).
- **Page de connexion bilingue simultanée** : chaque texte affiché en « FR / EN » via `tBoth()` (titres, labels, placeholders, bouton, erreurs de validation zod, messages d'échec serveur, aria-labels afficher/masquer le mot de passe).
- **Sélecteur FR | EN** dans l'en-tête des 5 layouts (tous les rôles), application immédiate sans déconnexion (remontage de l'arbre React via `<AppRouter key={lang} />`, route courante préservée).
- **Persistance** : localStorage (`feba-lang`) + profil utilisateur (`CustomUser.preferred_language`, migration `accounts.0004`), synchronisée par PATCH `/api/auth/me/` au changement, ré-appliquée en priorité au login.
- **Messages backend** : `Accept-Language` envoyé par axios + `LocaleMiddleware` Django (messages du framework localisés) ; les messages métier français connus sont traduits à l'affichage par le dictionnaire via `utils/errors.js` (point de passage unique des erreurs API).
- **Dates localisées** : helper `dateLocale()` (fr-FR / en-GB), remplacement des locales codées en dur, date-fns localisé (salles virtuelles), jours de semaine et mois abrégés traduits.

## 3. Problèmes détectés et corrigés

| # | Gravité | Problème | Fichiers | Correction | Test |
|---|---|---|---|---|---|
| 1 | Critique (mission) | Application non bilingue : ~1 500 chaînes françaises codées en dur dans 56 pages, 5 layouts, 12 composants | tout `frontend/src` | Système i18n central + enveloppement `t()` de toutes les chaînes + dictionnaire EN ~1 050 entrées | Build Vite OK ; vérification navigateur FR/EN ; `tests/test_i18n_preferences.py` (7 tests) |
| 2 | Élevée | Pas de préférence de langue persistée côté serveur | `accounts/models.py`, `serializers.py`, `views.py` | Champ `preferred_language` + migration 0004 + exposition/PATCH `/auth/me/` | `test_i18n_preferences.py` : défaut fr, PATCH, rejet langue non supportée, restauration à la reconnexion, isolation par utilisateur |
| 3 | Élevée | Montant de paiement sans validation : montants négatifs ou nuls acceptés (risque d'incohérence financière) | `payments/serializers.py` | `validate_amount` (strictement positif) + `validate_payment_date` (pas de date future) | `test_audit_validations.py::TestPaymentValidation` (4 tests) |
| 4 | Élevée | Présences : doublons possibles (même élève, même date, même matière) et dates futures acceptées | `attendance/serializers.py` | Validation d'unicité (mise à jour exclue) + rejet date future | `TestAttendanceValidation` (3 tests) |
| 5 | Élevée | Emploi du temps : aucun contrôle de conflit — fin avant début, chevauchements classe/enseignant/salle acceptés | `schedule/serializers.py` | Validation fin > début + détection de chevauchement (même jour/année) pour la classe, l'enseignant et la salle | `TestScheduleConflicts` (4 tests) |
| 6 | Moyenne | Lookup JSONField `__contains` non portable (plantage SQLite : annonces + dashboard élève) | `announcements/utils.py` (nouveau), `announcements/views.py`, `dashboard/views.py` | Helper `filter_targets_role()` : lookup natif sur PostgreSQL, cast texte sur les autres moteurs (sans faux positif grâce aux guillemets JSON) | 3 tests précédemment en échec sur SQLite passent désormais des deux côtés |
| 7 | Moyenne | `urls.py` importait `debug_toolbar` dès que `DEBUG=True` → crash au démarrage si le paquet n'est pas installé | `feba_project/urls.py` | Import conditionné à la présence dans `INSTALLED_APPS` | Démarrage vérifié en mode `dev_sqlite` (runserver) |
| 8 | Moyenne | Proxy Vite figé sur l'hôte docker `backend-dev` → frontend inutilisable hors Docker | `frontend/vite.config.js` | Cible configurable par `BACKEND_ORIGIN` (défaut docker inchangé) | Stack locale lancée avec `BACKEND_ORIGIN=http://localhost:8000`, connexion vérifiée au navigateur |
| 9 | Moyenne | Pas de mode d'exécution sans PostgreSQL/Redis (démo/dev léger) ; migrations v29 en SQL brut PostgreSQL | `feba_project/settings/dev_sqlite.py` (nouveau) | Settings démo documentés : SQLite fichier, schéma dérivé des modèles (`migrate --run-syncdb`), Celery eager, channels mémoire | Migrate + `seed_demo_data` + runserver + parcours navigateur exécutés |
| 10 | Faible | `settings/test_postgres.py` : identifiants codés en dur ne correspondant pas à la stack docker | `test_postgres.py` | Variables d'environnement `TEST_DB_*` avec défauts = stack docker dev | Suite complète exécutée sur PostgreSQL : 220/220 |
| 11 | Faible | Test de concurrence en échec permanent sur SQLite (verrou de table en mémoire) | `tests/test_parent_student.py` | `skipIf(vendor=="sqlite")` avec raison documentée ; test exécuté et vert sur PostgreSQL | `220 passed` sur PostgreSQL |
| 12 | Faible | 2 tests de notifications utilisaient une date codée en dur devenue future (cassants avec la validation n°4) | `tests/test_priority_fixes.py` | Date passée dans l'année scolaire (2026-02-05) | Suite verte |
| 13 | Faible | Code mort : `allRoomTypeOptions` construit puis jamais utilisé | `pages/admin/Settings.jsx` | Supprimé | Build OK |
| 14 | Faible | Variables locales `t` masquant la fonction de traduction (5 sites, dont 2 entourant des rendus d'options) | Teachers/Schedule/Grades/Settings.jsx | Renommées (`tch`, `tc`, `per`, `nt`, `rt`) | Build OK |

## 4. Contrôles d'audit sans anomalie détectée (vérifiés)

| Domaine | Méthode de vérification | Résultat |
|---|---|---|
| Montants financiers | Lecture des modèles : `DecimalField` partout (payments.amount 12,2 ; grades.value 4,2) — pas de flottants | Conforme |
| Barème des notes | `MinValueValidator(0)/MaxValueValidator(20)` sur `Grade.value` ; coefficient ≥ 1 | Conforme (impossible de saisir hors barème via l'API — validators DRF hérités du modèle) |
| Formule bilingue 60/40 et moyennes | Suite de tests dédiée existante (`test_years_and_averages.py`, `test_priority_fixes.py`, `test_parent_averages_missing_period.py`, `test_bug_fixes_v45.py`) réexécutée | 220/220 verts sur PostgreSQL |
| Permissions serveur | Lecture de `accounts/permissions.py` + `get_permissions()` des ViewSets (ex. paiements : écritures réservées admin+) ; suite `test_tenant_security.py` (isolation multi-établissements) réexécutée | Conforme — les restrictions ne sont pas seulement visuelles |
| PATCH /auth/me/ | Liste blanche de champs (`first_name`, `last_name`, `phone`, `avatar`, `preferred_language`) — un utilisateur ne peut pas s'auto-promouvoir | Test dédié `test_patch_me_cannot_change_role` |
| Authentification | Login email+mdp, comptes désactivés bloqués, établissement suspendu bloqué, rate-limit 20/min/IP sur le login, rotation des refresh tokens + blacklist, déconnexion révoquant le refresh | Lecture de `CustomTokenObtainPairSerializer` + tests accounts existants |
| Secrets | `.env.prod` gitignoré ; `.env.dev` ne contient que des valeurs locales de développement explicitement marquées non-production ; `SECRET_KEY` prod exigée par variable d'environnement | Inspection `git ls-files` + settings |
| Config production | `prod.py` : DEBUG=False, HSTS 1 an + preload, SSL redirect, cookies Secure, X-Frame-Options DENY, nosniff | Lecture settings |
| Redirections notifications | Corrigées dans la V3 importée (`notification_path` préfixé par rôle) — vérifiées présentes | Tests `test_priority_fixes.py` |
| Pagination | `FlexiblePagination` par défaut (PAGE_SIZE 20) | Lecture settings |

## 5. Tests exécutés (commandes réelles)

```bash
# SQLite (rapide, sans services)
cd backend
DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite .venv-test/bin/python -m pytest --no-migrations -q
# → 219 passed, 1 skipped (concurrence : nécessite un vrai serveur de BD)

# PostgreSQL (migrations incluses)
DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres .venv-test/bin/python -m pytest -q
# → 220 passed

# Frontend
cd frontend && npm run build
# → ✓ built (sans erreur)
```

Vérification navigateur (stack locale `dev_sqlite` + Vite, données `seed_demo_data`) :
- page de connexion : tous les textes en FR / EN simultanés — capturé ;
- connexion invalide → 400 + toast bilingue ; connexion valide `admin@feba.bj` → tableau de bord ;
- sélecteur FR|EN dans l'en-tête → bascule immédiate (Dashboard/School overview, cartes KPI, graphiques) — capturé ;
- persistance : `PATCH /api/auth/me/` (200) émis au changement de langue ; préférence restaurée à la reconnexion (couvert aussi par test API dédié).

## 6. Risques résiduels

1. **Couverture i18n** : ~1 050 chaînes traduites ; d'éventuels reliquats mineurs (textes très dynamiques, combinaisons rares) s'affichent en français (repli sûr) — jamais de clé technique. Un balayage systématique des nœuds mixtes a été fait ; signaler tout reliquat repéré à l'usage.
2. **Doublons de présence pré-existants** : la validation bloque les nouveaux doublons via l'API ; les éventuels doublons historiques en base ne sont pas purgés (aucune migration destructive, conformément à la mission).
3. **Conflits d'emploi du temps pré-existants** : même logique — le contrôle s'applique aux créations/modifications futures.
4. **Migrations v29 en SQL PostgreSQL** : inchangées (les réécrire risquerait de casser les bases existantes) ; le mode SQLite local utilise le schéma dérivé des modèles, documenté dans `dev_sqlite.py`.
5. **Mode d'emploi Celery/Redis** : en mode démo local, Celery est en mode eager (synchronisé) — comportement des tâches identique mais non asynchrone.

## 7. Éléments non testables dans cet environnement (et pourquoi)

- **E-mails réels** : backend console en dev (aucun serveur SMTP fourni) — la logique d'envoi est exercée, pas la délivrance.
- **Jitsi auto-hébergé (JWT)** : nécessite l'instance `docker-compose.jitsi.yml` et des secrets `JITSI_APP_*` ; le mode démo meet.jit.si est fonctionnel.
- **Test de charge / volumes élevés** : hors périmètre de l'environnement local ; la pagination et les index existants limitent le risque.
- **Docker en fin de session** : Docker Desktop a été arrêté en cours de vérification (hors de mon contrôle) ; la validation navigateur a été terminée sur la stack locale sans Docker (`dev_sqlite` + Vite). La stack Docker avait démarré proprement auparavant (migration 0004 appliquée sur PostgreSQL, backend healthy, login 400/200 vérifiés à travers le proxy).
