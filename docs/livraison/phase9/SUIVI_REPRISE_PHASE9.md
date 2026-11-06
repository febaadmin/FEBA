# Phase 9 — Point de reprise

Branche : `fix/phase9-communications` (depuis `main` à 28841d8).

## État de la phase 8 vérifié au démarrage (lecture seule)
- PR #102, #103, #104, #105, #106 : fusionnées. `main` = 28841d8 (#106).
- Déploiement 42127437245 (28841d8) : succès. Conteneurs `feba_*_prod` sains.
- Journaux backend sur 6 h : 0 erreur 5xx, 0 traceback.
- Synchronisation IMAP Hostinger (Celery, toutes les 3 min) : réussie, `{'nouveaux': 0, 'erreur': ''}`.
- Migration `boite_mail` en production : 0001 seule (0002 arrive avec cette phase).

## Résultats locaux
| Suite | Résultat |
|---|---|
| Backend complet (PostgreSQL) | 2227 tests OK (7 ignorés) |
| Frontend (Vitest) | 91 fichiers, 625 tests OK |
| Lint | 0 erreur |
| E2E complet (navigateur réel, 20 scénarios) | **438 contrôles, 0 échec** |

Échec intermittent noté : le scénario `messagerie` a échoué une fois sur trois passages (clic « corbeille » non trouvé dans les archives, l. 77). Il est passé ensuite seul et dans la suite complète. Cause non établie.

## À faire / bloquants
1. CI de la PR à surveiller.
2. **Fusion : autorisation explicite requise.**
3. Après déploiement : migration `boite_mail 0002`, journaux, vérifications en lecture seule (compteur, liste des réponses).
4. Aucun e-mail réel n'a été envoyé. Une réponse réelle à un message du site ne doit être faite qu'avec l'accord de FEBA, sur un destinataire autorisé.
5. Validation avec des comptes réels (5 profils) : à faire par FEBA.
