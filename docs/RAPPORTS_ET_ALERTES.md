# Rapports et alertes pédagogiques

## Rapports (`/api/suivi/rapports/`)

Un rapport est distinct du module `monthly_reports` et des bulletins.

| État | Sens |
|---|---|
| Brouillon | Modifiable |
| Validé | Version figée, modifier le ramène en brouillon |
| Publié | Version figée, non modifiable, visible par les familles si l'académie l'a ouvert |

`donnees` est calculé depuis les données réelles et ne s'édite pas. `contenu` est rédigé par l'enseignant. Une donnée absente s'écrit « Non renseigné » ; rien n'est complété automatiquement. `nouvelle_version` reprend un rapport publié ; les familles gardent la dernière version publiée. La notification aux familles part seulement à la publication, et si `suivi_familles` est actif.

## Alertes (`/api/suivi/alertes/`)

Tâche quotidienne `suivi.detecter_alertes`, ou **Vérifier maintenant**. Le même signal n'est jamais créé deux fois (unicité élève, règle, clé).

| Règle | Déclenchement | Seuil par défaut | Catégorie |
|---|---|---|---|
| `baisse_resultats` | Baisse entre les 2 dernières évaluations du suivi | 10 points | À surveiller |
| `progression_positive` | Hausse entre ces mêmes évaluations | 10 points | Progression positive |
| `stagnation` | Compétence non acquise au même niveau, sur ses 2 dernières évaluations, avec au moins N évaluations | 3 | Attention |
| `absences` | Absences sur 30 jours | 3 | À surveiller |
| `difficultes` | Compétences au premier niveau | 3 | À surveiller |
| `objectif_atteint` | Objectif atteint | 1 | Objectif atteint |

Les seuils et l'activation sont réglables par l'administration. Ces valeurs sont des propositions à relire par la direction pédagogique. Une alerte reste un signal : aucune sanction, aucune décision automatique, aucun envoi aux familles.
