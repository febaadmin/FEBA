# GRADING_SCALE_REPORT.md — Barèmes par niveau (V8-P5, 26/07/2026)

## 1. Règle métier

- **Niveaux 1 à 11** (Garderie → CM2) : moyennes affichées **sur 10** ;
- **Niveaux 12 et au-delà** (Collège, Lycée) : moyennes **sur 20** (inchangé).

Conversion : `moyenne_sur_10 = moyenne_sur_20 ÷ 2`.

## 2. Détermination du niveau — champ STABLE

Le barème est déduit de **`Level.order`**, champ déjà présent et stable — jamais
du libellé de la classe. Aucune liste de noms de classes en dur nulle part.

```python
def get_grading_scale(level):
    if 1 <= level.order <= PRIMARY_MAX_LEVEL_ORDER:   # 11
        return Decimal("10")
    return Decimal("20")                              # référence
```

Sans niveau identifiable, on conserve prudemment le barème de référence /20.

## 3. Architecture : une seule conversion

| Étage | Échelle |
|---|---|
| Stockage des notes (`Grade.value`) | **/20** (inchangé) |
| Calculs internes (moyennes matière, FR, EN, bilingue, générale, stats) | **/20** |
| **Affichage** (bulletin PDF) | **/10 ou /20** selon le niveau |

`convert_average_for_scale()` est appelée **une seule fois**, au moment du
rendu. Il n'y a **aucune division en cascade** : les fonctions de calcul ne
reçoivent jamais une valeur déjà convertie.

## 4. Tableau de conversion (résultats obtenus)

| Niveau | Échelle attendue | Moyenne interne /20 | Valeur affichée | Dénominateur | Appréciation | Statut |
|---|---|---|---|---|---|---|
| 1 (Garderie) | /10 | 15 | **7.50** | /10 | SATISFAISANT | ✅ |
| 2 (Maternelle 1) | /10 | 20 | **10.00** | /10 | EXCELLENT | ✅ |
| 3–10 (Maternelle 2 → CM1) | /10 | 8,5 | **4.25** | /10 | INSUFFISANT | ✅ |
| **11 (CM2)** | **/10** | **12** | **6.00** | **/10** | **PEUT MIEUX FAIRE** | ✅ |
| 11 (CM2) | /10 | 10 | **5.00** | /10 | INSUFFISANT | ✅ |
| 11 (CM2) | /10 | 0 | **0.00** | /10 | TRÈS FAIBLE | ✅ |
| 11 (CM2) | /10 | 5 | **2.50** | /10 | TRÈS INSUFFISANT | ✅ |
| 11 (CM2) | /10 | 19 | **9.50** | /10 | EXCELLENT | ✅ |
| **12 (6ᵉ, Collège)** | **/20** | **12** | **12.00** | **/20** | **PEUT MIEUX FAIRE** | ✅ |
| 13+ (Collège/Lycée) | /20 | 15 | **15.00** | /20 | SATISFAISANT | ✅ |

## 5. Portée dans le bulletin

Suivent le barème du niveau : moyenne de chaque matière, **moyenne pondérée**
(`6.00/10 × coeff 4 = 24.00`), moyenne de partie (FR / EN), moyennes
française / anglaise / **bilingue**, **minimum et maximum de classe**,
**Moyenne Générale**, et l'en-tête de colonne — **« Moy. /10 »** ou
**« Moy. /20 »** — ainsi que le dénominateur explicite de chaque valeur.

## 6. Appréciations et lettres : inchangées

Les appréciations (barème officiel V4, 9 niveaux) et les lettres (A+ … F) sont
**toujours calculées sur l'équivalent /20**, jamais sur la valeur affichée.

> **6,00/10 ≡ 12/20 → « PEUT MIEUX FAIRE », lettre B-.**
>
> Appliquer les seuils 0–20 à la valeur affichée « 6 » donnerait à tort
> « INSUFFISANT » : un test vérifie explicitement que ces deux classements
> **diffèrent**, donc que l'erreur n'est pas commise.

Une même performance reçoit ainsi la même appréciation et la même lettre, quel
que soit le barème d'affichage.

## 7. Preuves

- `tests/test_grade_weighting_and_scale.py` : niveaux 1 → 11 sur 10, 12+ sur 20,
  niveau inconnu → 20, conversions (0, 5, 8.5, 10, 12, 15, 19, 20), libellés
  d'en-tête, cohérence des appréciations.
- **PDF réels générés et inspectés** : primaire → « 6.00/10 » et « Moy. /10» ;
  collège → « 12.00/20 » et « Moy. /20 ». Aucune trace de « 12.00/20 » sur un
  bulletin de CM2, ni de « 6.00/10 » sur un bulletin de Collège.

## 8. Limite connue

La conversion est appliquée au **bulletin PDF** (document officiel). Les écrans
ERP (tableaux de bord, listes de notes, espaces Parent/Élève) continuent
d'afficher l'échelle interne /20 ; les fonctions centrales
(`get_grading_scale`, `convert_average_for_scale`) sont prêtes à y être
branchées — voir `KNOWN_LIMITATIONS.md`.
