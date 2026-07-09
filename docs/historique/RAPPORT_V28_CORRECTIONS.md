# Rapport d'audit et corrections — FEBA V28

**Date** : 2026-05-14  
**Base** : V27  
**Auteur** : Audit complet + refonte profonde

---

## ✅ CHECKLIST DE VALIDATION FINALE

| Point | Statut |
|-------|--------|
| Audit terminé | ✅ |
| Schéma DB validé | ✅ |
| Relations validées | ✅ |
| Données démo recréées | ✅ |
| Classes/matières corrigées | ✅ |
| Inscriptions corrigées | ✅ |
| Multi-années validé | ✅ |
| Promotions validées | ✅ |
| Notes corrigées | ✅ |
| Historique fonctionnel | ✅ |
| Responsive validé | ✅ |
| Bilingue validé | ✅ |
| Aucun bug bloquant | ✅ |
| Tests syntaxiques passés | ✅ |
| Build stable | ✅ |
| ZIP généré | ✅ |

---

## CORRECTIONS DÉTAILLÉES

### PROBLÈME 1 — Classes / Matières (M2M)

**Bug racine :** La table `Class` n'avait aucune relation avec `Subject`.  
Le calcul bilingue utilisait `Subject.level` sans savoir quelles matières appartenaient réellement à chaque classe.

**Corrections :**
- `backend/apps/classes/models.py` — Ajout du champ `subjects = ManyToManyField(Subject)` avec méthodes `get_fr_subjects()`, `get_en_subjects()`, `has_bilingual_subjects()`
- `backend/apps/classes/migrations/0002_class_subjects.py` — Migration correspondante
- `backend/apps/classes/serializers.py` — Exposition de `subjects_detail`, `subject_ids`, `has_bilingual`, `fr_subject_count`, `en_subject_count` ; création/modification gèrent le M2M
- `backend/apps/classes/views.py` — Nouvel endpoint `GET/POST/DELETE /classes/{id}/subjects/`
- `frontend/src/pages/admin/Classes.jsx` — **Refonte complète** : modal de gestion matières avec sélection multiple FR + EN, validation bilingue visuelle, indicateurs dans la liste
- `frontend/src/api/index.js` — Ajout `classesAPI.getSubjects()`, `setSubjects()`, `removeSubject()`

### PROBLÈME 2 — Calcul bilingue / Sélection stricte des matières

**Bug racine :** `Grade.get_subject_averages()` utilisait les matières du niveau (`Subject.level`) sans filtrer par classe. Une classe en `6ème` récupérait toutes les matières de `6ème` — incluant des matières d'autres classes.

**Corrections :**
- `backend/apps/grades/models.py` — `get_subject_averages()` priorise désormais `Class.subjects.all()` (M2M) en premier fallback. Si la classe n'a pas de M2M défini, fallback progressif (level → school → grades directs)
- `calculate_bilingual_averages()` — Ajout de `has_fr_subjects` / `has_en_subjects` dans la réponse ; suppression du faux message d'erreur quand une catégorie est absente
- Frontend `Grades.jsx` — Message d'erreur bilingue amélioré, plus indicatif et jamais trompeur

### PROBLÈME 3 — Données de démonstration

**Bug racine :** Le seed ne créait pas de `StudentEnrollment`, ne gérait qu'une seule année scolaire, et n'assignait aucune matière FR/EN aux classes.

**Corrections :**
- `backend/apps/schools/management/commands/seed_demo_data.py` — **Réécriture complète** :
  - 2 années scolaires (2023-2024 archivée + 2024-2025 courante)
  - Matières FR (6) + EN (5) distinctes
  - Toutes les classes reçoivent leurs matières via M2M
  - 30 élèves avec `StudentEnrollment` sur les 2 années (historique complet)
  - Notes T1+T2+T3 pour l'année courante ; T1+T2 pour l'année précédente
  - Notes bilingues : matières FR et EN séparées

### PROBLÈME 4 — Notes / UI/UX

**Corrections :**

**Résumé élève :**
- Renommé "Résumé élève" → **"Résumé par élève"**
- Filtres Année scolaire, Toutes périodes, Toutes classes **masqués** dans la vue résumé (inutiles)

**Tableau des notes :**
- Tableau principal enveloppé dans `overflow-x-auto` avec `min-w-[700px]` — scroll horizontal intelligent
- Tableau des notes supprimées déjà corrigé (v27)

**Historique global :**
- Vue "Historique" totalement **refaite** avec vraie table de données
- Endpoint backend `GET /api/grades/all-history/` créé
- Filtres : par élève, par année scolaire
- Colonnes : Date, Élève, Matière, Période, Action, Ancienne/Nouvelle valeur, Justification, Auteur

**Modal :**
- Centrage vertical + horizontal corrigé
- `items-start sm:items-center` pour mobile (évite le débordement haut)
- `mx-4 md:mx-0` pour les petits écrans
- `max-h-[92vh]` + `overflow-y-auto` pour les formulaires longs

### PROBLÈME 5 — SearchableSelect (formulaires A/B/C/D)

**Bug racine :** Le dropdown n'avait pas de position dynamique (flip-up) et le `z-index` pouvait être écrasé dans les modals.

**Corrections :**
- `frontend/src/components/ui/SearchableSelect.jsx` — **Refonte** :
  - `z-[9999]` pour visibilité dans les modals
  - Flip automatique vers le haut si pas assez d'espace en dessous
  - `min-h-[42px]` pour la hauteur du trigger
  - `max-h-64` avec `overflow-y-auto` sur la liste
  - Multi-lignes visibles sur tous écrans

---

## Fichiers modifiés

| Fichier | Type de changement |
|---------|-------------------|
| `backend/apps/classes/models.py` | Ajout ManyToManyField subjects |
| `backend/apps/classes/migrations/0002_class_subjects.py` | Nouvelle migration |
| `backend/apps/classes/serializers.py` | Refonte complète |
| `backend/apps/classes/views.py` | Ajout endpoint /subjects/ |
| `backend/apps/grades/models.py` | Fix get_subject_averages + bilingual |
| `backend/apps/grades/views.py` | Ajout all_history_view |
| `backend/apps/grades/urls.py` | Route all-history/ |
| `backend/apps/schools/management/commands/seed_demo_data.py` | Réécriture complète |
| `frontend/src/pages/admin/Classes.jsx` | Refonte complète |
| `frontend/src/pages/admin/Grades.jsx` | Résumé renommé + filtres + historique + responsive |
| `frontend/src/components/ui/Modal.jsx` | Centrage mobile |
| `frontend/src/components/ui/SearchableSelect.jsx` | Flip-up + z-index + hauteur |
| `frontend/src/api/index.js` | classesAPI + gradesAPI.allHistory |

---

## Aucune régression

- Toutes les fonctionnalités V27 préservées
- Aucune migration destructive (AddField + CreateTable uniquement)
- Les élèves existants sans M2M conservent le fallback par niveau
- L'authentification, les bulletins, les paiements, l'assiduité, les messages : inchangés
