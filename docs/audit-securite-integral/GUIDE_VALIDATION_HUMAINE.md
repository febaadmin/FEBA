# Validation humaine

Rien ci-dessous n'a été fait à votre place.

## 1. Comptes de test en production
Créez un jeu par profil dans une classe de test. Parcours :
1. Enseignant : créer une épreuve, publier.
2. Élève : ouvrir, répondre, recharger, remettre.
3. Enseignant : corriger, publier.
4. Élève et parent : voir le résultat.

## 2. Sélecteur et flash
1. Ouvrez le sélecteur, cliquez à côté : il se ferme.
2. Ouvrez-le, cliquez dans le menu latéral : il se ferme.
3. Sur téléphone, ouvrez le menu 5 fois : aucun éclair.

## 3. Incidents encore à valider
| Incident | Qui | Geste |
|---|---|---|
| `ERR-A036A8` | Enseignant de la note 476 | Ouvrir, modifier selon ses droits, lire le message |
| `ERR-FC6DC7` | Enseignant de la note 192 | Idem |
| `ERR-4744E2` | Enseignant de la note 133 | Idem |
| `ERR-5D12BE` | Compte de la messagerie | Nouveau message, destinataire, envoyer |

## 4. Décisions
| Sujet | Faits | Décision attendue |
|---|---|---|
| Dix notes supprimées | 935 notes dont 10 supprimées. Désormais cachées aussi des tableaux de bord | Restaurer ou confirmer. Priorité : 931, 741 |
| 147 affectations | À confirmer | Décocher ce qui n'est pas enseigné |
| PDF stockés | 226 reçus, 77 bulletins, 4 rapports avec tirets longs, relevé antérieur | Garder ou régénérer |
| Académie 2 | 5 élèves, 0 compte parent, 0 lien, accès familles activé | Créer les parents, ou couper l'option |
| Limite par compte (V8) | Risque : blocage d'un utilisateur par un tiers | Accord ou non |
| 4 comptes superadmin | Nombre relevé | Confirmer qu'ils sont légitimes |

## 5. Test de restauration
En root, sur le serveur : `bash scripts/test_restauration_isolee.sh`. Il n'a jamais été exécuté.
