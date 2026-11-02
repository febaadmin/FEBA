# Tests en production

## Réalisé, en lecture seule

| Contrôle | Résultat |
|---|---|
| Commit | `f25868c` |
| Conteneurs FEBA | 7 actifs |
| Migrations en attente | 0 |
| Tracebacks sur 20 min | 0 |
| Réponses 5xx sur 20 min | 4 réponses 502, au redémarrage |
| Fichiers servis | Contiennent les classes de la refonte et l'entrée de page corrigée |
| Page de connexion | Ouverte, 0 erreur JS |
| Notes, paiements | 935, 233 |
| Incidents | 4 résolus, 4 corrigés à valider, aucune nouvelle occurrence depuis le 24/10 |

## Non réalisé

Aucun parcours connecté : je n'ai pas de compte de test en production, et je n'en crée pas. **Le parcours élève réel, explicitement demandé, n'est donc pas validé.**

## Scénarios à exécuter

**Parcours élève**
1. Avec un compte élève de test : Mes épreuves, ouvrir, répondre, recharger, remettre.
2. Enseignant : corriger, publier.
3. Élève puis parent : consulter le résultat.
4. Sans le produit « note » sur une épreuve de test, vérifier l'absence de transfert.

**Flash**
1. Sur téléphone, ouvrir et fermer le menu 5 fois.
2. Sur ordinateur, changer de page 10 fois, ouvrir une fenêtre.

**Incidents**

| Incident | Qui | Scénario |
|---|---|---|
| `ERR-A036A8` | Enseignant de la note 476 | Ouvrir la note, tenter de la modifier selon ses droits, observer le message |
| `ERR-FC6DC7` | Enseignant de la note 192 | Idem |
| `ERR-4744E2` | Enseignant de la note 133 | Idem |
| `ERR-5D12BE` | Compte concerné par la messagerie | Ouvrir Nouveau message, choisir un destinataire, envoyer |
