# Authentification

**Symptôme :** vidéo du 02/11 à 22:31. Première validation : « Identifiants incorrects ». Deuxième : connexion.

**Preuve que le serveur acceptait :** journaux nginx, `POST /api/auth/login/` en 200 à 21:31:33 puis 21:31:35, et à 20:34:58 puis 20:34:59.

**Cause racine, côté navigateur**
1. `login()` enregistrait les jetons avec un utilisateur nul.
2. `AcademyProvider` se réveillait et appelait `setAcademyScope()`.
3. Cela annulait les requêtes en vol, dont `GET /auth/me/`.
4. `LoginPage` traduisait toute exception en « Identifiants incorrects ».

Le défaut dépend du timing.

**Pourquoi les audits précédents l'ont raté :** pas de latence en local, et mes scripts attendaient l'URL finale sans lire les messages ni compter les tentatives.

**Reproduction :** latence de 250 ms, compte superadmin : POST 200, `/auth/me/` annulée, message identique.

**Correction**
- `hooks/useAuth.js` : profil lu avant d'enregistrer la session.
- `api/index.js` : `horsPortee` protège cette lecture.
- `pages/LoginPage.jsx` : message selon la vraie cause. Le refus « compte désactivé » n'est plus masqué.

## Validation

| Critère | Résultat | Niveau |
|---|---|---|
| Première tentative | Réussie sur les 5 rôles | Chrome local, 0 à 450 ms, 0 échec sur chaque passe achevée |
| Une seule requête | Oui, y compris au double clic | Chrome local |
| Rechargement, déconnexion, reconnexion | Oui | Chrome local, administrateur |
| Mobile, anglais, Entrée | Oui | Chrome local, un rôle chacun |
| Session expirée | Oui | Chrome local |
| Mauvais mot de passe, compte inconnu | Refusés | Chrome local |
| Test qui aurait détecté le défaut | Échoue sur l'ancien ordre | `useAuth.connexion.test.jsx` |
| **En production** | **À confirmer par vous** | Pas de compte de test |
| Gestionnaire de mots de passe réel | **Non testé** | Remplissage simulé |

Aussi corrigé : `last_login` n'était jamais renseigné à la connexion. Sa valeur reste vide jusqu'à la prochaine connexion de chaque compte.
