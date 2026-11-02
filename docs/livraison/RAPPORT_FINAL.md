# Rapport final de la refonte (02/11/2026)

**Mission non terminée.** Production : `bdc8bcf`, déployé avec succès. Aucun parcours d'écriture de ces modules n'a été exécuté par moi en production.

## Développé

Cartes d'épreuves pour l'élève, ouverture anticipée, résultat et corrigé, bibliothèque de compétences, évaluation d'une classe, tableau de bord, graphiques, objectifs en colonnes, frise, 4 nouvelles alertes.

## Corrigé

| Défaut | Cause |
|---|---|
| « Non ouverte » sans explication | Date d'ouverture jamais affichée |
| Liste de compétences vide et sans issue | Page peu accessible, aucun message |
| Dépôts de fichiers, médias et imports refusés | En-tête JSON sur les envois de fichiers |
| Échec CI n° 101 | Collision de référence de paiement, sans vérification |
| Commentaires internes visibles par les familles via l'API | Champ renvoyé tel quel |

## Niveaux de vérification

| Fonction | Auto | Navigateur local | Production |
|---|---|---|---|
| Parcours d'examen complet | Oui | Oui | Non |
| 9 types en un seul parcours ; dépôt de fichier à part | Oui | Oui | Non |
| Compétences, évaluation, historique | Oui | Oui | Non |
| Tableau de bord, graphiques, frise | Partiel | Oui | Lecture du calcul seulement, sur un élève |
| Objectifs par glisser-déposer | Statuts | Oui | Non |
| Parents et élèves, résultats | Oui | Oui | Non |
| Déploiement, migrations, santé | - | - | Oui |
| Notes, bulletins et paiements inchangés en nombre | - | - | Oui (935, 58, 233) |

## Non testé

Vrai téléphone et tablette ; glisser-déposer tactile ; glisser-déposer des questions à la souris ; audio et vidéo ; expiration de session pendant un examen ; charge ; transfert simultané sur PostgreSQL ; comptes réels. Le transfert vers les notes n'a pas été rejoué dans cette refonte : tests automatiques verts et parcours local précédent.

## Défauts et manques

Tableau de bord personnalisable, éditeur de formules, import Excel, rapports par matière, responsable à l'écran, référentiels globaux, réorganisation des widgets. Droits croisés limités aux notes et aux nouveaux modules.

## Actions humaines

Comptes de test en production et recette ; 4 incidents ; dix suppressions ; 147 affectations ; restauration isolée en root ; PDF archivés.
