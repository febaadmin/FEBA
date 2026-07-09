# FEBA v44 — Rapport : filtres bilingues redondants, classes en triple, matières en double

Date : 09/07/2026 · Base : v43 · Le zip renvoyé est identique à l'état v43 livré.

---

## Confirmation : le bilingue fonctionne

Vos captures 3, 4, 6, 16, 17 montrent le calcul bilingue opérationnel (FR/EN/BI réels par trimestre, ex. 13.83 / 10.27 / 11.69) — le correctif de route v43 (bilingual/ n'est plus masqué par le routeur) est confirmé en conditions réelles. Les espaces parent (12) et élève (13, 14) affichent aussi des moyennes cohérentes.

## Corrections v44 (annotées sur vos captures)

### 1. Filtres « Inutile » dans la vue Bilingue (capture 16)
Vous avez annoté « Inutile » les filtres **Toutes périodes** et **Toutes classes** de l'onglet Bilingue. C'était juste : ces deux filtres ne servent que la vue **Liste**. Dans la vue Bilingue (comme dans « Résumé par élève »), le calcul dépend de l'**élève** et du **trimestre** déjà sélectionnés à droite — les deux filtres génériques n'avaient aucun effet et prêtaient à confusion. Ils sont désormais **masqués** dans les vues Bilingue et Résumé ; seuls restent Année scolaire, Élève et Trimestre (+ Reset). La vue Liste conserve tous ses filtres.

### 2. Classes en triple « 3ème-A — 3ème » (captures 2, 5, 7)
Dans la fenêtre de **réinscription d'un élève** (page Élèves), le menu « Nouvelle classe » listait chaque classe **une fois par année** (3ème-A ×3…), car il affichait toutes les années sans distinction. Correction : la liste est maintenant **filtrée par l'année cible** choisie juste au-dessus — on ne voit que les classes de cette année. Sans année sélectionnée, chaque classe est étiquetée par son année. (La page Inscriptions/Passages utilisait déjà des libellés désambiguïsés — capture 10.)

### 3. Matières en double « test / test » (capture 9)
Le sélecteur de matière du formulaire « Ajouter une note » montrait « test » deux fois : des matières de même nom avaient été créées en double lors de vos essais. Pour empêcher que cela se reproduise, la création d'une matière est désormais **refusée si une matière de même nom et même langue existe déjà** dans l'établissement (message explicite). Les doublons déjà présents ne sont pas supprimés automatiquement (ce sont vos données) : vous pouvez les retirer depuis Paramètres → Matières.

## Vérifications

Backend compilé ; graphe de migrations intègre (aucune migration) ; 79 fichiers frontend, 0 erreur ; imports/appels API valides. **2 nouveaux tests** (`test_subject_dedup.py`) : doublon de matière refusé ; même nom en langue différente autorisé. Check-list du guide portée à **56 scénarios**.

## Fichiers modifiés
| Fichier | Nature |
|---|---|
| `frontend/src/pages/admin/Grades.jsx` | Filtres période/classe masqués hors vue Liste |
| `frontend/src/pages/admin/Students.jsx` | Classe de réinscription filtrée par l'année cible |
| `backend/apps/subjects/serializers.py` | Refus des matières en double (nom + langue) |
| `backend/tests/test_subject_dedup.py` | 2 tests de régression |
| Guides PDF | Check-list 56 scénarios |

## Note de mise à jour
Correctifs sans migration. Après extraction : `docker compose up --build -d` puis `Cmd+Shift+R`. Pour nettoyer d'éventuelles matières « test » en double déjà créées, utilisez Paramètres → Matières (icône corbeille).
