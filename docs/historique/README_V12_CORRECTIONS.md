# FEBA V12 — Rapport des corrections

## Résumé des causes racines et corrections

### 🔴 CRITIQUE — Problème 11 : Profil Parent "Mes enfants" → "Erreur lors du chargement"
**Cause racine** : L'endpoint `/api/parents/me/` était **absent** du `ParentViewSet`. La page `Children.jsx` appelait `parentsAPI.me()` → réponse 404 → catch → "Erreur lors du chargement".
**Correction** : Action `me()` ajoutée dans `ParentViewSet` + sérialiseur `ParentSerializer` enrichi avec `children_links` (contenant `student_detail` imbriqué).

### 🔴 CRITIQUE — Problème 11B : Notes/Absences/Paiements vides pour le parent
**Cause racine** : Le filtre ORM `student__parents__user=user` était **faux** — `ParentStudent` n'a pas de champ `user` direct. Le bon chemin est `student__parents__parent__user=user`.
**Correction** : Corrigé dans `grades/views.py`, `attendance/views.py`, `payments/views.py`.

### 🔴 Problème 5A : Upload fichier élève — "La donnée soumise n'est pas un fichier"
**Cause racine** : `studentsAPI.create()` envoyait toujours `Content-Type: application/json` même quand le payload était `FormData`.
**Correction** : `studentsAPI.create` et `update` détectent `FormData` et envoient `multipart/form-data`.

### 🟠 Problème 1 — Responsivité mobile
**Cause racine** : Les layouts initialisaient `useState(true)` (sidebar toujours ouverte) et n'avaient pas d'overlay mobile ni d'animation de fermeture.
**Correction** : Tous les layouts (`AdminLayout`, `TeacherLayout`, `ParentLayout`, `StudentLayout`) réécrit avec : hook `useIsMobile()`, `AnimatePresence` pour la sidebar, overlay cliquable sur mobile, fermeture automatique sur navigation mobile.

### 🟠 Problème 4 — Badge messages non lus
**Cause racine** : `msgUnread` était calculé mais **jamais rendu** dans les `<NavLink>`. La valeur était calculée mais perdue.
**Correction** : Ajout d'un badge inline `<span>` dans chaque `<NavLink>` Messages dans les 4 layouts.

### 🟠 Problème 8 — Notes supprimées sans UI dédiée
**Cause racine** : Aucun bouton "Voir supprimées" ni overlay dans `Grades.jsx`.
**Correction** : Bouton "Voir supprimées" + panel modal avec `backdrop-blur-sm`, liste séparée, bouton "Restaurer".

### 🟠 Problème 9 — Paiements supprimés + détail ne se ferme pas
**Cause racine 1** : Pas de bouton "Voir supprimés" dans `Payments.jsx`.
**Cause racine 2** : `deleteMut.onSuccess` appelait `setDeleteItem(null)` mais pas `setViewItem(null)`.
**Correction** : Bouton + panel supprimés ajouté; `setViewItem(null)` ajouté dans `onSuccess` du `deleteMut`.

### 🟠 Problème 5B — Champs "Parent/Tuteur" + "Photo de profil" dans formulaire élève
**Cause** : Ces champs étaient inclus dans le formulaire (`Students.jsx`).
**Correction** : Champs supprimés du formulaire et du `buildPayload`.

### 🟠 Problème 10 — Type de salle personnalisé
**Cause** : Modèle `Room` avec `choices` fixes, pas de champ libre.
**Correction** : Ajout de `custom_type_label` (CharField) + migration `0003_room_custom_type` + select "Type personnalisé" dans le frontend avec input conditionnel.

### 🟢 Problème 3 — Module Fichiers (nouvelle fonctionnalité)
**Correction** : Création de l'app Django `apps.user_files` complète (model, serializer, ViewSet CRUD avec upload/download/replace) + page `AdminUserFiles.jsx` avec grille de fichiers, prévisualisation, recherche, filtre par utilisateur.

### 🟢 Problème 2/7 — Relations dynamiques + profils
**Correction** : `ParentSerializer.children_links` inclut `NestedStudentSerializer` avec photo, classe, matricule.

## Fichiers modifiés
### Backend
- `apps/parents/serializers.py` — NestedStudentSerializer, children_links enrichis
- `apps/parents/views.py` — Action `/me/` ajoutée
- `apps/grades/views.py` — Filtre ORM parent corrigé
- `apps/attendance/views.py` — Filtre ORM parent corrigé
- `apps/payments/views.py` — Filtre ORM parent corrigé
- `apps/schools/models.py` — custom_type_label sur Room
- `apps/schools/serializers.py` — display_type exposé
- `apps/schools/migrations/0003_room_custom_type.py` — migration
- `apps/user_files/` — Nouveau module complet
- `feba_project/settings/base.py` — user_files dans INSTALLED_APPS
- `feba_project/urls.py` — route /api/user-files/

### Frontend
- `layouts/AdminLayout.jsx` — Responsive + badge messages + nav Fichiers
- `layouts/TeacherLayout.jsx` — Responsive + badge messages
- `layouts/ParentLayout.jsx` — Responsive + badge messages
- `layouts/StudentLayout.jsx` — Responsive + badge messages
- `pages/admin/Grades.jsx` — Panel supprimées + blur
- `pages/admin/Payments.jsx` — Panel supprimés + blur + fix fermeture
- `pages/admin/Students.jsx` — Suppression champs Parent/Photo + fix FormData
- `pages/admin/UserFiles.jsx` — Nouveau module fichiers
- `pages/parent/Grades.jsx` — Filtre par enfant
- `pages/parent/Attendance.jsx` — Filtre par enfant
- `api/index.js` — studentsAPI fix FormData + parentsAPI.me + userFilesAPI
- `router/index.jsx` — Route user-files
