# Déploiement : état final et mesures

Date : 04/11/2026. Production `globalfeba.com` (`62.238.38.111`). Sonde : `sonde.py`, GET en lecture seule toutes les 0,3 s sur `/api/health/` et `/login`, sans compte ni écriture. Machine maintenue éveillée pendant la mesure.

## 1. Recréation inutile de nginx : cause exacte

Constat du 03/11 (déploiement #68) : nginx a été recréé alors que sa configuration et son image n'avaient pas changé.

| Déploiement | Configuration de l'image | Manifeste | Identifiant (liste de manifestes) |
|---|---|---|---|
| #66 | 1b23d44b | 264c8ad9 | a8b5bd4a |
| #67 | 1b23d44b | 264c8ad9 | 1e785b2c |
| #68 | 1b23d44b | 264c8ad9 | ec07cfcb |

**Cause** : BuildKit ajoute à chaque construction une attestation de provenance horodatée. L'identifiant d'image change donc même quand toutes les couches viennent du cache (`#11 CACHED`). La condition « image identique » échouait à chaque déploiement.

Une comparaison après coup n'est pas possible non plus. Avec le stockage containerd, l'ancienne image n'est plus consultable dès que l'étiquette est déplacée (vérifié localement : `No such image`).

**Correctif (PR #71)** : `BUILDX_NO_DEFAULT_ATTESTATIONS=1` pendant `compose build`. Essai local avec Compose 5.1 :
- 3 constructions, 1 identifiant ;
- sans la variable : 2 constructions, 2 identifiants.

Serveur : Compose 5.3.1, buildx 0.35.

Le premier déploiement après #71 recrée nginx une dernière fois, puisque l'ancien identifiant contient l'attestation. Les suivants le conservent s'il n'a pas changé.

## 2. Mesures en production

| Déploiement (commit) | Requêtes | Échecs | Fenêtre | Cause |
|---|---|---|---|---|
| #70 (`f3e30de`), 04/11 | 3 642 | 6 | 02:20:00.8 → 02:20:02.4 UTC | Recréation de nginx (journal : `Recreate 02:20:00.17`, `Started 02:20:01.39`). Ce déploiement utilisait encore l'ancien `deploy.yml` |
| Remplacement backend et frontend du même déploiement (02:19:38) | — | 0 | — | Relais actifs. Une requête a pris 3,3 s (latence médiane 148 ms, p99 267 ms) |
| #71 (`44f18d6`) | 561 (fenêtre 02:36-02:39) | 6 | 02:37:38.4 → 02:37:39.9 | Dernière recréation de nginx, attendue (ancien identifiant avec attestation) |
| #74 (`cb47bfd`) | 991 (02:57-03:01) | 4, plus 1 expiration | 02:59:20.0 → 02:59:20.5 ; expiration à 02:59:11 | `compose up` **n'a pas recréé** nginx (image identique) ; un redémarrage a suivi, nécessaire car `nginx/` changeait (`server_tokens off`) |
| #76 (`48a9377`) | 595 (03:14-03:19) | 0, plus 1 expiration | expiration à 03:16:48 | **« nginx inchangé : conservé »**, ni recréation ni redémarrage. Contrôle Celery : « 1 node online », planificateur avec 0 redémarrage |

**Expirations résiduelles** : 1 requête par déploiement (`/api/health/` à 02:59:11 et `/login` à 03:16:48, 8 s), au moment du remplacement du backend et du frontend.

Hypothèse : nginx garde en cache, pendant `valid=2s`, l'adresse de l'ancien conteneur, et une connexion vers une adresse disparue attend jusqu'au délai.

Piste à éprouver sur la mini-pile isolée **avant** toute modification de production : `proxy_connect_timeout` court et `proxy_next_upstream error timeout`. nginx ne rejoue pas les requêtes non idempotentes par défaut. Ce n'est pas fait.

Historique (03/11) : #64 72 échecs sur 39 s ; #66 41 échecs sur 17 s ; #67 6 échecs sur environ 1 s.

## 3. Coupure résiduelle connue

Quand `nginx/` change, le déploiement redémarre nginx (environ 1 s de refus de connexion). Un `nginx -s reload` ne suffit pas dans la conception actuelle. Le fichier est monté seul (`./nginx/nginx.prod.conf:/etc/nginx/nginx.conf`) et `git reset` le remplace par un nouveau fichier, si bien que le conteneur continue de voir l'ancien. Monter le dossier à la place permettrait un rechargement sans coupure. Ce changement touche le montage de production et doit être testé à part ; il n'est pas fait ici.

## 4. Contrôles ajoutés au déploiement (PR #76)

Après les migrations, le déploiement exige :
- un worker Celery qui répond au ping (12 essais de 5 s) ;
- un planificateur en marche, avec 0 redémarrage après 20 s.

Sinon, il échoue avec les journaux.

Origine : la panne Celery du 03/11 (kombu 5.7.0) a traversé deux déploiements sans être vue.

## 5. Écritures et sessions

- Les écritures ne sont jamais rejouées : pas de nouvel essai automatique des mutations côté client (`retry: false`), et aucun rejeu par le déploiement.
- Les sessions survivent au remplacement du backend : jetons JWT, aucune session serveur en mémoire.

## 6. Protection de la production

- Sauvegarde Restic avant chaque déploiement : étape inchangée, réussie à chaque fois.
- Retour arrière : les images `:previous` sont étiquetées avant la construction, et `restore_previous` est appelé en cas d'échec.
- Aucun nettoyage Docker global : seul `docker image prune -f`, qui ne supprime que les images sans étiquette, comme avant.
- Le bot OKX, Jitsi et plugNmeet n'ont pas été touchés par les déploiements FEBA.
