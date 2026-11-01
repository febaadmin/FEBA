# FEBA - Suivi pédagogique

Module distinct des notes et des bulletins (`backend/apps/suivi`, API `/api/suivi/`). Il a ses propres tables et n'écrit jamais dans `apps.grades`.

## Activation

Désactivé par défaut, par académie, dans `School.settings["features"]` :

| Drapeau | Effet |
|---|---|
| `suivi_pedagogique` | Ouvre le module au personnel de l'académie |
| `suivi_familles` | Ouvre la consultation aux élèves et aux parents. Décision de l'établissement |

## Provenance des données

| Origine | Contenu | Écriture par le suivi |
|---|---|---|
| `suivi_pedagogique` | Compétences, évaluations du suivi, observations, objectifs, plans | Oui |
| `notes_historiques` | Notes et présences lues depuis les modules existants | Jamais |

Une note n'est jamais convertie en évaluation du suivi. Elle s'affiche à part, avec sa période, son année et son origine.

## Règles de calcul

**Progression générale** : moyenne pondérée des composantes disponibles, avec les poids de `ParametresSuivi` (par défaut compétences 50, évaluations 30, objectifs 20). Une composante absente sort du calcul. Sans aucune composante, l'écran affiche « Données insuffisantes ».

| Composante | Calcul |
|---|---|
| Compétences | Moyenne de (rang du dernier niveau validé - 1) / (rang maximum - 1) × 100 |
| Évaluations | Moyenne des scores en pourcentage des évaluations du suivi |
| Objectifs | Objectifs atteints / (atteints + non atteints) × 100 |

Les notes officielles n'entrent pas dans ce calcul.

**Assiduité** : (présents + retards) / relevés × 100. Sans relevé, aucun taux : l'absence de relevé n'est pas une présence. Une séance annulée n'existe pas dans le module Présences, donc elle n'y compte pas.

**Participation** : moyenne des observations saisies par l'enseignant (1 à 4), affichée à partir de `min_observations` observations. Jamais déduite d'une caméra ou d'un micro.

**Tendance d'une compétence** : comparaison des deux derniers niveaux validés.

**Comparaison de périodes** : un écart n'est calculé que si les deux périodes ont une valeur. La moyenne des notes officielles exige `min_notes_comparaison` notes par période.

## Historique

- `EvaluationCompetence` est en ajout seul : ni modification ni suppression par l'API. Seule une proposition reçoit une décision (validée ou refusée), et la ligne reste.
- `ObjectifHistorique` conserve chaque changement de statut.

## Permissions

| Action | Superadmin | Admin | Enseignant | Élève | Parent |
|---|---|---|---|---|---|
| Voir un élève | Académie active | Son académie | Ses classes | Soi, si `suivi_familles` | Ses enfants, si `suivi_familles` |
| Évaluer, observer, objectifs, plans | Académie active | Son académie | Ses classes, matières affectées | Non | Non |
| Référentiels et compétences | Oui | Oui | Oui | Lecture | Lecture |
| Niveaux et poids | Oui | Oui | Non | Non | Non |

Les familles ne voient ni les propositions non validées, ni les observations, ni les plans non partagés.

## API

`eleves/`, `eleves/{id}/fiche/?du&au&subject`, `eleves/{id}/comparer/?a_du&a_au&b_du&b_au`, `referentiels/`, `competences/`, `niveaux/`, `evaluations-competences/` (`decider/`), `evaluations/`, `observations/`, `objectifs/`, `plans/`, `actions/`, `parametres/` (`modifier/`).
