# FEBA School Management — Corrections V8.1

## Résumé des corrections par module

### 🗓️ Emploi du temps (`Schedule.jsx`)
- **Bug critique** : `Uncaught ReferenceError: classes is not defined` causant une page blanche
- **Correction** : Ajout des variables `classes` et `schedules` extraites correctement depuis les résultats des requêtes React Query (`classData` et `data`)

### 👨‍🎓 Gestion Élève (`Students.jsx`)
- **Correction 1** : Suppression du champ "Associer un parent" dans le formulaire de création d'élève. L'association parent-élève se fait uniquement depuis la création du parent
- **Correction 2** : Les champs `Prénom` et `Nom` sont maintenant `readOnly` dès qu'un compte utilisateur est sélectionné (auto-remplissage non modifiable)

### 👪 Gestion Parent (`Parents.jsx`)
- **Correction** : Ajout d'un modal de détail complet au clic d'une ligne : nom, email, téléphone, profession, adresse, liste des enfants associés avec la relation (père/mère/tuteur)
- **Amélioration UX** : Le bouton "Modifier" dans le détail ouvre directement le formulaire d'édition

### 💬 Messages / Notifications
- **Bug** : Les parents et élèves ne voyaient aucune notification (cloche non fonctionnelle)
- **Correction** : `ParentLayout.jsx` et `StudentLayout.jsx` entièrement réécrits avec :
  - Panel de notifications fonctionnel (cloche avec badge rouge)
  - Polling automatique toutes les 30 secondes
  - Marquage lu global
  - Affichage de toutes les notifications (nouvelles notes, messages, paiements...)

### 📝 Notes
- **Correction 1 — Restriction enseignant** : Le formulaire de saisie utilise maintenant `teachersAPI.mySubjects()` au lieu de `subjectsAPI.list()` → l'enseignant ne voit que ses propres matières assignées
- **Correction 2 — Historique (enseignant)** : Cliquer sur une note ouvre un modal avec l'historique complet (création, modification, ancienne valeur, nouvelle valeur, auteur, justification, date)
- **Correction 3 — Historique (admin)** : Même fonctionnalité ajoutée dans `admin/Grades.jsx`
- **Correction 4 — Justification** : Champ justification ajouté dans le formulaire de saisie de note
- **Correction 5 — API** : `gradesAPI.history(id)` et `gradesAPI.bulkSave(d)` ajoutés dans `api/index.js`

### 📄 Bulletins
- **Bug** : `No module named 'reportlab'`
- **Correction** : Ajout de `reportlab==4.2.2` dans `backend/requirements/base.txt`
- Le code des générateurs PDF (`bulletins/pdf_generator.py` et `payments/pdf_generator.py`) utilise bien ReportLab

### 💰 Paiements
- **Correction 1 — Suppression** : Le bouton "Supprimer" retournait 405. La méthode `destroy()` permet maintenant la suppression pour les administrateurs/superadmins (role_level ≥ 80) avec traçabilité dans `PaymentHistory`
- **Correction 2 — API frontend** : Ajout de `paymentsAPI.delete(id)` et `paymentsAPI.history(id)` dans `api/index.js`
- **Correction 3 — URL reçu** : L'endpoint `generate-receipt` avait une URL incorrecte (`generate_receipt` côté backend). Corrigé avec `url_path="generate-receipt"` sur le décorateur `@action`

### 📚 Devoirs (`Homework.jsx`)
- **Correction** : Cliquer sur un devoir ouvre maintenant un modal de détail affichant :
  - Titre, description complète
  - Classe, matière, enseignant, date limite
  - Liste des pièces jointes avec liens de téléchargement directs

---

## Instructions d'installation

### Prérequis
- Docker & Docker Compose
- Node.js 20+ (développement local uniquement)
- Python 3.12+

### Lancement (développement)

```bash
# 1. Copier le fichier d'environnement
cp .env.dev.example .env.dev
# Éditer .env.dev avec vos valeurs (DB, Redis, secret key...)

# 2. Lancer tous les services
docker compose -f docker-compose.dev.yml up --build

# 3. Migrations (premier lancement)
docker compose -f docker-compose.dev.yml exec backend python manage.py migrate

# 4. Créer un superadmin
docker compose -f docker-compose.dev.yml exec backend python manage.py createsuperuser

# 5. Charger les données de démo (optionnel)
docker compose -f docker-compose.dev.yml exec backend python manage.py seed_demo_data
```

L'application est disponible sur :
- **Frontend** : http://localhost:3000
- **Backend API** : http://localhost:8000/api/
- **Admin Django** : http://localhost:8000/admin/

### Dépendances clés ajoutées
| Package | Version | Usage |
|---------|---------|-------|
| `reportlab` | 4.2.2 | Génération PDF bulletins et reçus de paiement |

### Lancement (production)

```bash
cp .env.prod.example .env.prod
# Remplir toutes les variables (SECRET_KEY, DB, ALLOWED_HOSTS...)
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate
docker compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --no-input
```

---

## Architecture des rôles

| Rôle | role_level | Permissions clés |
|------|-----------|-----------------|
| Élève | 10 | Lecture seule (notes, devoirs, bulletins personnels) |
| Parent | 20 | Lecture enfants + paiements |
| Enseignant | 40 | CRUD notes sur ses matières et classes uniquement |
| Admin | 80 | Gestion complète de l'établissement |
| SuperAdmin | 100 | Accès multi-établissements |

---

## Tests

```bash
# Tests backend
docker compose -f docker-compose.dev.yml exec backend python manage.py test

# Tests spécifiques parent-élève
docker compose -f docker-compose.dev.yml exec backend python manage.py test tests.test_parent_student
```
