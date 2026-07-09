# FEBA v34 — Rapport : isolation multi-années & sémantique de suppression

Date : 06/07/2026 · Base : v33 · Mission : « refonte de la gestion des années scolaires ».

---

## 1. Diagnostic d'architecture — ce qui était sain, ce qui ne l'était pas

**Socle conforme (audité, conservé).** Le modèle métier exigé — Élève (identité unique) → Inscription annuelle (`StudentEnrollment`, unique par élève+année) → Année scolaire → Classe — est en place depuis les versions précédentes : notes, bulletins, absences/retards, paiements et décisions de passage portent une FK `enrollment` (en plus de `student` et `school_year`, ce qui garantit qu'aucune donnée n'est perdue si une inscription est retirée : `on_delete=SET_NULL`). Les classes appartiennent chacune à UNE année. Reconstruire ce socle aurait détruit des données sans bénéfice ; la mission a donc porté sur ce qui était réellement défectueux : **la couche d'exposition** (valeurs par défaut des API, formulaires, suppressions), où l'isolation par année n'était pas appliquée.

**Défauts identifiés (causes racines) :**
1. **L'API des classes renvoyait toutes les années par défaut.** Chaque formulaire consommant `GET /classes/` (Nouvel élève — votre 1re capture ; Salles virtuelles — votre 2e capture ; Emploi du temps ; Devoirs ; Bulletins ; Enseignants ; Notes) affichait donc les triplets « CP1-A / CP1-A / CP1-A » issus des 3 années, sans étiquette. Ce n'était pas 12 bugs de formulaires : c'était UNE valeur par défaut d'API incorrecte.
2. **Le formulaire « Nouvel élève » ne cascadait pas année → classes** : le champ Classe (filtré seulement par niveau) précédait même le champ Année.
3. **La suppression d'un élève était un DELETE physique** (CASCADE) : supprimer depuis une année effaçait l'élève ET tout son historique de toutes les années — le comportement explicitement interdit par la mission. Idem pour la suppression en masse et pour les parents (liens familiaux détruits).
4. Aucune distinction entre « retirer de l'année », « désactiver » et « supprimer définitivement ».

## 2. Corrections — isolation par année

- **API classes (correction systémique)** : par défaut, `GET /classes/` ne renvoie que les classes de **l'année active** (l'année = espace de travail indépendant). Dérogations explicites : `?school_year=<id>` (année précise) et `?all_years=1` (écrans multi-années : passages, formulaire élève). Cette seule modification assainit d'un coup les sélecteurs de classes de 8 pages (Salles virtuelles, Emploi du temps, Devoirs, Bulletins, Enseignants, Paramètres, pages enseignant) — plus aucun doublon inter-années nulle part.
- **Formulaire « Nouvel élève »** : workflow exigé implémenté — 1) sélection de l'année scolaire (champ déplacé EN PREMIER, avec aide « détermine les classes proposées ») ; 2) chargement dynamique des classes de CETTE année uniquement (cascade, en plus du filtre par niveau) ; 3) sélection de la classe. Changer d'année invalide automatiquement une classe devenue hors périmètre. Sans année choisie, chaque classe est étiquetée par son année.
- **Page Notes** : la liste des classes suit l'année sélectionnée dans les filtres (année active par défaut).
- **Page Classes** : puces d'années (« Année active » par défaut) — chaque année gère SES classes, et on peut préparer celles d'une année future.
- Rappel des acquis v31–v33 (déjà livrés, faisant partie de la même exigence) : listes Élèves et Parents filtrées par année via l'HISTORIQUE des inscriptions (année active par défaut), colonne Classe affichant la classe de l'année consultée, promotions par classe via l'historique, résumé/bilingue résolus par année.

## 3. Corrections — sémantique de suppression (élèves & parents)

Trois niveaux distincts, exactement comme exigé :

| Action | Endpoint | Effet |
|---|---|---|
| **Retirer de l'année** | `POST /students/{id}/remove-from-year/` | Supprime UNIQUEMENT l'inscription de l'année indiquée. Les notes/paiements de l'année restent liés à l'élève et à l'année (FK `enrollment` → SET_NULL). Les autres années sont strictement intactes. Si le pointeur « année courante » visait l'année retirée, il est repositionné sur l'inscription restante la plus récente. |
| **Désactiver** (défaut) | `DELETE /students/{id}/` | Soft delete : `is_active=False` (élève + compte). Disparaît des listes actives (masquage par défaut, `?include_inactive=1` pour le retrouver), historique multi-années inviolé, **réactivation** possible (`POST .../reactivate/`). La suppression en masse est également soft. |
| **Suppression définitive** | `DELETE /students/{id}/?hard=true` | Refusée (HTTP 409) tant que des dépendances existent — la réponse liste les comptes (inscriptions, notes, paiements, absences, bulletins). N'aboutit que sur un dossier vide, après confirmation explicite. |

Parents : `DELETE /parents/{id}/` = désactivation du compte (liens familiaux et historique conservés, `reactivate/` disponible) ; `?hard=true` refusé (409) tant que des liens élèves existent. La suppression d'une inscription via l'endpoint enrollments applique le même repositionnement de pointeur.

**UI (page Élèves)** : le bouton Supprimer ouvre désormais un dialogue à trois options — « Retirer de l'année X » (proposé uniquement quand une année précise est sélectionnée, ambre), « Désactiver l'élève (toutes années) » (neutre), « Suppression définitive » (rouge, double confirmation, refus automatique si dépendances). Les toasts reflètent le message serveur. Le message de confirmation Parents explique la désactivation et la conservation des liens.

## 4. Vérifications (boucle analyser → corriger → vérifier)

Compilation backend complète ; 77 fichiers frontend, 0 erreur de syntaxe ; imports et appels API tous valides ; graphe de migrations intègre (aucune migration nécessaire : corrections de logique d'exposition, le schéma multi-années étant déjà correct). **9 nouveaux tests** (`test_year_isolation_deletion.py`) : soft delete par défaut + masquage + include_inactive ; hard delete bloqué avec dépendances listées ; remove-from-year conservant les autres années et repositionnant le pointeur ; bulk delete soft ; API classes limitée à l'année active par défaut + dérogations `school_year`/`all_years` ; parent soft + hard bloqué si liens. Check-list du guide d'installation portée à **30 scénarios**, dont 7 dédiés à l'isolation et aux suppressions, à rejouer avec plusieurs années contenant des données différentes (le seeder en fournit 3).

## 5. Fichiers modifiés

| Fichier | Nature |
|---|---|
| `backend/apps/classes/views.py` | Isolation : classes de l'année active par défaut (+ dérogations) |
| `backend/apps/students/views.py` | destroy soft / hard gardé, remove-from-year, reactivate, bulk soft, masquage des inactifs, repositionnement du pointeur sur suppression d'inscription |
| `backend/apps/parents/views.py` | destroy soft / hard gardé si liens, reactivate |
| `frontend/src/pages/admin/Students.jsx` | Cascade année→classes, champ année en premier, dialogue de suppression à 3 niveaux |
| `frontend/src/pages/admin/Grades.jsx` | Classes suivant l'année filtrée |
| `frontend/src/pages/admin/Classes.jsx` | Puces d'années (année active par défaut) |
| `frontend/src/pages/admin/Parents.jsx` | Message et toast de désactivation |
| `frontend/src/api/index.js` | removeFromYear / hardDelete / reactivate |
| `backend/tests/test_year_isolation_deletion.py` | 9 tests de régression |
| Guides PDF | Check-list portée à 30 scénarios |

## 6. Changelog v34
- **feat(isolation)** : l'API classes ne renvoie par défaut que l'année active — fin des doublons inter-années dans TOUS les sélecteurs (élève, salles virtuelles, emploi du temps, devoirs, bulletins, enseignants…).
- **feat(form)** : formulaire élève en cascade année → classes de l'année → classe, année en premier.
- **feat(deletion)** : trois niveaux de suppression élève (retrait d'année / désactivation réversible / définitive gardée par dépendances) + parents en désactivation ; suppressions en masse soft ; pointeur d'année repositionné automatiquement.
- **feat(ui)** : dialogue de suppression à 3 options ; puces d'années sur la page Classes.
- **tests** : 9 tests d'isolation et de suppression.
