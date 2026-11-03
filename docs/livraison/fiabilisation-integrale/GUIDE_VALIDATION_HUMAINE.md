# Validation humaine

## À vérifier, 5 minutes
1. **Connexion :** une fois, avec votre gestionnaire de mots de passe.
2. **Salle virtuelle :** ouvrir une salle. La CSP étant désormais appliquée, signalez toute page blanche.
3. **Double clic :** enregistrer un élément de test.

## Décisions

| Sujet | Faits | Décision |
|---|---|---|
| Élève 109, compte 208 | Rôle « parent » sur un compte d'élève | Corriger ? |
| Compte 191 | Superadmin, profil parent, élèves 99 et 100 | Normal ? |
| Superadmins 1, 180, 191, 278 | Tous actifs | Légitimes ? |
| Académie 2 | 5 élèves, 0 parent, accès familles activé | Créer les parents ou couper |
| 10 notes supprimées | Priorité : 931, 741 | Restaurer ou confirmer |
| 147 affectations | Relevé | Confirmer |
| PDF stockés | Tirets longs | Garder ou régénérer |
| Limite par compte | Peut bloquer un utilisateur | Accord ? |
| Comptes de test en production | Nécessaires à la recette | Créer |

## Incidents

`ERR-A036A8`, `ERR-FC6DC7`, `ERR-4744E2`, `ERR-5D12BE` : à rejouer par les comptes concernés. Scénarios : `../../audit-securite-integral/GUIDE_VALIDATION_HUMAINE.md`.

## Restauration Restic
En root : `bash scripts/test_restauration_isolee.sh`.
