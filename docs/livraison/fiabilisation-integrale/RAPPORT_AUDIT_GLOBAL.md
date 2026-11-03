# Audit global

| Critère | État | Preuve ou manque |
|---|---|---|
| Inventaire du projet | Partiel | `INVENTAIRE_COMPLET_MODULES.md` : routes comptées, actions non toutes exercées |
| Anomalies découvertes | Corrigées ou documentées | `INVENTAIRE_BUGS_ANOMALIES.md` |
| Connexion | Local, déployé | `RAPPORT_AUTHENTIFICATION.md`. Attend votre essai réel |
| 502 de déploiement | Cause établie, solution validée | Banc : 260 échecs puis 0. Premier vrai déploiement : 0 réponse 5xx au journal, sans mesure de trafic concurrent |
| Anomalie des bulletins | **Expliquée** | `RAPPORT_INTEGRITE_DONNEES.md` |
| Vulnérabilités prioritaires | Partiel | `RAPPORT_SECURITE.md` |
| Permissions des 5 profils | Local, tests PostgreSQL | Pas de compte de test en production |
| Isolation sous PostgreSQL | Vérifiée | Campagne 2, 7, 19 académies |
| Parcours métier | Partiel | `MATRICE_TESTS_PAR_ROLE.md` |
| Non-régression | Vérifiée sur le périmètre listé | `MATRICE_NON_REGRESSION.md` |
| Sauvegardes et rollback | Partiel | Restauration logique réussie. **Restauration Restic non testée, root requis** |
| Archive | Voir le compte rendu de mission | Contrôlée et reconstruite |

**L'application n'est déclarée ni fonctionnelle ni sûre à 100 %.**
