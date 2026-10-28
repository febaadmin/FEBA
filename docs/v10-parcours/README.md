# Parcours navigateur V10 — preuves

Captures produites par `parcours.mjs` (Playwright / Chromium) contre
l'application FEBA servie en local, avec l'académie **FEBA FHA laissée
dans l'état exact des captures d'écran du rapport** : une année scolaire
existante, jamais activée — l'état où tous les menus tombaient à zéro.

| Fichier | Ce qu'il montre |
|---|---|
| `A-tableau-de-bord.png` | connexion administrateur FEBA FHA |
| `B-menu-classe.png` | le menu « Classe » d'une nouvelle salle propose les 3 classes FHA |
| `C-classes-assignees.png` | « Classes assignées » ne dit plus « Aucun résultat » |
| `D-salles-physiques.png` | « Salles physiques de l'école » n'est plus à 0 |
| `E-parcours-linguistique.png` | le sélecteur « Parcours linguistique » |
| `F-onglet-conference.png` | l'onglet plein écran, sans barre latérale ni en-tête |
| `F3-onglet-jitsi-injoignable.png` | Jitsi injoignable : un message explicite, jamais un écran noir |
| `G-feba-classes.png` | §37 — FEBA affiche toujours ses classes |

## Rejouer les parcours

```bash
# backend
cd backend && python manage.py migrate && python manage.py seed_demo_data
python manage.py runserver 127.0.0.1:8099

# frontend
cd frontend && BACKEND_ORIGIN=http://127.0.0.1:8099 npx vite --port 5173

# parcours
node docs/v10-parcours/parcours.mjs ./sorties
```

Le script attend Chromium ; il pointe par défaut le chemin Playwright de
l'environnement d'intégration. 15 vérifications, sortie non nulle si
l'une échoue.
