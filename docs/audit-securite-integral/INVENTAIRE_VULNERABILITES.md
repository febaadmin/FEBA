# Inventaire des vulnérabilités

Niveaux : Détecté, Reproduit, Corrigé, Testé, Local (validé en local), Production (déployé et contrôlé).

| ID | Gravité | Problème | Cause | Scénario | Données | Correctif | Test | État |
|---|---|---|---|---|---|---|---|---|
| V1 | **Élevée** | XSS stocké par dépôt d'avatar | `AvatarUploadView` enregistrait tout fichier dans `/media/avatars/`, servi publiquement | Un compte dépose du HTML ou du SVG, un autre l'ouvre : script sur le domaine, vol des jetons en `localStorage` | Tous les comptes | `core/images.image_sure`, CSP `sandbox` sur `/media/` | `AvatarTests` | Reproduit, corrigé, testé PostgreSQL. Déployé par #56. Production : 0 avatar et 0 fichier actif, aucune trace d'exploitation |
| V2 | Moyenne | Injection de formule dans les exports CSV | Formulaires publics et listes exportés sans neutralisation | Un visiteur soumet `=HYPERLINK(...)`, l'administrateur ouvre l'export | Poste de l'administrateur | `core/csv_sur`, `utils/csv.js` | `CsvTests`, `csv.test.js` | Corrigé, testé. PR #57 |
| V3 | Moyenne | Jeton d'accès du WebSocket écrit dans les journaux nginx | Jeton dans l'URL | Lecture des journaux : session valable jusqu'à 60 min | Comptes connectés | Format de journal masqué | `nginx -t` seulement | Corrigé. PR #57. **Le jeton reste dans l'URL. Les journaux existants ne sont pas purgés** |
| V4 | Faible | Pièces jointes d'annonces et justificatifs sans contrôle de format | Pas de `checked_upload` | Fichier arbitraire stocké, servi en téléchargement | Admins, enseignants | `checked_upload` | `PiecesJointesTests` | Corrigé, déployé par #56 |
| V5 | Faible | `/django-admin/` sans limite | Pas de limite | Essais répétés de mots de passe | 1 compte staff | `limit_req` nginx | `nginx -t` seulement | Corrigé, limite non éprouvée en charge |
| V6 | Moyenne | Pas de CSP active | Aucune en-tête | Aggrave tout XSS | Tous | CSP **en observation seulement** | - | **Partiel** : à passer en blocage après observation |
| V7 | Moyenne | Jetons dans `localStorage` | Choix d'architecture | Lisibles en cas de XSS | Tous | Non corrigé : passer aux cookies HttpOnly touche toute l'authentification | - | Documenté |
| V8 | Moyenne | Connexion limitée par adresse seulement (20/min) | Pas de limite par compte | Essais distribués sur un compte | Tous | **Non appliqué** : une limite par compte permet de bloquer un utilisateur, ce qui demande votre accord | Scénario prêt | Décision humaine |
| V9 | Moyenne | Conteneur backend en root | Pas de `USER` dans le Dockerfile | Une faille d'exécution de code donne root dans le conteneur | Serveur | Non appliqué : droits des volumes de production à migrer | - | Plan documenté |
| V10 | Moyenne | Vulnérabilités de `react-router` (redirection ouverte, injection) | Version 6 | Limité : aucune redirection à partir d'un paramètre trouvée | Navigateur | Correctif seulement en version 7, majeure | `npm audit` | Documenté, non corrigé |
| V11 | Faible | Lien signé de fichier privé valable par simple possession | Jeton porteur, droit vérifié à l'émission | Lien transmis, utilisable jusqu'à expiration | Fichiers | Durée limitée. Non modifié | - | Documenté |
| V12 | Faible | Jeton d'accès valable jusqu'à 60 min après un changement de mot de passe | JWT sans état | Vol antérieur | Compte concerné | Refresh révoqué, access non | `SessionsTests` | Documenté |

## Contrôlés sans défaut trouvé

Ce sont des tests précis, pas une preuve d'absence de faille.

| Sujet | Contrôle | Résultat |
|---|---|---|
| Élévation de privilèges, mass assignment | `ElevationTests` | Refus |
| Compte désactivé, déconnexion, changement de mot de passe | `SessionsTests` | Coupure |
| Message de connexion identique, compte connu ou non | `SessionsTests` | Identique |
| IDOR entre académies | Campagne 2, 7, 19 académies, PostgreSQL | 8 sur 8 sans fuite |
| IDOR entre personnes d'une académie | `test_securite_personnes`, avec témoin positif | 0 accès |
| Injection SQL dans la recherche | 1 test, plus revue : pas de SQL brut trouvé | Sans effet |
| Secrets | Gitleaks, 223 commits ; recherche dans le bundle | 0 |
| Ports publics | Serveur : 22, 80, 443. 5432, 6379, 8000 fermés depuis l'extérieur | Conforme |
| TLS | 1.1 refusé, 1.2 et 1.3 acceptés, certificat jusqu'au 07/12/2026 | Conforme |
| `/.env`, `/.git/config` | 200 mais page HTML de l'application | Pas de fuite |
| Mots de passe | PBKDF2, 0 hash faible, 0 compte de démo exposé | Conforme |
| `.env.prod` | Droits 600 | Conforme |

**Limites :** pas de test d'intrusion externe, pas d'analyse des images Docker, pas de revue ligne à ligne de chaque API, pas de scan OSV. `pip-audit` n'a pas abouti : les dépendances ne sont pas toutes figées, le contrôle repose sur le job de la CI.
