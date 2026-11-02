# Audit de sécurité

**FEBA n'est pas déclaré sûr à 100 %.** Détail : `INVENTAIRE_VULNERABILITES.md`.

Découvert par lecture de code et tests d'attaque, pas par les scanners : la faille V1. Bandit, Semgrep et Gitleaks n'ont rien remonté de bloquant après tri : URL d'appel issues de la configuration, faux positifs sur le mot « password » dans des journaux.

Domaines revus : authentification, jetons, permissions, isolation, fichiers, frontend, secrets, nginx, Docker, CI.

| Domaine | Constat |
|---|---|
| CI | `permissions: contents: read`, pas de `pull_request_target` |
| CORS | Origine étrangère non autorisée |
| Cookies, HSTS | Sécurisés |
| WebSocket | Authentifié, salon limité à ses membres. Jeton dans l'URL (V3) |
| Conversion de documents | Limites sur les archives, sous-processus avec délai |
| Redis, PostgreSQL | Réseau interne seulement. Mot de passe Redis non vérifié |
| 4 comptes superadmin, 1 staff | À revoir par l'établissement |

Non contrôlé : pare-feu du fournisseur (`ufw` non lisible sans root), sauvegardes distantes.
