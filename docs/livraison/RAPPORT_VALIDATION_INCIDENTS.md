# Validation des incidents

Statuts réels en base : **4 résolus, 4 corrigés à valider, 0 nouvelle occurrence depuis les correctifs.** Aucun incident supprimé.

| Incident | Cause | Reproduction | Correctif | Parcours réel | Statut |
|---|---|---|---|---|---|
| `ERR-291699` (note 936) | Justification reçue sous forme d'objet | 10 échecs sur 19 sur l'ancien code, 19 réussis après | PR #28, #34 | Suppression réelle du compte concerné | Résolu |
| `ERR-FF13EF` (note 934) | Idem | Idem | Idem | Idem | Résolu |
| `ERR-CBAA57` (note 931) | Idem | Idem | Idem | Idem | Résolu |
| `ERR-72B72D` (note 742) | Idem | Idem | Idem | Idem | Résolu |
| `ERR-A036A8` (note 476) | Idem | Idem | Idem | Manque : parcours sur iPhone en production | À valider |
| `ERR-FC6DC7` (note 192) | Idem | Idem | Idem, plus signalement du bulletin (#35) | Manque : parcours du compte concerné | À valider |
| `ERR-4744E2` (note 133) | Idem | Idem | Idem | Manque : parcours du compte concerné | À valider |
| `ERR-5D12BE` (messagerie) | Compte enseignant sans profil | Test reproduit | PR #28, #34 | Requête serveur 200 ; manque l'ouverture par ce compte | À valider |

Le bien-fondé pédagogique des dix suppressions reste à confirmer par l'établissement. Je ne crée pas de compte en production : scénarios dans `SCENARIOS-VALIDATION-HUMAINE.md`, livré à part.
