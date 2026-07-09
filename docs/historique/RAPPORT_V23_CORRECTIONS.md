# RAPPORT DES CORRECTIONS — FEBA v23

Date : 2026-05-12
Version précédente : v22
Version livrée : v23

---

## 1. SUPPRESSION EN MASSE — IMPLÉMENTÉE PARTOUT

### Backend : BulkDeleteMixin (nouveau fichier)
`backend/feba_project/bulk_delete.py`

- Nouveau mixin réutilisable ajouté à TOUS les ViewSets concernés
- POST `/endpoint/bulk-delete/` → body `{ "ids": [1,2,3] }`
- Soft-delete si le modèle a `is_deleted` (notes, paiements)
- Hard-delete sinon
- Wrappé dans `transaction.atomic()`
- Logs auteur/model/ids/count
- Retourne `{ "deleted": N }`

**ViewSets patchés :**
students, parents, teachers, grades, payments, bulletins, attendance, homework, announcements

### Frontend : DataTable upgradé
`frontend/src/components/ui/DataTable.jsx`

- Nouvelles props : `selectable`, `onBulkDelete`, `bulkDeleteLabel`, `bulkDeletePending`
- Checkbox "tout sélectionner" en en-tête (état indéterminé si sélection partielle)
- Checkbox par ligne, fond bleu sur les lignes sélectionnées
- Bouton "Supprimer la sélection (N)" avec confirmation `window.confirm()` sécurisée
- Compteur affiché dans la barre de pagination
- `useEffect` remet la sélection à zéro après chaque rechargement de données
- Rétrocompatible : comportement identique si `selectable` non passé

**Pages wired :**
Students, Teachers, Parents, Payments, Homework, Announcements, Bulletins

### Notes : tableau custom avec checkboxes
`frontend/src/pages/admin/Grades.jsx`

- Checkbox "tout sélectionner" en en-tête du tableau custom
- Checkbox par ligne
- Barre de suppression en masse flottante avec confirmation
- Mutation `bulkDelMut` → `gradesAPI.bulkDelete(ids)`

---

## 2. MATIÈRES : CHAMP LANGUE (FR/EN/BILINGUE) — AJOUTÉ AUX FORMULAIRES

### Problème
Le modèle `Subject` avait `language = CharField(choices=['fr','en','bilingual'])` mais les formulaires create/edit dans Settings n'avaient PAS ce champ → impossible de categoriser les matières.

### Fichier modifié
`frontend/src/pages/admin/Settings.jsx`

### Corrections
- **Formulaire création** : ajout du champ `<select>` "Catégorie de matière" avec options FR/EN/Bilingue
- **Formulaire édition** : idem + préremplissage automatique avec `language: s.language || "fr"`
- **Liste matières** : affichage du badge langue (🇫🇷 / 🇬🇧 / 🌐) sur chaque matière
- Texte d'aide : "Détermine dans quelle moyenne la matière est comptabilisée"

---

## 3. NOTES DÉTAIL : RESPONSIVE MOBILE — BOTTOM SHEET

### Problème
Le panneau détail était un sidebar `lg:col-span-2` → invisible sur mobile (seulement visible ≥ lg).

### Fichier modifié
`frontend/src/pages/admin/Grades.jsx`

### Correction
- Sur **mobile** : panneau = bottom sheet fixe (`fixed bottom-0 left-0 right-0 z-50`) avec backdrop semi-transparent, drag handle visuel, scroll interne limité à 70vh
- Sur **desktop** : panneau = sidebar sticky classique (`lg:sticky lg:top-4`)
- Scroll sécurisé sur le contenu (`max-h-[70vh] overflow-y-auto`)
- Bouton fermeture agrandi (w-5 h-5)
- Boutons d'action avec padding vertical augmenté (py-2.5)

---

## 4. ÉLÈVES MULTI-ANNÉES : UI DE RÉENROLLMENT — IMPLÉMENTÉE

### Problème
Le backend avait `StudentEnrollment` (multi-année) mais aucune UI pour réenroller un élève dans une nouvelle année sans écraser son profil.

### Fichier modifié
`frontend/src/pages/admin/Students.jsx`

### Fichier modifié
`frontend/src/api/index.js`

### Corrections
- **Bouton "Nouvelle année"** dans la fiche détail de chaque élève
- **Modal de réenrollment** : sélection année scolaire + classe + note/observation
- Utilise POST `/students/enrollments/` → `StudentEnrollmentViewSet`
- Message d'info : "sera inscrit(e)... sans perdre son historique"
- Gestion erreur `unique_together` (déjà inscrit pour cette année)
- Nouvelles méthodes API : `enrollments()`, `addEnrollment()`, `updateEnrollment()`, `deleteEnrollment()`

---

## 5. BULLETINS : VÉRIFICATION CALCULS FR/EN/BILINGUE — VALIDÉS

Calculs existants vérifiés et confirmés corrects :

- **Moyenne FR** = moyenne pondérée (par coefficient) de toutes les matières `language='fr'`
- **Moyenne EN** = moyenne pondérée de toutes les matières `language='en'`
- **Moyenne Bilingue** = `(FR × 40%) + (EN × 60%)`
- Si une seule catégorie présente : utilise la catégorie disponible
- Si aucune : None

Le champ `language` est propagé depuis `Subject.language` dans `get_subject_averages()` → utilisé dans `calculate_bilingual_averages()` → affiché dans le PDF.

**Le correctif du point 2 (formulaire matière) est la clé** : sans ce champ, toutes les matières étaient `fr` par défaut → pas de moyenne EN → moyenne bilingue = moyenne FR.

---

## RÉSUMÉ DES FICHIERS MODIFIÉS

| Fichier | Modification |
|---------|-------------|
| `backend/feba_project/bulk_delete.py` | ✅ NOUVEAU — BulkDeleteMixin |
| `backend/apps/*/views.py` (×9) | ✅ Injection BulkDeleteMixin + import |
| `frontend/src/components/ui/DataTable.jsx` | ✅ Bulk-select complet (checkboxes + toolbar) |
| `frontend/src/api/index.js` | ✅ bulkDelete() sur tous les modules + enrollments |
| `frontend/src/pages/admin/Grades.jsx` | ✅ Checkboxes custom + bottom sheet mobile |
| `frontend/src/pages/admin/Settings.jsx` | ✅ Champ language FR/EN/Bilingue dans formulaires |
| `frontend/src/pages/admin/Students.jsx` | ✅ Modal réenrollment multi-années |
| `frontend/src/pages/admin/Teachers.jsx` | ✅ bulkDelete wired |
| `frontend/src/pages/admin/Parents.jsx` | ✅ bulkDelete wired |
| `frontend/src/pages/admin/Payments.jsx` | ✅ bulkDelete wired |
| `frontend/src/pages/admin/Homework.jsx` | ✅ bulkDelete wired |
| `frontend/src/pages/admin/Announcements.jsx` | ✅ bulkDelete wired |
| `frontend/src/pages/admin/Bulletins.jsx` | ✅ bulkDelete wired |

---

## AUCUNE MIGRATION DB REQUISE

Tous les champs utilisés (`is_deleted`, `language`, `StudentEnrollment`) existent déjà dans les modèles et migrations précédents.

---

## TESTS DE VALIDATION

### Test suppression en masse
1. Aller sur /admin/students
2. Cocher 3 élèves → bouton "Supprimer la sélection (3)" apparaît
3. Cliquer → confirmation → ✅ 3 supprimés, toast "3 élément(s) supprimé(s)"
4. Vérifier en DB : soft-delete si `is_deleted`, hard-delete sinon

### Test matière avec langue
1. Aller sur /admin/settings → section Matières
2. Créer une matière → ✅ champ "Catégorie" visible (FR/EN/Bilingue)
3. Vérifier l'affichage de la badge dans la liste
4. Générer un bulletin → ✅ moyennes FR/EN/Bilingue distinctes

### Test notes mobile
1. Ouvrir /admin/grades sur mobile (viewport < 768px)
2. Cliquer sur une ligne → ✅ bottom sheet remonte du bas
3. Bouton "Modifier" → ✅ modal préremplit
4. Swipe ou clic backdrop → ✅ fermeture

### Test élève multi-années
1. Ouvrir fiche d'un élève existant
2. Cliquer "Nouvelle année" → ✅ modal s'ouvre
3. Sélectionner année 2025-2026 + classe → Inscrire
4. ✅ Élève apparaît dans la nouvelle année, historique préservé
5. Tenter de réinscrire la même année → ✅ erreur "déjà inscrit"
