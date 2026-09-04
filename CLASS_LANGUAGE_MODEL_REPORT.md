# FEBA — Parcours linguistique d'une classe (V10)

---

## 1. Le problème

« Au moins une matière française **et** une matière anglaise sont
obligatoires » décrit FEBA, qui est bilingue. FEBA FHA accueille des
classes **monolingues**.

Appliquée à une classe francophone, cette règle lui reprochait sans fin
l'absence d'une langue qu'elle n'enseigne pas — et le reproche ne pouvait
**jamais** être levé, quoi que fasse l'administrateur.

C'était une règle d'une académie promue en règle universelle.

---

## 2. Le modèle

`Class.language_track`, avec trois valeurs :

| Valeur | Libellé | Langues attendues |
|---|---|---|
| `BILINGUAL` | Bilingue (français et anglais) | `fr`, `en` |
| `FRANCOPHONE` | Francophone | `fr` |
| `ANGLOPHONE` | Anglophone | `en` |

**La valeur par défaut est `BILINGUAL`.** C'est le point qui garantit
§37 : toutes les classes FEBA existantes conservent exactement leur
comportement, sans migration de données ni intervention.

Trois méthodes portent la logique, à un seul endroit :

```python
def expected_subject_languages(self)        # ce que le parcours attend
def missing_subject_languages(self)         # ce qui manque parmi l'attendu
def is_language_configuration_complete(self)
```

`missing_subject_languages()` remplace la règle universelle : elle ne
regarde que **les langues attendues**. Une classe anglophone sans matière
française n'a rien qui manque.

Migration : `apps/classes/migrations/0003_class_language_track.py`.

---

## 3. L'interface

Écran **Classes** — un sélecteur « Parcours linguistique », à côté de
« Capacité max », avec la phrase qui dit à quoi il sert : « Détermine les
matières attendues et la forme du bulletin. »

Modale **Matières** — le message s'adapte au parcours déclaré :

| Parcours | Message |
|---|---|
| Bilingue | « une matière française et une matière anglaise sont attendues » |
| Francophone | « seules les matières françaises sont attendues » |
| Anglophone | « seules les matières anglaises sont attendues » |

La validation ne signale que les langues **attendues** et manquantes.

### Détail de traduction

Les messages avaient d'abord été découpés en plusieurs `t()` :
`« Aucune matière »` + `« française »` + `« sélectionnée. »`. Cela produit
un anglais bancal — l'ordre des mots n'est pas le même. Chaque message
est désormais une phrase entière, et les comptes passent par une
interpolation (`« {n} matière(s) {lang} »` → `« {n} {lang} subject(s) »`).

---

## 4. Le bulletin

Le bulletin standard imprimait **toujours** les deux parties. Pour une
classe francophone, chaque trimestre sortait donc avec :

```
ACADEMIC RESULTS — ENGLISH SECTION / PARTIE ANGLAISE
Aucune matière dans cette catégorie / No subject in this category.

Moyenne Anglaise / English Average     —     —     —     —
Moyenne Bilingue / Bilingual Average   …
Formule bilingue : (Moyenne Française × 60%) + (Moyenne Anglaise × 40%)
```

Un document officiel remis aux parents annonçait un manque là où il n'y
avait rien à manquer, et affichait une moyenne pondérée par une langue que
la classe n'enseigne pas.

Les sections suivent désormais le parcours déclaré.

### Deux limites tenues par des tests

« Adapter » ne veut pas dire « masquer ».

1. **Une classe bilingue à qui il manque une langue montre toujours la
   section vide.** C'est une anomalie de configuration ; la taire la
   rendrait invisible.
   → `test_classe_bilingue_incomplete_montre_toujours_le_manque`

2. **Des notes présentes dans une langue non attendue restent
   imprimées.** Une étiquette de classe ne fait pas disparaître un
   résultat réel.
   → `test_des_notes_dans_une_langue_non_attendue_restent_imprimees`

### Détail technique

Les couleurs de fond du tableau des moyennes étaient posées sur des index
écrits en dur (lignes 1, 2, 3). Elles suivent maintenant les lignes
réellement produites — sinon une classe monolingue héritait du fond de la
ligne bilingue.

Le modèle **maternelle** n'imprimait déjà que les sections non vides :
aucun changement n'y était nécessaire.

Le repli est explicite : classe inconnue ou modèle plus ancien →
`("fr", "en")`. Un bulletin ne perd jamais une section par accident.

---

## 5. Vérifications

| Test | Objet | Statut |
|---|---|---|
| `test_feba_bilingue_inchange` | §37 — la sortie FEBA est identique | **PASS VÉRIFIÉ** |
| `test_classe_francophone_sans_partie_anglaise` | plus de section vide | **PASS VÉRIFIÉ** |
| `test_classe_anglophone_sans_partie_francaise` | symétrique | **PASS VÉRIFIÉ** |
| `test_classe_bilingue_incomplete_montre_toujours_le_manque` | l'anomalie reste visible | **PASS VÉRIFIÉ** |
| `test_des_notes_dans_une_langue_non_attendue_restent_imprimees` | aucun résultat perdu | **PASS VÉRIFIÉ** |
| `test_sans_classe_le_bulletin_reste_bilingue` | repli sûr | **PASS VÉRIFIÉ** |
| `ParcoursLinguistiqueTests` | API et validation | **PASS VÉRIFIÉ** |
| Parcours navigateur E2 | le sélecteur est bien à l'écran | **PASS VÉRIFIÉ** |

En neutralisant l'adaptation, 2 tests échouent : la vérification porte
bien sur le comportement.

---

## 6. Données de démonstration

`seed_demo_data` illustre les trois parcours sur FEBA FHA :

| Classe | Parcours |
|---|---|
| Junior Roots | Francophone |
| French Explorers | Bilingue |
| French Ambassadors | Anglophone |

Cinq matières FHA sont créées et assignées selon le parcours de chaque
classe. Vérifié sur l'API : `missing_languages = []` pour les trois.
