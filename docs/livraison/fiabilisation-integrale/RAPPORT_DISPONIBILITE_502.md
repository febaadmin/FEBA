> Mesures en production plus récentes : `RAPPORT_DEPLOIEMENT_SANS_INTERRUPTION.md`.

# Disponibilité

**Cause :** un seul conteneur backend, remplacé directement. Il met 15 à 20 s à servir : attente de PostgreSQL, contrôles, `migrate`, `collectstatic`. Relevé du 02/11 : 18 réponses 502 de 22:58:30 à 22:58:49. Le redémarrage de nginx s'y ajoutait.

| Mesure, mini-pile identique, 20 requêtes par seconde environ | Réponses | Échecs |
|---|---|---|
| Ancienne séquence | 538 | **260** 502 sur 16 s |
| Avec relais | 816 | **0** |

**Solution :** relais de la nouvelle image à côté de l'ancienne, ancienne remplacée seulement une fois le relais sain, résolveur nginx à 2 s, arrêt progressif, nginx redémarré seulement si sa configuration change. Solution la plus simple : pas de second backend permanent.

**Production :** déploiement de `cdcd637` : relais sain, 0 réponse 5xx au journal. Trafic concurrent non mesuré. Ce déploiement modifiait nginx et l'a donc redémarré.

**Effet de bord utile :** si la nouvelle version ne démarre pas, l'ancienne reste en service.

**Reprise des lectures :** GET sur 502 et 504 seulement, 4 fois au plus. Jamais d'écriture.

**Risque résiduel :** le relais lance les migrations pendant que l'ancienne version sert : une migration destructive doit se déployer en deux temps. Le frontend est remplacé directement, coupure non mesurée.
