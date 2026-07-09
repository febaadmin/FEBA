# FEBA v20 — LIVRABLES ET INSTRUCTIONS DE TEST

## 📦 Contenu du ZIP

```
feba_v20/
├── backend/                    # Django + DRF (corrigé)
├── frontend/                   # React + Vite (corrigé)
├── nginx/                      # Configuration Nginx (inchangée)
├── scripts/                    # Scripts utilitaires
├── verify_feba.py              # ✅ Script de vérification automatique
├── incoherences_parent_eleve.csv  # 📊 Template — relancer verify_feba.py
├── README_CHANGELOG.md         # 📝 Changelog complet
├── DELIVERABLES.md             # Ce fichier
└── docker-compose.dev.yml      # Docker Compose dev
```

---

## 🚀 INSTALLATION

### 1. Variables d'environnement
```bash
cp .env.dev.example .env.dev
# Éditer .env.dev avec vos valeurs
```

### 2. Démarrage Docker
```bash
docker compose -f docker-compose.dev.yml up --build
```

### 3. Migrations Django
```bash
docker compose exec backend python manage.py migrate
```

Aucune nouvelle migration n'est requise pour v20 (corrections purement logiques).

---

## ✅ VÉRIFICATION AUTOMATIQUE

```bash
# Installer requests si nécessaire
pip install requests

# Lancer le script de vérification
python verify_feba.py \
  --url http://localhost:8000 \
  --email admin@feba.cd \
  --password votre_mot_de_passe \
  --output verify_results.json
```

Le script teste :
- ✔ Login / refresh / token
- ✔ Année scolaire active
- ✔ Branding (`/api/schools/branding/active/`)
- ✔ Notes (liste, supprimées, résumé)
- ✔ Bulletins (liste, pas de doublons)
- ✔ Messages (`/inbox/`, `/unread-count/`)
- ✔ Notifications (`/unread-count/`)
- ✔ Dashboard admin (données filtrées)
- ✔ Sécurité (401 sans token)
- ✔ Incohérences (CSV généré)

---

## 🧪 TESTS MANUELS RECOMMANDÉS

### A. Notifications — endpoint `/unread-count/`
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/notifications/unread-count/
# Attendu : {"count": 0}
```

### B. Messages — inbox
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/messages/inbox/
# Attendu : liste de messages
```

### C. Notes élève — plus de déconnexion
1. Se connecter en tant qu'élève
2. Naviguer vers "Mes notes"
3. Vérifier qu'aucune déconnexion ne se produit
4. Vérifier les moyennes trimestrielles affichées

### D. Bulletins — plus de doublons
1. Admin → Bulletins → Générer pour un élève/période
2. Re-générer le même élève/période
3. Vérifier qu'un seul bulletin apparaît en liste

### E. Suppression de note avec justification
1. Admin → Notes → icône supprimer (🗑️)
2. Laisser la justification vide → le bouton ne doit pas envoyer
3. Saisir une justification → suppression autorisée
4. Vérifier l'onglet "Supprimées" → note visible

### F. Restauration de note
1. Admin → Notes → onglet "Supprimées"
2. Cliquer "Restaurer" → note réapparaît dans la liste

### G. Dashboard admin — total élèves par année active
1. Admin → Dashboard
2. "Total élèves" doit afficher uniquement les élèves de l'année active

---

## ⚙️ CORRECTIONS RAPPLÉES

| # | Problème | Fix |
|---|----------|-----|
| 1 | 404 `/api/notifications/unread-count/` | Route explicite ajoutée |
| 2 | 401/404 `/api/messages/inbox/` | Route explicite ajoutée |
| 3 | 401/404 `/api/messages/unread-count/` | Route explicite ajoutée |
| 4 | Doublons de bulletins | Suppression avant régénération |
| 5 | Bulletins non filtrés par année | `get_queryset()` corrigé |
| 6 | Dashboard — données globales | `student_qs` filtré par année active |
| 7 | Crash élève → notes (Rules of Hooks) | `useQuery` dans `.map()` supprimé |
| 8 | `currentYear` non défini au moment de l'usage | Déclaration réordonnée |
| 9 | Suppression note sans justification | Validation backend + frontend |
| 10 | Pas de vue "notes supprimées" | Onglet ajouté dans admin/Grades |
| 11 | Élèves non filtrés lors création parent | Filtre `school_year` ajouté |
| 12 | `gradesAPI.delete` ne passait pas justification | Body corrigé dans api/index.js |
| 13 | `data` non déclaré dans admin/Bulletins | Composant réécrit |
| 14 | `deleted_by_name` absent du sérialiseur | `GradeSerializer` étendu |

