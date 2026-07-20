# TEST_REPORT — itération « bilinguisation + hotfix page blanche Parent » (16/07/2026)

## Commandes réellement exécutées et résultats

```bash
# Backend — SQLite (sans services externes)
cd backend
DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite pytest --no-migrations -q
#  → 219 passed, 1 skipped (concurrence : nécessite un serveur de BD ; vert sur PostgreSQL)

# Backend — PostgreSQL (docker dev up, migrations incluses — avant l'arrêt de Docker)
DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres pytest -q
#  → 220 passed

# Backend — depuis la copie propre extraite du ZIP livré
#  → 219 passed, 1 skipped

# Frontend — tests unitaires (Vitest + Testing Library, nouveau)
cd frontend && npx vitest run
#  → 3 fichiers, 22 tests, 22 passed
#     · src/pages/parent/Home.test.jsx  (10) — rendu ParentHome, dont le
#       scénario exact du crash « t2 is not a function » (moyennes T1/T2/T3)
#     · src/i18n/i18n.test.js           (12) — t/tBoth/interpolation/repli/persistance
#     · src/test/no-t-shadowing.test.js (1)  — garde statique anti-shadowing de t

# Frontend — build production
npm run build
#  → ✓ built (aucune erreur)
```

## Vérification navigateur (serveurs réels : Django runserver + Vite)

| Scénario | Résultat observé |
|---|---|
| Connexion parent1@feba.bj | 200, redirection `/parent/home` |
| `/parent/home` | **Page complète** : 2 enfants, moyenne générale 12.62/20 & 12.68/20, Moy. T1/T2/T3, Français/Anglais, progression — plus de page blanche |
| Console navigateur | **0 erreur** (plus de « t2 is not a function ») |
| Rechargement direct `/parent/home` | OK |
| `/parent/grades` puis retour | OK — cartes Moy. Générale/Française/Anglaise/Bilingue remplies pour chaque enfant |
| Notification réelle (nouvelle note créée par l'enseignant via API) | Cloche → clic → navigation `/parent/grades`, session conservée, pas de déconnexion |
| Déconnexion (bouton UI) | Retour `/login`, jetons purgés |
| Connexion eleve1@feba.bj | `/student/home` complet (moyennes T1/T2/T3, annuelle, FR/EN) |
| Bascule FR ↔ EN (parent + admin) | Immédiate, persistée (PATCH `/auth/me/` 200) |
| Changement de mot de passe admin (API) | mauvais ancien → 400 ; bon → 200 ; login avec nouveau → 200 ; restauré |
| Réseau | Tous les endpoints du dashboard parent en 200, aucune boucle de requêtes |

---

# (Itérations précédentes ci-dessous)

# TEST_REPORT — Itération courante (notifications / moyennes / mot de passe)

Toutes les commandes ci-dessous ont été **réellement exécutées** dans
l'environnement de travail (pas de résultat inventé). Voir `CORRECTIONS.md`
pour le détail des corrections associées. Le rapport de l'itération
précédente (bulletins/matricules) a été renommé `TEST_REPORT_PREVIOUS.md`.

## 1. Backend — suite complète (PostgreSQL réel)

```
$ DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres python manage.py migrate --no-input
... (toutes les migrations appliquées sans erreur, y compris les migrations
     multi-tenant v29 qui utilisent une syntaxe PostgreSQL réelle)

$ DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres python -m pytest tests/ -q --reuse-db
====================== 192 passed, 143 warnings in 7.53s =======================
```

175 tests pré-existants + 17 nouveaux (`tests/test_priority_fixes.py`) = 192.
**0 échec, 0 erreur.**

## 2. Détail des 17 nouveaux tests (`tests/test_priority_fixes.py`)

```
tests/test_priority_fixes.py::NotificationPathTests::test_all_roles_get_correct_prefix PASSED
tests/test_priority_fixes.py::NotificationPathTests::test_create_notification_stores_related_url_verbatim PASSED
tests/test_priority_fixes.py::NotificationPathTests::test_leading_slash_in_path_is_normalized PASSED
tests/test_priority_fixes.py::NotificationPathTests::test_unknown_role_returns_empty_string_not_broken_url PASSED
tests/test_priority_fixes.py::GradeNotificationRedirectTests::test_grade_creation_notifies_parent_with_parent_prefixed_url PASSED
tests/test_priority_fixes.py::GradeNotificationRedirectTests::test_grade_creation_notifies_student_with_student_prefixed_url PASSED
tests/test_priority_fixes.py::AttendanceAndPaymentNotificationTests::test_absence_notifies_parent_and_student_with_correct_prefixes PASSED
tests/test_priority_fixes.py::AttendanceAndPaymentNotificationTests::test_payment_notifies_parent_and_student_with_correct_prefixes PASSED
tests/test_priority_fixes.py::DashboardSubjectAveragesTests::test_annual_subject_averages_helper_groups_by_subject PASSED
tests/test_priority_fixes.py::DashboardSubjectAveragesTests::test_parent_dashboard_exposes_subject_and_bilingual_averages_per_child PASSED
tests/test_priority_fixes.py::DashboardSubjectAveragesTests::test_student_dashboard_exposes_subject_and_bilingual_averages PASSED
tests/test_priority_fixes.py::DashboardSubjectAveragesTests::test_student_with_no_grades_at_all_dashboard_does_not_crash PASSED
tests/test_priority_fixes.py::DashboardSubjectAveragesTests::test_subject_without_grades_reports_none_not_zero PASSED
tests/test_priority_fixes.py::AdminPasswordChangeTests::test_admin_can_change_own_password PASSED
tests/test_priority_fixes.py::AdminPasswordChangeTests::test_superadmin_can_change_own_password PASSED
tests/test_priority_fixes.py::AdminPasswordChangeTests::test_weak_new_password_rejected_for_admin PASSED
tests/test_priority_fixes.py::AdminPasswordChangeTests::test_wrong_old_password_rejected_for_admin PASSED
```

## 3. Non-régression — tests des itérations précédentes

Toujours verts, sans modification :
- `tests/test_bulletin_layout.py` — 7/7
- `tests/test_matricule.py` — 16/16
- `tests/test_averages_and_notifications.py` (endpoint `/api/grades/averages/`,
  déjà présent) — inchangé, toujours vert.

## 4. Frontend — build de production

```
$ npm install
added 398 packages in 7s

$ npm run build
✓ 3751 modules transformed.
✓ built in 13.39s
```

Aucune erreur de compilation. Un avertissement pré-existant sur la taille du
bundle principal (>500 kB) subsiste — non lié à cette itération, non
corrigé (hors périmètre : découpage en chunks à faire dans une itération
dédiée à la performance).

## 5. Frontend — lint

```
$ npm run lint
✖ 60 problems (0 errors, 60 warnings)
```

**0 erreur.** Les 60 avertissements sont très majoritairement pré-existants
(imports inutilisés dans des fichiers non touchés, dépendances de hooks
`useEffect`/`useMemo` déjà présentes avant cette itération). Un seul
avertissement nouveau, dans le fichier créé
`frontend/src/pages/shared/AccountProfile.jsx` :
`Compilation Skipped: Use of incompatible library` sur `watchPwd(...)` —
avertissement du React Compiler concernant `react-hook-form`, présent à
l'identique dans les formulaires teacher/parent/student déjà livrés
(`Profile.jsx`, `Admins.jsx`) ; **pas une erreur**, comportement déjà
accepté dans le reste du projet.

## 6. Vérification de la dérive de migrations

```
$ DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres python manage.py makemigrations --check --dry-run
Migrations for 'parents': ...
Migrations for 'students': ...
Migrations for 'subjects': ...
Migrations for 'attendance': ...
Migrations for 'bulletins': ...
Migrations for 'grades': ...
Migrations for 'payments': ...
```

Dérive **déjà présente avant cette itération** (déjà documentée dans
`CORRECTIONS_PREVIOUS.md`). Aucun champ de modèle n'a été modifié dans
cette itération — seule une méthode a été ajoutée à `Grade`
(`get_annual_subject_averages`), qui ne génère aucune migration. Vérifié en
comparant la sortie ci-dessus avant/après mes changements : identique.

## 7. Lint Python (ruff) sur les fichiers modifiés

```
$ ruff check apps/notifications/utils.py apps/dashboard/views.py apps/grades/models.py \
    apps/grades/views.py apps/attendance/views.py apps/payments/views.py \
    apps/messaging/views.py tests/test_priority_fixes.py --select F
```

6 problèmes détectés, **tous pré-existants** (imports inutilisés, variable
non utilisée) situés dans des sections de code non touchées par cette
itération — vérifié ligne par ligne, aucun n'est dans le code que j'ai
ajouté ou modifié.

## 8. Ce qui n'a PAS pu être testé (déclaré honnêtement)

- **Rendu réel dans un navigateur** (clic effectif sur une notification, un
  bouton, navigation visuelle) : aucun outil E2E (Cypress/Playwright)
  n'existe dans le projet, et Docker n'est pas disponible dans cet
  environnement d'exécution sandboxé — impossible de démarrer
  simultanément le backend Django, le frontend Vite, Redis, MinIO et un
  navigateur piloté. Les corrections ont donc été validées au niveau API
  (backend) et build/lint (frontend), pas via un scénario utilisateur
  complet dans un navigateur.
- **Redis / Celery / MinIO / Jitsi** : non démarrés dans cet environnement
  (pas nécessaires pour les trois corrections de cette itération, qui ne
  touchent ni fichiers, ni tâches asynchrones, ni visio).
- **Audit exhaustif des ~25 modules** demandé dans le cahier des charges :
  non mené (voir « Audit global — état honnête » dans `CORRECTIONS.md`).

## Environnement utilisé

- PostgreSQL 16 installé et démarré localement (`apt-get install postgresql`),
  base `feba_test`, migrations appliquées normalement.
- Python 3.12, dépendances installées via
  `pip install -r requirements/dev.txt` + `psycopg2-binary`.
- Node.js 22, npm 10, dépendances installées via `npm install`.
- Paramètres de test : `feba_project/settings/test_postgres.py` (nouveau,
  cache en mémoire, rate-limit désactivé pour éviter les échecs en cascade
  documentés dans `dev.py`).
