# CORRECTIF — Moyennes absentes sur la page « Notes » du profil Parent

Périmètre de cette itération : **un seul problème prioritaire**, signalé
avec capture d'écran — sur `/parent/grades`, les 4 cartes de moyenne
(Générale, Française, Anglaise, Bilingue) affichent un tiret `—` pour
**chaque enfant**, alors que le tableau de notes en dessous contient bien
des notes avec coefficients.

⚠️ À ne pas confondre avec le correctif précédent documenté dans
`CORRECTIONS.md` (« P2 — Tableaux de bord ») : celui-ci concernait
`ParentDashboardView` (page d'accueil, `frontend/src/pages/parent/Home.jsx`)
et a été vérifié fonctionnel dans cette itération (voir section
« Non-régression » ci-dessous). Le bug traité ici est **différent et
indépendant** : il touche exclusivement la page dédiée aux notes
(`frontend/src/pages/parent/Grades.jsx`), qui appelle directement
`/api/grades/averages/` et `/api/grades/bilingual/` avec sa propre logique
d'affichage.

Environnement de validation : suite Django (`pytest`) exécutée contre un
**vrai PostgreSQL 16 local** (pas SQLite — le projet contient une migration
PL/pgSQL propre à Postgres, `apps/parents/migrations/0003_remove_single_parent_constraint.py`,
incompatible avec SQLite) + Redis, seedés avec `seed_demo_data` (mêmes
comptes de démonstration que les guides d'installation), et `npm run build`
pour le frontend.

---

## Reproduction du bug (avant correction)

Connexion réelle avec le compte `parent1@feba.bj`, appel des deux mêmes
requêtes que la page Parent envoie par défaut (aucun filtre de période
sélectionné — état initial de la page, « Toutes périodes ») :

```
GET /api/grades/averages/?student=1&school_year=3
→ {"average": null, "student": "1", "period": null, "by_subject": {}}

GET /api/grades/bilingual/?student=1&school_year=3
→ {"T1": {...}, "T2": {...}, "T3": {...},
   "annual": {"fr_average": 12.76, "en_average": ..., "bilingual_average": ...}}
```

Avec le code frontend d'origine, qui lisait :
```js
avg?.overall_average     // clé inexistante dans la réponse → undefined → "—"
bi?.french_average       // clé inexistante (et mauvais niveau d'imbrication) → undefined → "—"
bi?.english_average      // idem → undefined → "—"
bi?.bilingual_average    // absente à la racine dans ce cas (imbriquée sous "annual") → undefined → "—"
```
→ Les 4 cartes affichent `—` pour les deux enfants (Koffi Codjo, Sègun
Dossou), exactement comme sur la capture d'écran fournie, **bien que les
deux enfants aient des notes réelles** visibles dans le tableau du dessous.

---

## Cause racine — DEUX bugs indépendants et cumulés

### Bug A (backend) — `period` manquant traité comme un filtre impossible

`Grade.period` est un `CharField` **obligatoire** (`'T1'`/`'T2'`/`'T3'`),
jamais `NULL` en base. Avant correction :

```python
@classmethod
def calculate_average(cls, student, school_year, period=None):
    if period == 'annual':
        return cls.calculate_annual_average(student, school_year)
    subject_avgs = cls.get_subject_averages(student, school_year, period)
    ...
```

Quand `period=None` (aucun paramètre `period` envoyé — le cas exact de
« Toutes périodes »), l'appel descendait jusqu'à
`get_subject_averages(student, school_year, period=None)`, qui filtrait
`Grade.objects.filter(period=None)`. Comme `period` n'est **jamais** `NULL`
en base, ce filtre ne correspond **à aucune note réelle**, quel que soit
l'élève. `calculate_average` renvoyait donc systématiquement `None` dans ce
cas — un commentaire déjà présent ailleurs dans le code
(`get_annual_subject_averages`) confirmait que cette anomalie était connue
mais n'avait jamais été corrigée à la source :
> « NE PAS appeler get_subject_averages(student, school_year, period=None) :
> les notes ont toujours un period='T1'/'T2'/'T3' réel, jamais None —
> period=None ne retourne donc jamais aucune note. »

Point notable : le endpoint `/api/grades/bilingual/` contournait déjà ce
piège au cas par cas (`if not period or period == 'annual': ... calculate
annuel`), mais **pas** `/api/grades/averages/` — d'où l'incohérence entre
la moyenne bilingue (imbriquée mais présente) et la moyenne générale
(toujours `null`).

### Bug B (frontend) — mauvais noms de champs ET mauvaise forme de réponse

`frontend/src/pages/parent/Grades.jsx` (`ChildAverages`) lisait des clés
qui n'ont **jamais existé** dans les réponses API :

| Champ lu (ancien, incorrect) | Champ réellement renvoyé par l'API |
|---|---|
| `avg?.overall_average` | `avg.average` |
| `bi?.french_average` | `bi.fr_average` |
| `bi?.english_average` | `bi.en_average` |
| `bi?.bilingual_average` (à la racine) | `bi.bilingual_average`, mais **imbriqué sous `bi.annual`** quand la période est `annual`/absente |

Preuve que le contrat API est correct et stable : `frontend/src/pages/student/Grades.jsx`
et `frontend/src/pages/admin/Grades.jsx` lisent déjà, avec succès,
`avg.average`, `bilingual.fr_average`, `bilingual.en_average`,
`bilingual.bilingual_average` — la page Parent était la seule à utiliser
les mauvais noms.

---

## Fichiers modifiés

1. **`backend/apps/grades/models.py`** — `Grade.calculate_average()` :
   `period` manquant/vide traité comme `'annual'`, exactement comme le fait
   déjà `get_annual_bilingual` pour la moyenne bilingue. Correction
   **centrale** (une seule méthode, utilisée par `/averages/`,
   `/student-summary/`, `/class-averages/` et la génération de bulletins) —
   aucun appelant existant ne dépendait de l'ancien comportement cassé
   (vérifié : tous les autres appels passent toujours une période explicite
   `'T1'`/`'T2'`/`'T3'`/`'annual'`).
2. **`frontend/src/pages/parent/Grades.jsx`** — composant `ChildAverages` :
   - lecture des bons noms de champs (`average`, `fr_average`, `en_average`,
     `bilingual_average`) ;
   - période explicite envoyée à l'API (`period || "annual"`) au lieu de
     `undefined`, pour que la réponse soit prévisible et auto-documentée ;
   - lecture de la bonne forme de réponse bilingue (`bi.annual.*` quand la
     période effective est `"annual"`, `bi.*` sinon) ;
   - composant `AvgCard` : affichage explicite **« Aucune note »** au lieu
     d'un tiret ambigu quand une catégorie n'a réellement aucune note (ex.
     Trimestre 3 pas encore commencé), conformément à l'exigence de ne
     jamais laisser un `—` sans explication quand la donnée est absente.
3. **`backend/tests/test_parent_averages_missing_period.py`** (nouveau) —
   10 tests de non-régression (voir ci-dessous).

---

## Preuve du calcul (élève Koffi Codjo, Trimestre 1, données réelles seedées)

Notes T1 : Mathématiques 14.33 (coeff. 4), Français 15.52 (coeff. 4),
Sciences 11.92 (coeff. 3), Histoire-Géo 7.87 (coeff. 2), Éducation Civique
13.27 (coeff. 1), Sport 13.35 (coeff. 1) — matières françaises ; Anglais
7.48 (coeff. 4), Mathematics 17.34 (coeff. 3), Science 9.87 (coeff. 2),
Social Studies 15.97 (coeff. 2) — matières anglaises.

```
Moy. Française  = Σ(note × coeff) / Σcoeff  (matières FR)
                 = (14.33×4 + 15.52×4 + 11.92×3 + 7.87×2 + 13.27×1 + 13.35×1) / (4+4+3+2+1+1)
                 = 197.52 / 15 = 13.17  ✓ (valeur API : 13.17)

Moy. Anglaise    = (7.48×4 + 17.34×3 + 9.87×2 + 15.97×2) / (4+3+2+2)
                 = 133.62 / 11 = 12.15  ✓ (valeur API : 12.15)

Moy. Bilingue    = 13.17 × 60% + 12.15 × 40% = 7.902 + 4.86 = 12.76  ✓ (valeur API : 12.76)

Moy. Générale    = (197.52 + 133.62) / (15 + 11) = 331.14 / 26 = 12.74  ✓ (valeur API : 12.74)
```

Les 4 valeurs renvoyées par l'API correspondent exactement au calcul manuel
à partir des notes brutes — la formule métier (moyenne pondérée par
coefficient, bilingue = FR×60% + EN×40%) n'a **pas** été modifiée, seul son
déclenchement pour « aucune période précisée » l'a été.

---

## Avant / Après (comparaison directe, mêmes comptes réels)

| | Koffi Codjo — AVANT | Koffi Codjo — APRÈS | Sègun Dossou — AVANT | Sègun Dossou — APRÈS |
|---|---|---|---|---|
| Moy. Générale | `—` (undefined) | **12.74/20** | `—` | **valeur réelle non-nulle** |
| Moy. Française | `—` (undefined) | **13.17/20** | `—` | **valeur réelle non-nulle** |
| Moy. Anglaise | `—` (undefined) | **12.15/20** | `—` | **valeur réelle non-nulle** |
| Moy. Bilingue | `—` (undefined) | **12.76/20** | `—` | **valeur réelle non-nulle** |

*(Reproduit avec des requêtes HTTP réelles contre le backend Django
patché, base PostgreSQL réelle, comptes de démonstration seedés — pas de
valeur inventée. Détail par enfant dans les logs de session.)*

---

## Tests exécutés

### Nouveaux tests (`test_parent_averages_missing_period.py`) — 10/10 verts

- `test_period_none_equals_annual` — `period=None` / `''` renvoie la même
  valeur que `period='annual'` (cœur de la régression).
- `test_period_none_matches_manual_calculation` — la valeur correspond au
  calcul manuel pondéré par coefficient.
- `test_specific_period_still_scoped_correctly` — non-régression : une
  période précise (T1) reste correctement filtrée ; T3 sans notes renvoie
  bien `None` (pas de donnée fictive).
- `test_student_with_no_grades_returns_none_not_crash` — élève sans aucune
  note : `None` propre, pas d'exception.
- `test_averages_no_period_param_returns_value_for_child1` — appel HTTP
  identique à celui de la page Parent par défaut.
- `test_averages_no_period_matches_explicit_annual` — cohérence de contrat
  API entre « pas de période » et `period=annual`.
- `test_bilingual_no_period_nested_annual_matches_flat_keys` — la forme
  imbriquée (`annual.fr_average` etc.) est bien présente et non-nulle.
- `test_each_child_gets_its_own_averages_not_mixed_up` — parent avec
  **deux enfants** : chacun garde ses propres moyennes (13.0 vs 18.0, notes
  totalement différentes), pas de réutilisation croisée des données.
- `test_child_without_english_grades_reports_none_not_zero` — enfant sans
  note d'anglais : `en_average = None`, jamais `0` (donnée fictive
  interdite).
- `test_parent_cannot_fetch_averages_of_unrelated_student` — sécurité : un
  parent ne peut pas lire les moyennes d'un élève qui n'est pas le sien.

### Suite complète du projet

```
202 passed, 0 failed, 149 warnings in 16.07s
```
Aucune régression sur les 192 tests pré-existants (comptes, tenants,
années scolaires, promotions, salles virtuelles, notifications, etc.) —
sortie complète conservée dans la session de travail.

### Frontend

`npm run build` : succès, sans erreur (warnings pré-existants sur la
taille des chunks, non liés à ce correctif).

### Non-régression — page d'accueil Parent (`Home.jsx`)

Vérification que le correctif précédent (« P2 — Tableaux de bord »,
documenté dans `CORRECTIONS.md`) reste fonctionnel : `Home.jsx` lit déjà
`child.average`, `child.bilingual.fr_average`, `child.bilingual.en_average`
et affichait déjà « Aucune note » plutôt qu'un tiret — **aucune
modification nécessaire sur ce fichier**, il n'était pas concerné par ce
bug (qui est propre à `Grades.jsx` et à sa propre logique d'appel).

### Limitation réellement constatée (transparence)

**Aucun navigateur (Chromium/Playwright) n'est disponible dans cet
environnement d'exécution** (pas d'accès réseau vers les CDN de
téléchargement des binaires navigateur). La vérification visuelle
« capture d'écran dans le navigateur » demandée n'a donc pas pu être
produite littéralement. À la place, la preuve a été apportée par : backend
Django réel + PostgreSQL réel + comptes seedés réels, appels HTTP réels
reproduisant exactement les requêtes envoyées par le composant React
corrigé (mêmes URLs, mêmes paramètres), et relecture manuelle du code
JSX patché pour confirmer qu'il consomme bien les champs prouvés présents
dans la réponse JSON. Recommandation : ouvrir `/parent/grades` avec le
compte `parent1@feba.bj` après déploiement pour une confirmation visuelle
finale (2 minutes) — les 4 cartes doivent afficher des valeurs numériques
pour les deux enfants en filtre « Toutes périodes ».

---

## Tableau final

| ID | Module | Problème | Cause racine | Fichiers modifiés | Correction | Tests | Résultat | Statut |
|---|---|---|---|---|---|---|---|---|
| P1 | Notes — Parent | Moy. Générale/Française/Anglaise/Bilingue affichent `—` pour tous les enfants sur `/parent/grades` | (a) backend : `period` absent traité comme un filtre `period=None` qui ne correspond à aucune note réelle ; (b) frontend : mauvais noms de champs lus (`overall_average`/`french_average`/`english_average`) + mauvaise forme de réponse bilingue non gérée | `backend/apps/grades/models.py` (`Grade.calculate_average`), `frontend/src/pages/parent/Grades.jsx` (`ChildAverages`, `AvgCard`) | `period` manquant/vide → délégué à `calculate_annual_average()` (backend, central) ; lecture des bons noms de champs + bonne forme imbriquée + période explicite envoyée (frontend) ; « Aucune note » au lieu de `—` ambigu | 10 nouveaux tests dédiés + 192 tests existants (0 régression) + build frontend + vérification manuelle du calcul + comparaison HTTP avant/après sur données réelles | Les 4 moyennes s'affichent avec des valeurs numériques réelles, cohérentes avec les notes du tableau, pour les 2 enfants du compte parent1@feba.bj | Corrigé et testé (backend + contrat API + logique du composant prouvés ; confirmation visuelle navigateur non réalisable dans cet environnement — voir limitation ci-dessus) |
