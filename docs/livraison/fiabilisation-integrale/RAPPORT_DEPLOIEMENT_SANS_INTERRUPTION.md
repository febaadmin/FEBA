# Déploiement sans interruption

## Mini-pile identique, même résolveur nginx, charge continue

| Scénario | Résultat |
|---|---|
| Ancien remplacement direct du backend | 260 réponses 502 sur 16 s |
| Relais (PR #60) | 0 échec sur 816 requêtes |
| Recréation de nginx avec `service_healthy` | 243 échecs sur 19 s |
| Relais + nginx recréé avec `service_started` | 3 échecs en 0,1 s, sur 817 requêtes |

## Production : sonde en lecture seule pendant 3 déploiements réels

La sonde envoie des GET sur `/api/health/` et `/login` toutes les 250 ms. Aucun compte, aucune écriture.

| Déploiement | Séquence | Requêtes | Échecs | Fenêtre | Cause |
|---|---|---|---|---|---|
| #64, 09:26-09:43 | Relais backend, `up -d` global | 2 543 | 72 | 39 s | nginx attendait le nouveau backend sain (`service_healthy`) |
| #66, 10:11-10:25 | Idem avec `service_started` | 2 080 | 41 | 17 s | Frontend sans relais, et nginx arrêté pendant l'arrêt du backend |
| #67, 10:48-11:10 | Relais backend et frontend, nginx seul et en dernier | 3 146 | **6** | **1 s** | Recréation inutile de nginx |
| Livraison | Idem, nginx conservé s'il n'a pas changé | Voir le compte rendu | | | |

**Latence hors bascule :** p50 environ 150 ms, p95 environ 158 ms.

Écritures : jamais rejouées. Lectures : rejouées sur 502 et 504. Sessions : jetons sans état, conservées.

**Non mesuré :** écriture en cours pendant la bascule, notifications pendant la bascule.

**Limites :**
- Une modification de nginx coupe encore environ 1 s.
- Une migration destructive doit se déployer en deux temps.

**Ancien journal :** 22 réponses 5xx relevées dans le conteneur nginx remplacé n'ont pas pu être analysées : son journal a disparu avec lui.
