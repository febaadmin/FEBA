# RAPPORT DES CORRECTIONS — FEBA v25

Date : 2026-05-12
Version précédente : v23/v24
Version livrée : v25

---

## 1. 🔴 PARENT / ENSEIGNANT → DÉCONNEXION — CORRIGÉ DÉFINITIVEMENT

### Cause racine
Zustand `persist` est **asynchrone** : au premier rendu après une navigation,
`user` et `accessToken` sont `null` le temps que `localStorage` soit relu.
`ProtectedRoute` voyait `user=null` → redirect `/login` → apparaissait comme déconnexion.

### Fichiers modifiés
- `frontend/src/store/authStore.js`
- `frontend/src/router/index.jsx`

### Solution
**authStore** : ajout de `_hasHydrated: false` + `setHasHydrated()` + callback `onRehydrateStorage` qui passe le flag à `true` une fois localStorage relu.

**ProtectedRoute** : si `!_hasHydrated` → affiche un spinner "Chargement…" au lieu de rediriger. Dès hydratation complète, les vérifications auth normales reprennent.

```js
// authStore.js — clé ajoutée
onRehydrateStorage: () => (state) => {
  if (state) state.setHasHydrated(true);
}

// ProtectedRoute — guard ajouté
if (!_hasHydrated) return <Spinner />;  // ← plus jamais de redirect prématuré
```

---

## 2. 🟡 FAVICON / ICÔNE ÉCOLE — IMPLÉMENTÉ

### Fichiers modifiés
- `frontend/public/favicon.svg` *(nouveau)*
- `frontend/index.html`
- `frontend/src/hooks/useBranding.js`

### Solution
- Dossier `public/` créé avec `favicon.svg` aux couleurs FEBA (bleu #1E3A6E / or #C9A227)
- `index.html` : ajout `<link rel="alternate icon">` et `<link rel="apple-touch-icon">`
- `useBranding` : appel `updateFavicon(activeLogo)` via `useEffect` → onglet navigateur affiche le logo de l'école dès son chargement

---

## 3. 🔴 INSCRIPTION NOUVELLE ANNÉE "POST NON AUTORISÉE" — CORRIGÉ

### Cause racine
La méthode `enroll()` dans `StudentViewSet` n'avait **pas de décorateur `@action`** → DRF ne l'enregistrait pas comme route HTTP → 404/405.

### Fichiers modifiés
- `backend/apps/students/views.py`
- `frontend/src/api/index.js`
- `frontend/src/pages/admin/Students.jsx`

### Solution backend
Ajout du décorateur `@action` + 3 nouveaux endpoints :

| Endpoint | Description |
|----------|-------------|
| `POST /students/{id}/enroll/` | Inscrire **un** élève dans une nouvelle année |
| `POST /students/enroll-all-from-year/` | Inscrire **tous** les élèves d'une année précédente (1 clic) |
| `POST /students/enroll-class/` | Inscrire **tous les élèves d'une classe** dans une nouvelle année |
| `POST /students/promote/` | Existait déjà |

Tous : pas de duplication (skip si déjà inscrit), préservation historique, retour `{enrolled, skipped, failed}`.

### Solution frontend
- `studentsAPI` : ajout `enroll()`, `enrollAllFromYear()`, `enrollClass()`
- Bouton **"Inscrire tous (nouvelle année)"** dans le header de la page Élèves
- Modal 3 modes : Un élève / Toute une classe / Toute l'année
- Toast différencié : "N élève(s) inscrit(s), M déjà inscrit(s)"

---

## 4. 🟠 NOTES : PAGINATION + EXPORT EXCEL — AJOUTÉS

### Fichier modifié
`frontend/src/pages/admin/Grades.jsx`

### Pagination
- État `gradePage` + constante `GRADES_PER_PAGE = 20`
- Pagination numérique avec ellipses (1 … 4 5 6 … 12)
- Navigation précédent/suivant
- Compteur "N notes · Page X/Y"
- `useEffect` reset page à 1 quand les filtres changent

### Export Excel
- Import `XLSX` (SheetJS, déjà dans les dépendances)
- Bouton "Excel (N)" visible uniquement quand la liste a des résultats
- Colonnes : Élève, Matricule, Classe, Matière, Période, Type, Note, Coefficient, Lettre, Commentaire, Année, Date saisie
- Nom de fichier dynamique : `notes_{année}_{période}_{date}.xlsx`

---

## 5. 🔴 BULLETINS VIDES — CORRIGÉ EN PROFONDEUR

### Cause racine
`get_subject_averages()`, `_build_annual_subject_data()`, et `_ensure_zeros_for_period()` cherchaient uniquement les matières liées au `level_id` de la classe. Si les matières n'étaient pas assignées à ce niveau → `subjects = []` → bulletin vide.

### Fichiers modifiés
- `backend/apps/grades/models.py` — `get_subject_averages()`
- `backend/apps/grades/views.py` — `_ensure_zeros_for_period()`
- `backend/apps/bulletins/pdf_generator.py` — `_build_annual_subject_data()`

### Solution : fallback en 3 niveaux
```
1. Matières du niveau de la classe  (le plus précis)
2. Toutes les matières de l'école   (fallback standard)
3. Matières qui ont déjà des notes  (dernier recours, données réelles)
```

Ce fallback garantit que le bulletin sera toujours généré avec des données, même si la configuration est incomplète.

### Amélioration PDF
- Section "Informations élève" enrichie : Rang, Période, Année scolaire, Date de naissance
- Style alternant pour les lignes de la fiche élève

---

## RÉSUMÉ DES FICHIERS MODIFIÉS

| Fichier | Modification |
|---------|-------------|
| `frontend/src/store/authStore.js` | ✅ Hydration guard `_hasHydrated` |
| `frontend/src/router/index.jsx` | ✅ ProtectedRoute attend l'hydration |
| `frontend/public/favicon.svg` | ✅ NOUVEAU — favicon école |
| `frontend/index.html` | ✅ Tags favicon complets |
| `frontend/src/hooks/useBranding.js` | ✅ Favicon dynamique depuis logo école |
| `backend/apps/students/views.py` | ✅ `@action` enroll + enroll_all_from_year + enroll_class |
| `frontend/src/api/index.js` | ✅ enrollAllFromYear, enrollClass, enroll |
| `frontend/src/pages/admin/Students.jsx` | ✅ Modal 3 modes + bouton global |
| `frontend/src/pages/admin/Grades.jsx` | ✅ Pagination (20/page) + Export Excel |
| `backend/apps/grades/models.py` | ✅ Fallback 3 niveaux get_subject_averages |
| `backend/apps/grades/views.py` | ✅ Fallback school dans _ensure_zeros |
| `backend/apps/bulletins/pdf_generator.py` | ✅ Fallback annual + rang dans info élève |

---

## TESTS DE VALIDATION

### Test 1 — Parent/Enseignant (admin)
1. Se connecter en admin
2. Cliquer sur "Parents" dans le menu → ✅ Page Parents s'affiche (spinner bref, pas de déconnexion)
3. Cliquer sur "Enseignants" → ✅ Idem
4. Naviguer rapidement entre 5 pages → ✅ Aucune déconnexion

### Test 2 — Favicon
1. Ouvrir l'app → ✅ Icône FEBA visible dans l'onglet
2. Si logo école configuré dans Branding → ✅ Onglet affiche ce logo

### Test 3 — Inscription nouvelle année
1. Aller sur /admin/students
2. Cliquer "Inscrire tous (nouvelle année)" → mode "Toute l'année"
3. Sélectionner année source 2023-2024 → cible 2024-2025 → ✅ N élèves inscrits
4. Relancer → ✅ "N déjà inscrits, 0 inscrit" (pas de duplication)
5. Ouvrir fiche élève → "Nouvelle année" → mode "Un élève" → ✅ fonctionne

### Test 4 — Notes pagination + Excel
1. Aller sur /admin/grades avec >20 notes
2. ✅ Pagination visible en bas du tableau
3. Cliquer "Excel (N)" → ✅ Téléchargement fichier .xlsx avec toutes les notes

### Test 5 — Bulletins non vides
1. Générer un bulletin pour un élève qui a des notes
2. ✅ PDF contient : toutes les matières, moyennes, rang, appréciations, infos élève complètes
3. Générer pour un élève dont les matières ne sont pas liées à un niveau
4. ✅ Le fallback école/grades est utilisé → bulletin non vide
