# Rapport d'audit et corrections — Feba V27

**Date** : $(date +%Y-%m-%d)
**Base** : V26 (feba_v25b)

---

## Corrections apportées

### 1. Page de connexion (LoginPage.jsx)
- **Problème** : Sous-titre "École Bilingue Foi & Excellence"
- **Correction** : Remplacé par **"L'école autrement avec vous."**

---

### 2. Formulaire Élèves — Niveau académique (Students.jsx)
- **Problème** : Formulaire création/édition élève sans champ "Niveau", les classes s'affichaient toutes sans filtrage
- **Corrections** :
  - Ajout d'un sélecteur **Niveau académique** qui filtre dynamiquement la liste des classes
  - Chargement de `schoolsAPI.levels()` dans le composant
  - Filtre côté client : sélectionner un niveau n'affiche que les classes de ce niveau
  - Réinitialisation auto de la classe si le niveau change
  - Pré-remplissage du niveau lors de l'édition (dérivé de la classe courante)

---

### 3. Export Excel — Élèves (Students.jsx)
- **Ajout** : Bouton **"Export Excel"** exportant tous les élèves visibles avec :
  - Matricule, Prénom, Nom, Genre, Date de naissance
  - Niveau, Classe, Année scolaire
  - Adresse, Statut, Date d'inscription
- Format CSV UTF-8 (compatible Excel sans plugin)

---

### 4. Export Excel — Paiements (Payments.jsx)
- **Ajout** : Bouton **"Export Excel"** avec toutes les colonnes :
  - Référence, Élève, Matricule, Classe, Type, Montant, Mode, Date
  - Reçu par, Statut, Année scolaire, Notes

---

### 5. Bug DataTable — props mal positionnées (Students.jsx, Payments.jsx)
- **Problème** : `selectable`, `onBulkDelete`, `bulkDeletePending` étaient des props sur l'icône `<Eye />` / `<Receipt />` au lieu du composant `<DataTable>`
- **Correction** : Props remontées au niveau `<DataTable>` — la suppression en masse est maintenant fonctionnelle

---

### 6. Notes — Fermeture automatique après modification (Grades.jsx)
- **Problème** : Après modification d'une note, le modal restait ouvert (`setAddOpen(false)` manquant dans `editMut.onSuccess`)
- **Correction** : `setAddOpen(false)` ajouté dans le callback `onSuccess` de `editMut`

---

### 7. Notes supprimées — Export CSV (Grades.jsx)
- **Ajout** : Bouton **"Exporter"** dans l'onglet "Notes supprimées" avec colonnes complètes :
  - Élève, Matricule, Classe, Matière, Catégorie, Note, Coefficient, Lettre
  - Période, Commentaire, Justification, Supprimé par, Date, Année scolaire
- **Correction** : `qc.invalidateQueries(["grades-deleted"])` ajouté aux mutations add/edit/bulk-delete pour refresh automatique

---

### 8. Inscriptions — "0 élève inscrit" corrigé (backend + frontend)
- **Cause racine** : `enroll_all_from_year` ne cherchait que dans `StudentEnrollment`, or les élèves créés via le formulaire admin ont `Student.school_year` défini sans enregistrement `StudentEnrollment`
- **Corrections backend** :
  - Union des deux sources : `StudentEnrollment` (is_active) + `Student.school_year`
  - Renommage `skipped_already_enrolled` → `skipped` pour cohérence avec les autres endpoints
- **Correction frontend** :
  - Toast amélioré : affiche `X inscrit(s), Y déjà inscrit(s)` selon les deux cas

---

### 9. Serializer Élève — champ `class_level` (students/serializers.py)
- **Ajout** : Champ calculé `class_level` retournant `student.current_class.level.name`
- Utilisé dans la fiche détail élève (affichage Niveau) et l'export Excel

---

## Fichiers modifiés

| Fichier | Changements |
|---------|-------------|
| `frontend/src/pages/LoginPage.jsx` | Sous-titre login |
| `frontend/src/pages/admin/Students.jsx` | Niveau + export + DataTable fix |
| `frontend/src/pages/admin/Payments.jsx` | Export + DataTable fix |
| `frontend/src/pages/admin/Grades.jsx` | Auto-close + export supprimées + cache |
| `frontend/src/pages/admin/Enrollments.jsx` | Toast inscription |
| `backend/apps/students/serializers.py` | Champ class_level |
| `backend/apps/students/views.py` | enroll_all_from_year dual-source fix |

---

## Zéro régression
- Toutes les fonctionnalités V26 préservées
- Aucune migration DB requise (changements serializer uniquement)
- Aucune suppression de données
