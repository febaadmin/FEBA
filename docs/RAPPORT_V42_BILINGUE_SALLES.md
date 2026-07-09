# FEBA v42 — Rapport : calcul bilingue robuste & clarification des salles

Date : 08/07/2026 · Base : v41 · Diagnostic depuis vos 7 captures.

---

## Lecture des captures — ce qui est correct, ce qui restait à corriger

**Comportements corrects confirmés (aucune action requise) :**
- **Tableau de bord admin** (Image 7) : 30 élèves, 5 enseignants, 8 classes, bandeau « Année active 2025-2026 » — cohérent. Revenus à 0 FCFA sur les graphes : normal, les paiements de démo sont datés hors de l'année courante.
- **Espace parent** (Image 6) : moyennes « — » pour Koffi et Sègun — correct, ils n'ont pas de notes dans l'année active (mêmes données que l'espace élève de la v41).
- **Années scolaires** (Images 1, 3, 4) : une seule « En cours » (2025-2026), les autres avec « Activer » — l'invariant « une seule année active » (v39) tient.

**Deux points corrigés :**

### 1. Bilingue « Calcul indisponible » (Images 2, 5)
**Symptôme** : pour Estelle Acakpo — CM1-A (année 2024-2025), l'onglet Bilingue affiche un encart d'ERREUR orange « Calcul bilingue indisponible ».
**Analyse** : ce message ne s'affichait que sur une **erreur HTTP** (500). Or, quand la classe de l'élève pour l'année sélectionnée n'a pas de matières FR **et** EN assignées, il ne s'agit pas d'une erreur mais d'un **cas de données normal**. Deux corrections :
- **Backend** : le calcul bilingue est désormais entouré d'un **filet de sécurité** — toute erreur imprévue est journalisée et renvoie une charge utile neutre (`has_fr_subjects/has_en_subjects: false`) au lieu d'un 500. L'endpoint ne casse plus jamais.
- **Frontend** : nouvel état **informatif** (neutre, pas alarmant) « Pas de calcul bilingue pour cette sélection — cet élève n'a pas de classe avec des matières FR et EN assignées pour l'année sélectionnée », affiché quand les deux catégories de matières sont absentes. L'encart d'erreur rouge est réservé aux vraies erreurs.
Ainsi, pour un élève d'une classe sans matières bilingues, l'utilisateur voit une explication claire et actionnable, plus un message d'erreur trompeur.

### 2. Classes affichées comme « salles » (Images 1, 4)
**Symptôme** : dans Paramètres → Salles, des entrées « 4ème-A, 5ème-A, CP1-A… » apparaissent en « Salle de classe », sans icônes d'édition, mêlées aux vraies salles (Salle 101-104, informatique).
**Analyse** : c'est **volontaire** — chaque classe de l'année active est exposée comme lieu utilisable dans l'emploi du temps. Mais le mélange, sans explication, laissait croire que ces classes étaient de vraies salles à gérer ici.
**Correction** : la page distingue désormais nettement :
- **« Salles physiques de l'École »** : uniquement les vraies salles, éditables/supprimables, avec un état vide explicite si aucune n'existe.
- **« Salles de classe (automatiques) »** : listées séparément sous forme de puces, avec une note « dérivées des classes de l'année active, disponibles comme lieu dans l'emploi du temps ; se gèrent depuis la page Classes, pas ici ».
Plus aucune confusion entre salles réelles et salles dérivées des classes.

## Vérifications

Backend compilé ; 78 fichiers frontend, 0 erreur ; imports/appels API valides ; aucune migration (corrections de logique/présentation). **2 nouveaux tests** (`BilingualSafetyTests`) : bilingue sans matières → 200 avec `has_*: false` ; bilingue annuel sans données → 200 sans crash. S'ajoutent aux tests v41 (moyennes, notifications). Check-list du guide portée à **51 scénarios**. Au passage, un `onError` dupliqué dans Settings a été nettoyé.

## Fichiers modifiés
| Fichier | Nature |
|---|---|
| `backend/apps/grades/views.py` | Filet de sécurité sur le calcul bilingue (jamais de 500) |
| `frontend/src/pages/admin/Grades.jsx` | État informatif « pas de calcul bilingue » distinct de l'erreur |
| `frontend/src/pages/admin/Settings.jsx` | Salles physiques vs salles de classe automatiques, clairement séparées ; nettoyage `onError` dupliqué |
| `backend/tests/test_averages_and_notifications.py` | +2 tests (bilingue robuste) |
| Guides PDF | Check-list 51 scénarios |

## Note de mise à jour
Correctifs backend + frontend, sans migration. Après extraction :
```
docker compose up --build -d
# rechargez l'onglet (Cmd+Shift+R)
```
Le bilingue affichera alors un message clair (jamais d'erreur) et la page Salles distinguera salles physiques et salles de classe automatiques.
