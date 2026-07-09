# RAPPORT DES CORRECTIONS — FEBA v22

Date : 2026-05-11  
Version précédente : v21 (feba_v21_corrected.zip)  
Version livrée : v22

---

## 🔴 CORRECTIF CRITIQUE — PROBLÈME FICHIER & BRANDING (déconnexion admin)

### Symptôme
Clic sur **"Fichiers"** ou **"Branding & Logo"** dans le menu admin → déconnexion automatique.

### Cause racine
Les routes `/admin/user-files` et `/admin/branding` étaient **absentes** du bloc `/admin` du routeur React (`src/router/index.jsx`). Elles n'existaient que dans le bloc `/superadmin`.

Quand l'admin naviguait vers ces URLs, React Router ne trouvait aucune route correspondante → tombait sur le catch-all `path="*"` → redirigeait vers `/login` → apparaissait comme une déconnexion.

### Fichier modifié
`frontend/src/router/index.jsx`

### Correction
```jsx
// Ajout des routes manquantes dans le bloc /admin :
<Route path="user-files"    element={<AdminUserFiles />} />
<Route path="branding"      element={<AdminBranding />} />
```

---

## 🔴 CORRECTIF CRITIQUE — NOTIFICATIONS 401 → DÉCONNEXION INVOLONTAIRE

### Symptôme
Appel à `/api/notifications/unread-count/` retournant 401 (token pas encore hydraté) → déclenchait le mécanisme de déconnexion de l'intercepteur Axios.

### Cause racine
`/notifications/unread-count/` n'était pas dans la liste `NON_CRITICAL_ENDPOINTS` du fichier `api/index.js`.

### Fichier modifié
`frontend/src/api/index.js`

### Correction
```js
const NON_CRITICAL_ENDPOINTS = [
  "/schools/branding/",
  "/notifications/",
  "/notifications/unread-count/",  // ← ajouté
  "/messages/unread-count",
  "/messages/inbox",
];
```

---

## 🟠 CORRECTIF IMPORTANT — NOTES : UX ROW-CLICK + ÉDITION (sélection par ligne)

### Symptôme
- Impossible de sélectionner un élève directement dans la liste de notes
- Formulaire d'édition vide (student, subject, period non préremplis)
- Pas de pattern "clic sur ligne → panneau détail + bouton modifier"

### Cause racine
1. La liste utilisait `DataTable` générique sans `onClick` par ligne
2. Le `reset()` lors de l'édition ne passait que `value, note_type, note_coefficient, comment` — pas `student, subject, period, school_year`

### Fichiers modifiés
`frontend/src/pages/admin/Grades.jsx`

### Corrections
1. **Row-click pattern** : Remplacement de `DataTable` par un `<table>` custom avec `onClick` par ligne → panneau détail collant sur la droite (comme le module paiement), avec boutons "Modifier", "Historique", "Supprimer"
2. **Préremplissage complet** : `reset()` inclut maintenant `student, subject, period, school_year` en plus des autres champs
3. **Mode édition sans resélection** : En mode édition, les champs élève/matière/période sont remplacés par un bandeau informatif (lecture seule), plus besoin de resélectionner
4. **Responsive deleted table** : Ajout de `overflow-x-auto` et `min-w-[600px]` sur le tableau des notes supprimées

---

## 🟠 CORRECTIF IMPORTANT — PAIEMENTS : school_year explicite dans le formulaire

### Symptôme
"Paiement enregistré" toast mais risque de paiement sans année scolaire si le backend ne trouve pas d'année active.

### Cause racine
Le formulaire de paiement n'envoyait pas `school_year`. Le backend faisait une auto-affectation conditionnelle (`if not serializer.validated_data.get("school_year")`), mais si aucune année active existait, le paiement était créé sans année.

### Fichier modifié
`frontend/src/pages/admin/Payments.jsx`

### Correction
- Ajout `<input type="hidden" {...register("school_year")} defaultValue={currentYear?.id} />`
- `onSubmit` enrichit explicitement avec `school_year: d.school_year || currentYear?.id`

---

## 🟡 CORRECTIF MESSAGERIE — Responsive mobile (tous profils)

### Symptôme
Sur mobile, la liste de conversations et le fil de messages s'affichaient ensemble → superposition, textes tronqués illisibles.

### Cause racine
Layout grid `grid-cols-1 lg:grid-cols-3` mais les deux panneaux visibles simultanément sur mobile (pas de logique de navigation).

### Fichiers modifiés
`frontend/src/pages/admin/Messages.jsx`  
`frontend/src/pages/teacher/Messages.jsx`  
`frontend/src/pages/parent/Messages.jsx`  
`frontend/src/pages/student/Messages.jsx`  

### Correction
- Ajout de l'état dérivé `activeThread = !!selectedId`
- Liste de conversations : `hidden lg:flex` quand `activeThread` est vrai (mobile uniquement)
- Panneau conversation : `hidden lg:flex` quand `!activeThread`, `flex` quand `activeThread`
- Bouton retour `<ArrowLeft>` déjà présent dans le header du thread → fonctionnel

---

## RÉSUMÉ DES FICHIERS MODIFIÉS

| Fichier | Modification |
|---------|-------------|
| `frontend/src/router/index.jsx` | ✅ Ajout routes `/admin/user-files` et `/admin/branding` |
| `frontend/src/api/index.js` | ✅ Ajout `/notifications/unread-count/` dans NON_CRITICAL_ENDPOINTS |
| `frontend/src/pages/admin/Grades.jsx` | ✅ Row-click selection, préremplissage edit, responsive deleted table |
| `frontend/src/pages/admin/Payments.jsx` | ✅ school_year explicite dans le formulaire de création |
| `frontend/src/pages/admin/Messages.jsx` | ✅ Responsive mobile (liste/thread toggle) |
| `frontend/src/pages/teacher/Messages.jsx` | ✅ Idem |
| `frontend/src/pages/parent/Messages.jsx` | ✅ Idem |
| `frontend/src/pages/student/Messages.jsx` | ✅ Idem |

---

## PROBLÈMES NON RÉGRESSÉS (déjà corrigés dans v20/v21, vérifiés)

- ✅ Endpoint `/notifications/unread-count/` (hyphen) — existant et fonctionnel
- ✅ Messages longs — `whitespace-pre-wrap break-words overflow-wrap-anywhere` déjà en place
- ✅ Bulletins — générateur PDF complet (notes, moyennes, rang, appréciations, bilingue)
- ✅ Filtre année scolaire active — global sur paiements, notes, devoirs, annonces
- ✅ Historique des notes — audit trail complet (`GradeHistory`)
- ✅ Soft-delete notes avec justification obligatoire
- ✅ Permissions RBAC — superadmin > admin > teacher > parent/student
- ✅ Sessions JWT stables — refresh automatique avec intercepteur Axios

---

## GUIDE DE DÉPLOIEMENT RAPIDE (correctifs uniquement)

```bash
# 1. Mettre à jour les fichiers frontend
cp -r feba_v22/frontend/src/router/index.jsx  <projet>/frontend/src/router/
cp -r feba_v22/frontend/src/api/index.js      <projet>/frontend/src/api/
cp -r feba_v22/frontend/src/pages/admin/Grades.jsx    <projet>/frontend/src/pages/admin/
cp -r feba_v22/frontend/src/pages/admin/Payments.jsx  <projet>/frontend/src/pages/admin/
cp -r feba_v22/frontend/src/pages/admin/Messages.jsx  <projet>/frontend/src/pages/admin/
cp -r feba_v22/frontend/src/pages/teacher/Messages.jsx <projet>/frontend/src/pages/teacher/
cp -r feba_v22/frontend/src/pages/parent/Messages.jsx  <projet>/frontend/src/pages/parent/
cp -r feba_v22/frontend/src/pages/student/Messages.jsx <projet>/frontend/src/pages/student/

# 2. Rebuild frontend
cd <projet>/frontend && npm run build

# 3. Aucune migration backend requise pour ces correctifs
```

---

## TESTS DE VALIDATION

### Test 1 — Fichiers (admin)
1. Se connecter en tant qu'admin
2. Cliquer sur "Fichiers" dans le menu → ✅ Page UserFiles s'affiche (pas de déconnexion)
3. Cliquer sur "Branding & Logo" → ✅ Page Branding s'affiche (pas de déconnexion)

### Test 2 — Notes row-click
1. Aller sur `/admin/grades`
2. Cliquer sur une ligne de la liste → ✅ Panneau détail s'affiche à droite
3. Cliquer sur "Modifier" dans le panneau → ✅ Modal s'ouvre avec tous les champs préremplis
4. Aucune resélection manuelle d'élève/matière/période requise en édition ✅

### Test 3 — Paiements
1. Créer un nouveau paiement → ✅ school_year envoyé automatiquement
2. Vérifier en DB que `school_year_id` est non-null

### Test 4 — Messagerie mobile
1. Ouvrir l'app sur mobile (viewport <768px)
2. Aller sur Messages → ✅ Liste des conversations visible
3. Cliquer sur une conversation → ✅ Fil de messages en plein écran
4. Cliquer sur la flèche retour → ✅ Retour à la liste

### Test 5 — Notifications sans déconnexion
1. Ouvrir l'app, attendre que le layout charge
2. Vérifier en console réseau que `/notifications/unread-count/` ne déclenche pas de redirect `/login` même si 401 initial
