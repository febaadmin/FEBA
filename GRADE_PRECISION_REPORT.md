# GRADE_PRECISION_REPORT.md — Note 10 conservée exactement (V7-P4, 25/07/2026)

## 1. Symptôme

En saisissant **10**, l'application enregistrait/affichait parfois **9,5** ou
**9,75**.

## 2. Cause racine (frontend, PAS backend)

Les champs de note étaient des `<input type="number" step="0.25">`
(enseignant `Grades.jsx:309`, admin `Grades.jsx:966`, saisie groupée
`step="0.01"`). Un champ numérique **focalisé** modifie **silencieusement** sa
valeur de ± `step` :

- **molette de la souris** (faire défiler la page = le geste accidentel le plus
  courant) : 10 → 9,75 → 9,5 ;
- **flèches ↑/↓** du clavier ;
- **compteurs** (spinners) du champ.

Aucune garde (`onWheel`, etc.) n'existait. Le backend, lui, était **sain** :
`Grade.value = DecimalField(max_digits=4, decimal_places=2)`, jamais transformé
à l'enregistrement (le serializer ne fait aucune arithmétique sur `value`).

## 3. Traçage de la note 10 (avant → après)

| Étape | Avant (bug) | Après (V7) |
|---|---|---|
| Champ frontend | `type=number step=0.25` → altérable molette/flèche | **`type=text inputMode=decimal`** — insensible |
| État du formulaire (RHF) | `"9.75"` (déjà altéré) | `"10"` |
| Payload envoyé | `"9.75"` | `"10"` (normalisé, jamais changé) |
| Serializer DRF | `Decimal("9.75")` | `Decimal("10.00")` |
| Valeur en base | `9.75` | **`10.00`** |
| Réponse API | `"9.75"` | `"10.00"` |
| Tableau | `9.75/20` | `10.00/20` |
| Bulletin | `9.75/20` | **`10.00/20`** |

## 4. Correctif

- **Champs de note → texte** (`type="text" inputMode="decimal"`) sur les trois
  formulaires (enseignant, admin, saisie groupée) : plus de compteur, de pas,
  de molette ni de flèche qui modifient la valeur. Clavier numérique conservé
  sur mobile via `inputMode`.
- **Normalisation** (`utils/gradeInput.js`) : virgule française → point,
  caractères parasites retirés — **sans jamais changer la valeur** (« 10 »
  reste « 10 » ; bonus : « 10,5 » → « 10.5 »).
- **Garde globale anti-molette** (`utils/useNumberInputGuard.js`, montée dans
  `App`) pour les autres champs numériques restants (coefficients, montants).
- Aucune transformation « magique » : pas de `if score == 10`, pas d'arrondi
  d'affichage masquant la base.

## 5. Preuves (tests)

- **Frontend** (`utils/gradeInput.test.js`, 8 cas) : « 10 » reste « 10 » ;
  valeurs `0 … 20` conservées ; virgule ; bornes ; signe négatif neutralisé.
- **Backend** (`tests/test_grade_precision.py`, 5 cas) :
  - `POST /api/grades/` value `"10"` → base `10.00` **et** API `10.00` ;
  - **14 valeurs** `0, 0.25, 0.5, 1, 9.5, 9.75, 10, 10.25, 10.5, 10.75, 15,
    19.5, 19.75, 20` conservées à l'identique ;
  - saisie groupée `"10"` → `10.00` ; décimales conservées ;
  - modification d'une note → valeur conservée.
- **Navigateur** (session enseignant réelle) : le champ note est désormais
  `type=text inputMode=decimal` ; « 10 » reste « 10 » après molette + flèche bas
  (capture du formulaire « Mes Notes » à l'appui) ; bulletin réel généré → note
  Maths **10.00/20**.

Fonctionne pour **Enseignant, Admin, Super administrateur**, en **saisie simple
et groupée**, à la **création et à la modification**.
