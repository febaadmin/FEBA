# GRADE_WEIGHTING_REPORT.md — Poids des évaluations (V8-P4, 26/07/2026)

## 1. Règle métier

**Toutes les évaluations d'une même matière pèsent 1**, quel que soit leur type
(devoir, interrogation / devoir de classe, contrôle, examen / évaluation,
travaux pratiques, autre). Un examen ne compte **plus** davantage qu'une
interrogation.

## 2. Deux notions désormais distinctes (elles étaient confondues)

| | Notion | Où | Valeur |
|---|---|---|---|
| **A** | **Poids de l'évaluation** (`assessment weight`) | `Grade.note_coefficient` | **toujours 1** |
| **B** | **Coefficient de la matière** (`subject coefficient`) | `Subject.coefficient` | **inchangé** — pondère les MATIÈRES entre elles dans la moyenne générale |

Source unique de vérité : **`apps/grades/grading.py`** (`ASSESSMENT_WEIGHT`,
`subject_average`, `normalize_to_reference`). Aucune formule dupliquée dans les
modèles, serializers, bulletins, exports ou le frontend — le **backend** est
l'autorité.

## 3. Formule

```
moyenne_matière = somme des notes valides / nombre de notes valides
```

Barèmes hétérogènes → normalisation préalable :
`note_sur_20 = note ÷ barème × 20` (ex. 45/50 → 18).

### Données incluses / exclues

| Cas | Traitement |
|---|---|
| Note valide (y compris **0 réel**) | **incluse** |
| Matière « non notée » | **exclue** — elle ne vaut pas 0 et n'écrase pas la moyenne |
| Note supprimée (`is_deleted`) | exclue |

## 4. Tableau de vérification (résultats réellement obtenus)

| Notes | Types | Coefficients d'évaluation | Calcul | Résultat attendu | Résultat obtenu |
|---|---|---|---|---|---|
| **12 et 5** | **Interrogation + Examen** | **1 et 1** | **(12 + 5) / 2** | **8,5** | **8,50 ✅** |
| 10 et 10 | Devoir + Contrôle | 1 et 1 | (10+10)/2 | 10 | 10 ✅ |
| 0 et 20 | Devoir + Examen | 1 et 1 | (0+20)/2 | 10 | 10 ✅ |
| 10 (seule) | Devoir | 1 | 10/1 | 10 | 10 ✅ |
| 10,5 et 9,5 | Interrogation + TP | 1 et 1 | (10,5+9,5)/2 | 10 | 10 ✅ |
| 12, 5, 10 | 3 types différents | 1, 1, 1 | (12+5+10)/3 | 9 | 9 ✅ |
| 8, 12, 16, 4, 20 | 5 notes | 1 ×5 | somme/5 | 12 | 12 ✅ |
| 0 et 10 | Devoir + Examen (0 réel) | 1 et 1 | (0+10)/2 | 5 | 5 ✅ |
| — et 10 | Non noté + Devoir | — et 1 | 10/1 | 10 (le « non noté » n'est pas 0) | 10 ✅ |
| 45/50 et 16/20 | Barèmes différents | 1 et 1 | (18+16)/2 | 17 | 17 ✅ |

Le cas imposé **12 + 5 → 8,50** est vérifié **de bout en bout**, pour la saisie
simple **et** groupée.

### Rejoué par l'INTERFACE réelle (26/07/2026)

Les deux notes ont été saisies dans le formulaire de l'espace Enseignant
(Marie Dossou → Estelle Acakpo, Français, T3) : « Interrogation / Devoir de
classe » **12** puis « Examen / Évaluation » **5** — deux `POST /api/grades/`
en **201**, aucun champ de poids dans le formulaire.

| Contrôle | Résultat |
|---|---|
| Base (`Grade`) | `12.00` et `5.00`, `note_coefficient = 1` pour les deux |
| API (`/grades/student-summary/`) | `"average": 8.5` |
| Espace **Enseignant** | 8,5 |
| Espace **Administrateur** | 8,5 |
| Espace **Super administrateur** | 8,5 |
| Espace **Parent** | 8,5 |
| Espace **Élève** | 8,5 |
| **Bulletin PDF** (CE1 → /10) | `E:2.50 I:6.00` → **4.25/10** (≡ 8,50/20), pondérée 17.00 (coeff 4) |
| **Export CSV** | colonne de poids supprimée ; note exportée `12.00` / `5.00` |

## 5. Application de la règle

| Niveau | Mécanisme |
|---|---|
| Base | `Grade.save()` ramène systématiquement `note_coefficient` à 1 |
| API | Le serializer **normalise** toute valeur reçue (envoyer 2 ou 3 n'accorde aucun avantage) ; `note_coefficient` est en lecture seule sur `GradeSerializer` |
| Interface | Champ retiré de la saisie simple et de la saisie groupée ; **colonnes « Poids » / « Coeff note » supprimées** des listes Enseignant, Admin et Élève, ainsi que du panneau de détail et des exports |
| État React | Plus aucun `note_coefficient` dans les états de formulaire : il n'est plus relu depuis une note existante, donc **aucun payload ne peut envoyer autre chose que 1** |
| Textes | « Examen = 3, devoir = 1 » supprimé partout, y compris les traductions désormais orphelines (« Poids », « Coeff note ») |

Le **coefficient de matière** reste affiché là où il a du sens (colonne
« Coeff » alimentée par `subject_coefficient`) : les deux notions ne se
confondent plus nulle part dans l'interface.

### Surfaces de saisie auditées (V8, toutes vérifiées)

| Profil | Saisie simple | Saisie groupée | Modification | Affichage détaillé | Export |
|---|---|---|---|---|---|
| Enseignant | ✅ aucun champ de poids | ✅ colonne supprimée | ✅ n'envoie que valeur/période/type/commentaire | ✅ colonne supprimée | — |
| Administrateur | ✅ | ✅ | ✅ poids forcé à 1 dans le payload | ✅ ligne « Coefficient » retirée | ✅ colonne retirée |
| Super administrateur | ✅ (mêmes écrans) | ✅ | ✅ | ✅ | ✅ |

Les formulaires mobile et desktop sont **le même composant responsive** : il
n'existe pas de variante mobile distincte pouvant conserver l'ancien champ.

## 6. Migration des données existantes

`apps/grades/migrations/0011_assessment_weight_one.py` :

1. **Rapport AVANT** — nombre de notes dont le poids ≠ 1, répartition des poids,
   nombre de moyennes (élève × matière × période) susceptibles de changer ;
2. **Exécution** — `note_coefficient = 1` ;
3. **Vérification APRÈS** — échec explicite s'il subsiste un poids ≠ 1.

Exemple de sortie réelle :

```
[V8] Poids d'évaluation → 1 : 2 note(s) concernée(s) (répartition {2: 1, 3: 1}) ;
     1 moyenne(s) élève×matière×période susceptible(s) de changer.
[V8] Vérification OK : toutes les évaluations pèsent 1.
```

**Les notes elles-mêmes ne sont pas modifiées** — seul leur poids change. Les
moyennes sont recalculées à la volée (aucun cache de moyenne persisté).
Sauvegarde et restauration : voir `RESTORE_GUIDE.md` (dump SQL avant migration ;
les anciens poids hétérogènes ne sont pas reconstituables autrement).

## 6 bis. Défaut corrigé : la base de démonstration échappait à la migration

La base de démonstration était préparée par `migrate --run-syncdb` puis
`seed_demo_data`. Or les réglages `dev_sqlite` **neutralisent la chaîne de
migrations** (`MIGRATION_MODULES = _DisableMigrations()`) : le schéma était bien
créé à partir des modèles, mais **aucune migration de données ne s'exécutait**.
La migration `grades/0011` était donc systématiquement sautée. S'ajoutait une
seconde cause : le seed lui-même tirait le poids au hasard
(`random.choice([1, 1, 2])`), héritage de l'ancienne règle.

Conséquence : une **installation de démonstration** pouvait afficher des
moyennes fausses, alors qu'une installation réelle (PostgreSQL, chaîne complète)
était correcte. Le problème serait revenu à chaque nouvelle installation.

**Correction du processus, pas seulement de la base locale :**

1. `seed_demo_data` écrit désormais `note_coefficient=ASSESSMENT_WEIGHT` ;
2. nouvelle commande **`python manage.py bootstrap_demo`** : migrations →
   migrations de **données** V8 (rejouées explicitement si la chaîne est
   neutralisée) → seeds → **vérification bloquante** ;
3. la vérification échoue avec un code de sortie non nul s'il subsiste un poids
   ≠ 1 (`--check-only` permet de l'exécuter seule) ;
4. `README.md` et `CORRECTIONS.md` ne documentent plus que cette commande.

Sortie réelle sur une base neuve :

```
4. Vérification des poids d'évaluation
  nombre de notes avec poids d'évaluation != 1 = 0   (sur 2400 note(s))
  ✔ conforme
```

### État des sources de données

| Source de données | Migration appliquée | Notes avec poids ≠ 1 avant | Après | Statut |
|---|---|---|---|---|
| Démo SQLite **existante** (créée avant le correctif) | ❌ non — chaîne neutralisée | **796** (sur 2 402) | **0** | ✅ réparée par `bootstrap_demo` |
| Démo SQLite **neuve** (`bootstrap_demo`) | ✅ oui — `grades/0011` rejouée explicitement | **0** (seed corrigé) | **0** | ✅ conforme |
| **PostgreSQL 16** (installation réelle, chaîne complète) | ✅ oui — `grades/0011` + `0012` | **0** | **0** | ✅ conforme |
| Base de test (`--no-migrations`) | ✅ logique testée directement | **3** (injectés en SQL brut) | **0** | ✅ vérifié par test |

## 7. Tests

- `tests/test_grade_weighting_and_scale.py` (19 cas) — tous les cas du tableau
  ci-dessus, saisie simple/groupée, enseignant/admin/superadmin.
- `tests/test_data_migrations.py` (5 cas) — la migration normalise les poids,
  ne modifie pas les notes, produit bien 8,50 après coup, et est **idempotente**.
- Test hérité `test_weighted_by_note_and_subject_coefficients` **adapté** : il
  vérifiait l'ANCIENNE pondération par note, explicitement remplacée par cette
  règle métier (changement documenté dans le test lui-même).
