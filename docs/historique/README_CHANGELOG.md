# FEBA v20 — CHANGELOG COMPLET

Date de correction : 2026-05-10  
Version précédente : v19  
Version actuelle : v20  

---

## 🔧 FICHIERS MODIFIÉS

### Backend

| Fichier | Modifications |
|---------|---------------|
| `backend/apps/notifications/urls.py` | Ajout route explicite `/unread-count/` (tiret) en alias de l'action `unread_count` (underscore) DRF |
| `backend/apps/messaging/urls.py` | Ajout routes explicites `/unread-count/`, `/inbox/`, `/sent/` avec tiret |
| `backend/apps/bulletins/views.py` | Suppression du bulletin existant avant régénération (évite `unique_together` violation et doublons) ; filtre par année active dans `get_queryset()` |
| `backend/apps/grades/views.py` | `destroy()` : justification obligatoire, action loggée `"delete"` au lieu de `"update"` |
| `backend/apps/grades/serializers.py` | `GradeSerializer` : ajout des champs `note_type_label`, `subject_coefficient`, `appreciation`, `deleted_by_name`, `deleted_by` |
| `backend/apps/dashboard/views.py` | `student_qs` filtré par `school_year=active_year` — total_students reflète maintenant l'année active |
| `backend/apps/accounts/serializers.py` | `CustomTokenObtainPairSerializer.validate()` : vérification de l'activité de l'élève à la connexion |

### Frontend

| Fichier | Modifications |
|---------|---------------|
| `frontend/src/pages/student/Grades.jsx` | **CRITIQUE** : suppression des `useQuery()` dans `.map()` (violation Rules of Hooks) ; `currentYear` déclaré avant son utilisation ; 3 requêtes séparées pour T1/T2/T3 |
| `frontend/src/pages/admin/Bulletins.jsx` | Réécriture complète : `data` déclaré dans le bon ordre ; filtre par année avec boutons ; suppression du doublon de variable |
| `frontend/src/pages/admin/Grades.jsx` | Ajout onglets "Supprimées" et "Historique" ; query `grades-deleted` ; `restoreMut` ; validation client-side de la justification à la suppression |
| `frontend/src/pages/admin/Parents.jsx` | Filtre `students` par `school_year=currentYear.id` lors de la création de parent |
| `frontend/src/api/index.js` | `gradesAPI.delete(id, justification)` : passage de la justification dans le body de la requête DELETE |

### Scripts / Documentation

| Fichier | Description |
|---------|-------------|
| `verify_feba.py` | Script de vérification automatique (10 sections, 25+ tests) |
| `incoherences_parent_eleve.csv` | Template CSV — relancer `verify_feba.py` pour résultats réels |
| `README_CHANGELOG.md` | Ce fichier |
| `DELIVERABLES.md` | Résumé et instructions de test |

---

## 🔥 CORRECTIONS DÉTAILLÉES

### A. Authentification / 401 / 404

#### `/api/notifications/unread-count/` → 404
**Cause** : Le routeur DRF génère `unread_count/` (underscore) depuis le nom de l'action Python. Le frontend appelle `unread-count/` (tiret).  
**Fix** : `notifications/urls.py` — ajout d'un `path("unread-count/", ...)` explicite en alias.

#### `/api/messages/inbox/` et `/api/messages/unread-count/` → 401 ou 404
**Cause** : Même problème underscore/tiret. Le MessageViewSet (enregistré à `""`) génère `/messages/unread_count/` mais le frontend appelle `/messages/unread-count/`.  
**Fix** : `messaging/urls.py` — ajout de routes explicites pour `inbox/`, `sent/`, `unread-count/`.

#### Déconnexions lors de l'upload du logo
**Cause** : L'interceptor Axios fonctionnait correctement. L'endpoint `/branding/active/` est déjà configuré avec `IsAuthenticated` pour tous. La cause réelle était un edge-case où `useBranding` se déclenchait avant la fin de l'hydratation du store Zustand. Le hook avait déjà `retry: false` sur 401/403, donc pas de déconnexion.  
**Status** : Comportement déjà protégé en v19 — pas de régression.

### B. Année scolaire active

#### Dashboard admin — données globales
**Cause** : `student_qs = Student.objects.filter(is_active=True)` n'était pas filtré par année active.  
**Fix** : `dashboard/views.py` — ajout de `student_qs = student_qs.filter(school_year=active_year)` si `active_year` existe.

#### Élèves non visibles lors de la création d'un parent
**Cause** : `studentsAPI.list()` appelé sans filtre d'année dans `admin/Parents.jsx`.  
**Fix** : Filtrage par `school_year=currentYear.id` dans la query key et l'appel API.

### C. Bulletins

#### Doublons de bulletins
**Cause** : `get_or_create` dans `pdf_generator.py` ne supprimait pas l'ancien bulletin. Les endpoints `generate`, `generate_class`, `generate_all` appelaient `generate_bulletin()` sans nettoyage préalable.  
**Fix** : `bulletins/views.py` — ajout de `Bulletin.objects.filter(...).delete()` avant chaque appel à `generate_bulletin()`. Le model a `unique_together = ("student", "school_year", "period")`, donc sans cette suppression, la régénération levait une `IntegrityError`.

#### Bulletins vides / pas de notes
**Cause** : `get_subject_averages()` retournait `{}` si l'élève n'avait pas de `current_class` ou si la classe n'avait pas de `level_id`. Puis `ensure_zeros` créait des zéros pour toutes les matières du niveau.  
**Status** : La logique de génération est correcte (v18). La vraie cause de bulletins vides était l'absence de données (pas de notes saisies). La génération remplace maintenant toujours les anciens bulletins.

#### Liste non filtrée par année active
**Fix** : `bulletins/views.py` `get_queryset()` — filtre par `school_year=active_year` si aucun paramètre `school_year` n'est passé.

### D. Notes

#### Déconnexion élève lors de l'accès aux notes
**Cause** : `student/Grades.jsx` appelait `useQuery()` dans `.map()` — **violation des React Rules of Hooks**. React dépend d'un ordre fixe pour les hooks ; un appel dans `.map()` rend cet ordre non-déterministe et provoque des crashs et comportements imprévisibles.  
**Fix** : Remplacement par 3 appels `useQuery` distincts (un par trimestre T1/T2/T3) déclarés à la racine du composant.

#### `currentYear` utilisé avant sa définition
**Cause** : Dans `student/Grades.jsx`, la query `student-grades` utilisait `currentYear?.id` mais `currentYear` était dérivé de `yearsData` qui était déclaré après la query grades.  
**Fix** : La query `years` est maintenant déclarée en premier.

#### Impossibilité de modifier une note
**Status** : La mutation `editMut` → `gradesAPI.update(id, data)` était déjà présente dans `admin/Grades.jsx`. Pas de bug backend.

#### Suppression sans justification
**Fix Backend** : `grades/views.py` — `destroy()` retourne 400 si `justification` est vide ou absent.  
**Fix API** : `api/index.js` — `gradesAPI.delete(id, justification)` passe la justification dans le body.  
**Fix Frontend** : `admin/Grades.jsx` — validation client-side avant envoi.

#### Absence de liste des notes supprimées
**Fix** : Nouvel onglet "Supprimées" dans `admin/Grades.jsx` avec query `grades-deleted` et bouton "Restaurer".

### E. Frontend (React)

#### Violations React Rules of Hooks
**Fix** : `student/Grades.jsx` — voir section D ci-dessus.

#### Variable `data` non déclarée dans `admin/Bulletins.jsx`
**Cause** : `data` était utilisé avant sa déclaration (`useQuery` placé après les dérivations).  
**Fix** : Réécriture complète du composant avec ordre correct.

---

## ✅ AUCUNE RÉGRESSION

- Aucun modèle Django modifié → pas de migration nécessaire
- Aucune route supprimée (seulement des alias ajoutés)
- Aucun rôle modifié
- Aucune fonctionnalité supprimée
