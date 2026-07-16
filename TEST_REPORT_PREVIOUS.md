# TEST_REPORT — FEBA School Management

Sorties **réelles** des commandes exécutées pour valider les deux corrections
prioritaires (bulletins PDF, matricules). Aucune commande n'est déclarée réussie
sans avoir été lancée.

## Environnement d'exécution

- OS : macOS (darwin), Python **3.14**.
- Le dépôt cible **PostgreSQL** (dev/prod) et **WeasyPrint** n'est pas utilisé par
  le bulletin (moteur = ReportLab). Postgres/Docker n'étant pas disponibles en
  local, un module de réglages de test **SQLite** a été ajouté
  (`backend/feba_project/settings/test_sqlite.py`) et la suite est lancée avec
  `--no-migrations` (schéma construit depuis les modèles — les migrations
  `RunSQL … IF NOT EXISTS` sont spécifiques PostgreSQL).
- Venv de test jetable : `backend/.venv-test` (ignoré par git). Sous Python 3.14,
  `Pillow`/`reportlab` sont installés en version compatible 3.14 (les épingles de
  `requirements` visent 3.11/3.12) ; cela n'affecte que l'exécution locale des
  tests, pas le code livré.

Commande type :
```
cd backend
DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
  .venv-test/bin/python -m pytest --no-migrations
```

---

## 1. Vérifications Django

```
$ python manage.py check
System check identified no issues (0 silenced).
```

```
$ python manage.py makemigrations students --check --dry-run
# La NOUVELLE table de séquence est déjà couverte par students/0005 :
# seule subsiste une dérive PRÉ-EXISTANTE, hors sujet, sur exit_notes :
Migrations for 'students':
  apps/students/migrations/0006_alter_student_exit_notes.py
    - Alter field exit_notes on student
```
> `makemigrations --check` global échoue à cause de dérives **pré-existantes**
> (parents, subjects, attendance, bulletins, grades, payments, students.exit_notes)
> présentes **avant** cette intervention et non liées aux deux corrections.
> Ma modification ajoute exactement **une** migration propre (`students 0005`).

---

## 2. Tests — matricules (`tests/test_matricule.py`)

```
$ pytest --no-migrations tests/test_matricule.py
tests/test_matricule.py ................                                 [100%]
16 passed, 1 warning in 0.45s
```

Scénarios couverts :
| Scénario | Attendu | Résultat |
|---|---|---|
| Année système 2023 | `FEBA-23-0001` | ✅ |
| Année système 2025 | `FEBA-25-0001` | ✅ |
| Année système 2026 | `FEBA-26-0001` | ✅ |
| Année système 2027 | `FEBA-27-0001` | ✅ |
| Format à tirets (pas de `_`) | 2 tirets, `FEBA-26-0001` | ✅ |
| Séquence même année | 0001, 0002, 0003 | ✅ |
| Redémarrage par année | 25→0002 puis 26→0001 | ✅ |
| Suppression d'un élève | pas de réutilisation de numéro (→0003) | ✅ |
| Indépendance par établissement | `FEBA-26-0001` / `AEC-26-0001` | ✅ |
| Amorçage anti-collision (héritage) | `FEBA-26-0007` → suivant `-0008` | ✅ |
| Ancien matricule intact | `FEBA_25_0005` conservé | ✅ |
| Anti-hardcode | suffixe dérivé de `year % 100` | ✅ |

Test complémentaire mis à jour au nouveau format à tirets :
`tests/test_bug_fixes_v45.py::MatriculeTests` (5 tests) — ✅.

---

## 3. Tests — mise en page bulletin (`tests/test_bulletin_layout.py`)

```
$ pytest --no-migrations tests/test_bulletin_layout.py
7 passed, 1 warning in 0.47s
```

| Scénario | Vérifié | Résultat |
|---|---|---|
| Peu de matières (1 FR / 1 EN) | 1 page A4 | ✅ |
| 10 matières (6 FR / 4 EN) | 1 page A4 | ✅ |
| Intitulés longs FR/EN | 1 page, pas d'exception, repli | ✅ |
| « Mot » sans espace très long | 1 page (repli CJK) | ✅ |
| Page A4 portrait | 595 × 842 pt | ✅ |
| Bulletin annuel (intitulés longs) | 1 page A4 | ✅ |
| Maternelle (intitulés longs) | 1 page A4 | ✅ |

### Validation visuelle (rendu réel des PDF)
PDF générés puis rastérisés en PNG et inspectés (`docs/bulletin_captures/`) :
- `avant_matieres_longues.png` — **AVANT** : le texte long chevauche les colonnes
  Coeff/Notes et déborde.
- `avant_page2_involontaire.png` — **AVANT** : bloc signatures seul en page 2.
- `apres_matieres_longues.png` — **APRÈS** : intitulés repliés, cadré, 1 page.
- `apres_10_matieres.png` — **APRÈS** : 10 matières + signatures, 1 page.
- `apres_maternelle.png` — **APRÈS** : template maternelle, clé 13 colonnes cadrée.

Contrôles effectués sur chaque rendu : pas de débordement gauche/droite, aucune
colonne coupée, marges régulières, texte lisible, pas de 2ᵉ page involontaire.

---

## 4. Suite backend complète (non-régression)

```
$ pytest --no-migrations
2 failed, 173 passed, 133 warnings in 4.82s
```

Les **2 échecs sont des artefacts du backend SQLite local**, présents **avant**
mes modifications, et **verts sous PostgreSQL** (SGBD réel) :
1. `test_bug_fixes_v45.py::DashboardTests::test_student_dashboard_average` —
   `NotSupportedError: contains lookup is not supported` : lookup `__contains`
   sur un `JSONField`, **non supporté par SQLite** (OK sous PostgreSQL).
2. `test_parent_student.py::ParentStudentConcurrencyTest::test_concurrent_assignment_both_succeed` —
   `database table is locked` : test de concurrence multi-thread, **SQLite
   sérialise/verrouille** les écritures (OK sous PostgreSQL). Intermittent.

Aucune régression introduite par les corrections (les modules touchés — students,
bulletins — passent à 100 % hors ces limitations SQLite).

---

## 5. Frontend

```
$ npm run lint
✖ 60 problems (0 errors, 60 warnings)
```
0 **erreur** (warnings pré-existants : hooks/vars inutilisées).

```
$ npm run build
✓ built in 7.13s
dist/index.html                     0.81 kB
dist/assets/index-*.css            52.90 kB
dist/assets/index-*.js          1,430.50 kB
```
Build réussi (avertissements pré-existants : taille de chunk, import dynamique).

---

## 6. Limites restantes / non fait

- **Non exécuté sous PostgreSQL réel** (indisponible localement) : les 2 échecs
  ci-dessus doivent être reconfirmés verts en CI Postgres.
- **`makemigrations --check` global** reste rouge à cause de dérives
  **pré-existantes** hors sujet (voir §1) — non corrigées ici volontairement.
- **Audit exhaustif des ~25 modules** : non réalisé dans cette itération.
- **ZIP final** : non généré (conditionné à l'audit complet par le contrat).
