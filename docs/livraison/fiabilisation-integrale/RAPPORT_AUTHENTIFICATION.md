# Authentification

| Scénario | Résultat | Niveau |
|---|---|---|
| 5 profils, première tentative, 0 à 600 ms | Réussi | Local |
| Connexions successives, après déconnexion, rechargement | Réussi | Local, administrateur |
| Coupure sur la connexion ou le profil | Message de coupure, pas de session | Local |
| 502 et 429 simulés | Message adapté | Local |
| Double clic, Entrée | Une requête | Local |
| Session expirée | Réussi | Local |
| Mot de passe incorrect, compte inconnu | Refusés, même message | Local |
| Compte désactivé | Jeton refusé en 401, message exact avec le bon mot de passe | Local, API |
| Académie, langue, rechargement | Session gardée | Local |
| Révocation au changement de mot de passe, déconnexion | Réussi | PostgreSQL |
| Changement de rôle en cours de session | **Non testé** | - |
| Gestionnaire de mots de passe réel | **Non testé** | Vous |
| En production | **Une connexion à un seul POST observée à 22:47:57, à confirmer par vous** | Journal |
