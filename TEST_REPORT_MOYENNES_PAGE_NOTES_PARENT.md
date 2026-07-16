# TEST_REPORT — Correctif moyennes page « Notes » Parent

Voir `CORRECTIONS_MOYENNES_PAGE_NOTES_PARENT.md` pour le détail du
diagnostic et des corrections. Toutes les commandes ci-dessous ont été
**réellement exécutées** dans l'environnement de travail contre un vrai
PostgreSQL 16 + Redis (services installés et démarrés pour la durée de la
validation), avec les données de démonstration réelles (`seed_demo_data`).

## 1. Environnement

```
$ apt-get install -y postgresql redis-server
$ service postgresql start && service redis-server start
$ createuser feba_user / createdb feba_dev (mêmes identifiants que .env.dev)
$ python manage.py migrate                     # 100+ migrations, 0 erreur
$ python manage.py seed_demo_data               # établissement complet, notes réelles
$ python manage.py runserver 0.0.0.0:8000
```

## 2. Reproduction du bug AVANT correction (preuve)

```
$ curl .../api/grades/averages/?student=1&school_year=3
{"average": null, "student": "1", "period": null, "by_subject": {}}
```
→ `average: null` confirmé alors que l'élève a des notes en T1/T2.

## 3. Backend — suite complète après correction

```
$ DATABASE_URL=postgresql://feba_user:feba_dev_pass@localhost:5432/feba_dev \
  REDIS_URL=redis://localhost:6379/0 \
  python -m pytest tests/ -q
====================== 202 passed, 149 warnings in 16.07s ======================
```
192 tests pré-existants (0 régression) + 10 nouveaux tests dédiés
(`tests/test_parent_averages_missing_period.py`) = 202. **0 échec, 0
erreur.**

Détail des 10 nouveaux tests :
```
tests/test_parent_averages_missing_period.py::CalculateAverageMissingPeriodTests::test_period_none_equals_annual PASSED
tests/test_parent_averages_missing_period.py::CalculateAverageMissingPeriodTests::test_period_none_matches_manual_calculation PASSED
tests/test_parent_averages_missing_period.py::CalculateAverageMissingPeriodTests::test_specific_period_still_scoped_correctly PASSED
tests/test_parent_averages_missing_period.py::CalculateAverageMissingPeriodTests::test_student_with_no_grades_returns_none_not_crash PASSED
tests/test_parent_averages_missing_period.py::ParentAveragesEndpointTests::test_averages_no_period_matches_explicit_annual PASSED
tests/test_parent_averages_missing_period.py::ParentAveragesEndpointTests::test_averages_no_period_param_returns_value_for_child1 PASSED
tests/test_parent_averages_missing_period.py::ParentAveragesEndpointTests::test_bilingual_no_period_nested_annual_matches_flat_keys PASSED
tests/test_parent_averages_missing_period.py::ParentAveragesEndpointTests::test_child_without_english_grades_reports_none_not_zero PASSED
tests/test_parent_averages_missing_period.py::ParentAveragesEndpointTests::test_each_child_gets_its_own_averages_not_mixed_up PASSED
tests/test_parent_averages_missing_period.py::ParentAveragesEndpointTests::test_parent_cannot_fetch_averages_of_unrelated_student PASSED
```

## 4. Vérification API APRÈS correction (mêmes comptes réels)

```
$ curl .../api/grades/averages/?student=1&period=annual&school_year=3
{"average": 12.74, "student": "1", "period": "annual", "by_subject": {}}

$ curl .../api/grades/bilingual/?student=1&period=annual&school_year=3
{"annual": {"fr_average": 13.17, "en_average": 12.15, "bilingual_average": 12.76, ...}}
```
Valeurs confirmées par calcul manuel (voir `CORRECTIONS_MOYENNES_PAGE_NOTES_PARENT.md`).

Testé pour les deux enfants du compte `parent1@feba.bj` (Koffi Codjo,
Sègun Dossou) et pour toutes les valeurs de période (``, T1, T2, T3,
annual) : plus aucune valeur `null` inattendue là où des notes existent
réellement ; `null` propre (et non `0`) là où une catégorie n'a
effectivement aucune note (ex. T3, ou anglais pour un enfant qui n'a que
du français).

## 5. Frontend

```
$ npm install
$ npm run build
✓ built in ~9s, 0 erreur
```

## 6. Limitation constatée

Pas de navigateur headless disponible dans cet environnement d'exécution
(pas d'accès réseau vers les CDN de téléchargement Chromium/Playwright) —
voir la section dédiée dans `CORRECTIONS_MOYENNES_PAGE_NOTES_PARENT.md`
pour la méthode de preuve utilisée à la place et la recommandation de
confirmation visuelle finale.
