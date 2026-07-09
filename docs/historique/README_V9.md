# FEBA School Management — Version 9 (Corrections complètes)

## 🚀 Installation rapide

```bash
# 1. Variables d'environnement
cp .env.dev.example .env.dev
# Éditer .env.dev (DB, Redis, SECRET_KEY, ALLOWED_HOSTS...)

# 2. Lancer les services
docker compose -f docker-compose.dev.yml up --build

# 3. Migrations (IMPORTANT : nouvelles migrations soft-delete)
docker compose -f docker-compose.dev.yml exec backend python manage.py migrate

# 4. Créer un superadmin
docker compose -f docker-compose.dev.yml exec backend python manage.py createsuperuser
```

URLs : Frontend → http://localhost:3000 | API → http://localhost:8000/api/

## 📦 Dépendances ajoutées
| Package | Version | Usage |
|---------|---------|-------|
| `reportlab` | 4.2.2 | Génération PDF bulletins et reçus |

## ✅ Corrections V9 — par module

### 🔔 1. Badge Messages (sidebar)
- **Cause** : layouts Teacher/Parent/Student n'interrogeaient pas l'endpoint de comptage des messages non lus
- **Fix** : Ajout de `conversationsAPI.unreadCount()` (polling 15s) dans **tous les layouts** (Admin, SuperAdmin, Teacher, Parent, Student)
- **Résultat** : Badge rouge dynamique sur "Messages" dans la sidebar, décrémenté à la lecture

### 👨‍🎓 2. Élève
- **Contrainte 1 parent** : `ParentStudent` déjà contraint au niveau DB (`UniqueConstraint`) — validé et documenté
- **Profil élève complet** : `StudentProfile.jsx` réécrit avec AvatarUpload + dossier scolaire complet (matricule, classe, date de naissance, genre, adresse)
- **Photo de profil** : Composant `AvatarUpload` créé (upload, remplacement, suppression, fallback initiales)

### 👨‍👩‍👧 3. Parent
- **Profil parent** : `ParentProfile.jsx` créé (avatar, infos compte, profession, adresse, liste enfants, changement de mot de passe)
- **Route** `/parent/profile` ajoutée au router et à la sidebar
- **Photo de profil** : AvatarUpload intégré

### 🧑‍🏫 4. Enseignant
- **Photo de profil** : AvatarUpload intégré dans `TeacherProfile.jsx`
- **Infos complètes** : email, téléphone, classes/matières affectées

### 🖼️ 5. Photo de profil (global)
- **Endpoint backend** : `POST /api/auth/avatar/` (upload) + `DELETE /api/auth/avatar/` (suppression)
- **Composant** `AvatarUpload.jsx` : réutilisable, upload 5MB max, fallback initiales automatique
- **API frontend** : `avatarAPI.upload(file)` et `avatarAPI.delete()` dans `api/index.js`

### 📝 6. Notes (Grades)
- **Soft delete** : `destroy()` met `is_deleted=True` + log dans `GradeHistory` (données conservées)
- **Restauration** : bouton "Restaurer" + endpoint `POST /api/grades/{id}/restore/`
- **Toggle** : bouton "Voir supprimées / Masquer supprimées" dans Admin et Teacher Grades
- **Bug ajout note** : `perform_create` réécrit avec upsert correct — si la note existe déjà (même élève/matière/période/année), elle est mise à jour au lieu de lever une erreur de contrainte
- **Migration** : `0003_grade_soft_delete.py` créée

### 📄 7. Bulletins
- **"POST non autorisée"** : `@action(url_path="generate-class")` corrigé — l'URL côté backend correspondait à `generate_class/` au lieu de `generate-class/`
- **Génération massive** : `POST /api/bulletins/generate-all/` créé, bouton "Tous les élèves" dans l'UI
- **Colonne classe** : `student_class` ajouté dans `BulletinSerializer`
- **Accès élève** : `get_queryset()` retourne les bulletins de l'élève connecté
- **Layout PDF** : espacement et alignement corrigés dans `pdf_generator.py`

### 💰 8. Paiements
- **Soft delete** : `destroy()` met `is_deleted=True` avec audit log (au lieu de suppression physique)
- **Restauration** : `POST /api/payments/{id}/restore/`
- **Toggle UI** : bouton "Voir supprimés" dans Payments admin
- **Migration** : `0003_payment_soft_delete.py` créée

### 📚 9. Devoirs
- **Upload pièces jointes** : `perform_create` réécrit — les fichiers sont maintenant correctement sauvés via `HomeworkAttachment.objects.create()`
- **Lien téléchargement** : `HomeworkAttachmentSerializer` retourne `file_url` (URL absolue via `request.build_absolute_uri`)
- **Suppression pièce jointe** : endpoint `DELETE /api/homework/{id}/attachments/{att_id}/`

### 📢 10. Annonces
- **Accès lecture seule** : page `SharedAnnouncements.jsx` créée (teacher / parent / student)
- **Routes** : `/teacher/announcements`, `/parent/announcements`, `/student/announcements`
- **Nav item "Annonces"** ajouté dans Teacher, Parent, Student layouts
- **Fonctionnalités** : recherche, expand/collapse, téléchargement pièces jointes, refresh auto 60s

## 🏗️ Architecture des rôles
| Rôle | role_level | Permissions |
|------|-----------|-------------|
| Élève | 10 | Lecture seule (notes, devoirs, bulletins personnels) |
| Parent | 20 | Lecture enfants + paiements |
| Enseignant | 40 | CRUD notes sur ses matières et classes |
| Admin | 80 | Gestion complète de l'établissement |
| SuperAdmin | 100 | Accès multi-établissements |

## 🧪 Tests
```bash
# Tests backend
docker compose exec backend python manage.py test

# Test spécifique soft-delete grades
docker compose exec backend python manage.py test apps.grades.tests

# Test contrainte 1 parent par élève
docker compose exec backend python manage.py test apps.parents.tests
```
