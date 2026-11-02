# Architecture des référentiels et des compétences

`Referentiel` (académie, matière, niveau, classe, période, programme, actif) contient des `Competence` (domaine, sous-domaine, description, objectif, critères, niveau attendu, période, actif). Une `EvaluationCompetence` relie un élève, une compétence et un `NiveauMaitrise`, en ajout seul.

| Règle | Mise en œuvre |
|---|---|
| Pas de doublon | Nom unique par académie (référentiel), par référentiel (compétence), sans tenir compte des majuscules |
| Historique protégé | Suppression refusée s'il existe une évaluation ou une question liée ; archivage à la place |
| Réutilisation | `dupliquer` copie un référentiel et ses compétences actives, sans historique |
| Évaluation collective | `evaluations-competences/lot/`, tout ou rien, droits contrôlés par ligne |
| Lien avec les examens | Une question peut viser des compétences. Une épreuve validée propose un niveau, plafonné sous le plus haut, que l'enseignant valide |

**Limite :** pas de référentiel global à plusieurs académies. Chaque référentiel appartient à une académie.
