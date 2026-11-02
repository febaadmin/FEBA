# Rapport : évaluations en ligne

## Cause du blocage constaté

L'épreuve de production « test » était publiée, sa classe et ses élèves corrects. Elle s'ouvre le 03/11/2026 à 08:01 UTC. L'écran affichait « Non ouverte » sans date, et l'enseignant ne pouvait pas l'avancer.

## Corrections

| Élément | État |
|---|---|
| Cartes élève : état, raison, date, enseignant, questions, tentatives, seuil | Fait |
| Ouverture anticipée, tant qu'aucun élève n'a commencé | Fait |
| Consignes avant le chronomètre | Fait |
| Page de résultat, corrigé après la fin si prévu | Fait |
| Envois de fichiers (dépôts, médias, imports) refusés à tort | Corrigé |
| Confirmation qui affichait « Supprimer » | Corrigé |

## Parcours exercé en navigateur local (comptes de démonstration)

Créer, 9 types de questions, publier, visible avec date, ouverture anticipée, consignes, démarrage, réponses, rechargement et reprise, coupure réseau, remise avec double clic, correction (8 points sur 9 automatiques, 1 manuel), publication, résultat 20/20 avec corrigé, parent de l'élève. Le dépôt de fichier a été exercé à part. Refus vérifiés : autre classe (liste et URL), autre parent, tentatives atteintes.

Cas vérifiés par tests automatiques seulement : épreuve expirée, autre académie, élève sans classe, requêtes simultanées partielles.
