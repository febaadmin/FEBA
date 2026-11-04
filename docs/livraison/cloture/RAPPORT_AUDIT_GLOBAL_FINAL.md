# Audit global : recherche active de défauts (04/11/2026)

Objectif : trouver les défauts **sans attendre qu'ils soient signalés**. Chaque constat a été démontré (reproduction, journal ou requête en lecture seule), puis corrigé à la cause, avec un test de non-régression.

Légende des environnements :
- **U** : test unitaire ou d'intégration (PostgreSQL local) ;
- **N** : navigateur local, base jetable ;
- **CI** : GitHub Actions ;
- **PL** : production en lecture seule ;
- **PE** : production, écriture autorisée par la mission.

## 1. Défauts trouvés et corrigés

| # | Défaut | Comment il a été trouvé | Preuve | Cause racine | Correctif | Test |
|---|---|---|---|---|---|---|
| 1 | **Celery hors service depuis le 03/11** : worker 792 redémarrages, planificateur 1 444 | Revue des journaux de production (PL) | `VersionMismatch('Redis transport requires redis-py versions 6.1.0 or later. You have 5.0.3')` ; reproduit localement avec l'image de production | `kombu` non épinglé, installé en 5.7.0 | PR #76 : kombu 5.6.2, amqp, vine et billiard épinglés | CI : vrai worker et planificateur avec Redis ; déploiement : ping exigé |
| 2 | Sauvegarde plugNmeet en échec (ERR-310AC0) | Incident | Journal systemd ; reproduit 3/3 | Course avec le serveur MariaDB temporaire | PR #69 | 3/3 local ; 5 tests de surveillance (PR #74) ; sauvegarde et restauration réelles (PE) |
| 3 | Alertes superadmin invisibles : 87 notifications non lues | Croisement « la surveillance notifie » / « l'interface superadmin n'a pas de cloche » (PL) | Comptage en base | Cloche absente du gabarit superadmin | PR #73 : cloche, et e-mail pour les incidents critiques | 2 tests backend, 1 test frontend |
| 4 | nginx recréé à chaque déploiement | Journal du déploiement #68 | Configurations identiques, trois identifiants différents | Attestation de provenance horodatée | PR #71 | Essai local de construction |
| 5 | 63 écritures refusées sans message | Analyse statique des `useMutation` | E2E sans correctif : aucun message | Absence de gestionnaire d'erreur par défaut | PR #75 : `MutationCache.onError` | 3 tests unitaires ; contrôle E2E qui échoue sans le correctif |
| 6 | Deux dépôts FHA simultanés provoquent une erreur 500 | Recherche des numérotations « dernier + 1 » | `IntegrityError` reproduit (U) | Absence de verrou ou de nouvelle tentative | PR #74 | 3 tests PostgreSQL |
| 7 | Aide absente si les modules optionnels sont inactifs ; aide limitée à 3 rubriques | Inventaire des menus | Entrée « Aide » liée à `feature` | Choix d'origine | PR #72 : centre d'aide | 19 tests unitaires ; 38 contrôles E2E |
| 8 | Version de nginx divulguée (`Server: nginx/1.28.1`) | En-têtes de production (PL) | `curl -I` | `server_tokens` actif par défaut | PR #74 | `nginx -t` |
| 9 | Réinitialisation de mot de passe impossible pour un superadmin | Signalement utilisateur | — | Règle d'origine | PR #70 : ré-authentification, révocation des sessions, journal, e-mail | 26 tests backend ; E2E |
| 10 | Logo de /login sans lien | Signalement utilisateur | — | — | PR #70 | Unitaire ; E2E sur 3 tailles, en anglais et avec session |

## 2. Contrôles réalisés sans défaut trouvé

| Domaine | Contrôle | Résultat |
|---|---|---|
| API | Les 419 appels du frontend confrontés aux routes Django (résolution, méthode) | 0 incohérence (1 faux positif : action dynamique) |
| API | Appels hors du module central `api/index.js` | aucun |
| Données | Numérotations : paiements (aléatoire vérifié), matricules et documents (séquences verrouillées), préinscriptions (clé primaire) | sûres |
| Dépendances | `npm audit --omit=dev` ; `pip-audit -r requirements/prod.txt` | 0 vulnérabilité connue |
| TLS | TLS 1.0 et 1.1 refusés, 1.2 et 1.3 acceptés ; HTTP redirigé en 301 vers HTTPS ; certificat valide jusqu'au 07/12/2026 | conforme |
| En-têtes | HSTS avec preload, CSP, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy | présents |
| Exposition | `/.env` et `/.git/config` | page de l'application (index.html), aucune fuite |
| Exposition | `/api/schema/`, `/api/docs/` | 404 |
| Admin Django | `/django-admin/` public, limité par nginx à 10 requêtes par minute et par IP, un seul compte habilité | risque résiduel faible (§ 3) |
| Examens | Tentatives échues non remises pendant la panne Celery | 0 |
| Opérations asynchrones | Bulletins, campagnes, relances bloqués pendant la panne | 0 |
| Ressources | Disque 29 %, mémoire disponible 6 Go, charge 0,5 | correct |

## 3. Risques résiduels et décisions humaines

| Sujet | Constat | Proposition | Décision |
|---|---|---|---|
| Sauvegarde FEBA non surveillée | La surveillance FEBA ne contrôle que la sauvegarde plugNmeet. Un échec de `feba-backup.service` (Restic) ne déclenche aucune alerte | Le script root écrit une date de réussite dans un dossier monté en lecture seule dans le backend, et la surveillance la contrôle comme pour plugNmeet | Nécessite **root** (script hôte hors dépôt) |
| Sauvegardes plugNmeet sur le même serveur | Pas de copie hors site | Stockage externe | Humaine (coût) |
| Admin Django public | Limité par nginx | Restriction par IP ou VPN | Humaine |
| Rechargement nginx sans coupure | Le montage d'un fichier unique impose un redémarrage (~1 s) quand `nginx/` change | Monter le dossier `nginx/` | À tester séparément |
| Dépendances transitives non épinglées | Seules celles de Celery le sont désormais | Fichier de verrouillage (`pip-compile`) | Prochaine étape technique |
| HttpOnly | Les jetons restent dans `localStorage` | Plan documenté en phase 2 | Non migré |

## 4. Limites de cet audit

- Pas de test d'intrusion actif en production. Les sondes sont limitées à des GET publics, sans compte.
- Pas de revue ligne à ligne de tous les endpoints. Les classes de défauts ont été recherchées par motifs : numérotation, mutations sans erreur, appels sans route, dépendances.
- Les parcours réels des 5 profils en production n'ont pas été rejoués avec de vrais comptes : aucun compte de production n'a été créé et aucun mot de passe demandé.
