# Validation humaine

## 1. Connexion, 2 minutes
1. Déconnectez-vous, rechargez la page de connexion.
2. Connectez-vous une fois, avec votre gestionnaire de mots de passe.
3. Attendu : tableau de bord, sans message d'erreur.

## 2. Décisions

| Sujet | Faits | Décision |
|---|---|---|
| Élève 109, compte 208 | Rôle « parent » sur un compte d'élève | Corriger le rôle ? |
| Compte 191 | Superadmin avec profil parent, élèves 99 et 100 | Normal, ou compte séparé ? |
| 4 superadmins | Comptes 1, 180, 191, 278, tous actifs. Dernière connexion inconnue avant ce correctif | Tous légitimes ? |
| Académie 2 | 5 élèves, 0 parent, accès familles activé | Créer les parents, ou couper l'option ? |
| 10 notes supprimées | Priorité : 931, 741 | Restaurer ou confirmer |
| 147 affectations | Relevé | Confirmer |
| PDF stockés | Tirets longs | Garder ou régénérer |
| Limite par compte | Peut bloquer un utilisateur | Accord ? |

## 3. Incidents

4 résolus, 4 corrigés à valider : `ERR-A036A8`, `ERR-FC6DC7`, `ERR-4744E2`, `ERR-5D12BE`. Aucune nouvelle occurrence depuis le 24/10. Scénarios : `../../audit-securite-integral/GUIDE_VALIDATION_HUMAINE.md`.

## 4. Restauration
En root : `bash scripts/test_restauration_isolee.sh`. Jamais exécuté.
