# Retour arrière

**Automatique :** si le relais ne devient pas sain, l'ancienne version reste en service.

**Code :**
1. `git revert <commit>` dans une PR.
2. CI verte, fusion, déploiement automatique.

**Image précédente, sur le serveur :** le déploiement garde les images sous le tag `previous`.

| Élément | Retour |
|---|---|
| CSP | Remettre `Content-Security-Policy-Report-Only` dans `nginx/nginx.prod.conf` |
| Déploiement | Revert de la PR #60 |
| React Router | Revert, attention aux 2 vulnérabilités modérées |
| Migration `suivi.0006` | `migrate suivi 0005`, perd les dates d'archivage |

**Données :** ne jamais restaurer sans décision écrite. Restic est non testé : lancer d'abord le test de restauration.

Sauvegarde : instantané Restic à chaque déploiement.
