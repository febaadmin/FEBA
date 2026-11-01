# FEBA - Examens et évaluations

Module distinct des notes (`backend/apps/evaluations`, API `/api/evaluations/`). Drapeau par académie : `evaluations_en_ligne`, désactivé par défaut (page **Modules pédagogiques** du superadministrateur).

## Quatre résultats conservés séparément

| Champ | Sens |
|---|---|
| `score_brut` | Points de la correction automatique à la remise |
| `score_corrige` | Après correction manuelle de toutes les questions |
| `score_valide` | Après validation par l'enseignant |
| `TransfertNote.valeur` | Note officielle créée dans le module de notes, sur 20 |

## Types de questions

QCM unique et multiple, vrai ou faux, réponse courte, numérique avec tolérance, texte à trous, associations, classement : correction automatique. Question ouverte et fichier déposé : correction manuelle, jamais automatique. Toute question peut porter une image, un document, un audio ou une vidéo. **Limite :** une formule mathématique s'écrit en texte ou dans une image, sans éditeur de formules.

## Points partiels

| Type | Règle |
|---|---|
| QCM multiple | (bonnes cochées - mauvaises cochées) / bonnes, jamais sous 0 |
| Trous, associations | Part des éléments justes |
| Classement | Part des éléments à la bonne place |
| Autres types objectifs | Tout ou rien |

## Calculs

- Points d'une question : arrondis au centième, à la demi-valeur supérieure.
- Pourcentage : score / total des points × 100.
- Note de l'épreuve : score / total × note maximale de l'épreuve.
- Note transférée : score validé / total × 20, car le module de notes travaille sur 20.
- Réussite : pourcentage supérieur ou égal au seuil.

## Tentatives

Politiques : meilleure, dernière, première, choisie par l'enseignant. Par défaut : dernière pour un examen officiel, meilleure sinon. Chaque tentative est conservée, avec son sujet figé, ses réponses et son journal.

## Passage

- Échéance calculée et vérifiée par le serveur. Après elle, une réponse est refusée.
- Remise automatique à l'échéance, par le serveur, y compris si l'élève a fermé la page (tâche `evaluations.cloturer_echues`, chaque minute).
- Sauvegarde à chaque changement, puis nouvel essai toutes les 20 secondes après une coupure.
- Reprise avec le même sujet et le même ordre.
- Corrigé, explications et critères jamais envoyés à l'élève pendant l'épreuve.
- Une version de question est immuable : modifier une question en crée une nouvelle.

## Intégrité

Journal : démarrage, reprise, remise, perte de connexion, sortie de fenêtre, autre session. Ces événements signalent, ils ne sanctionnent jamais. Aucune caméra, aucun micro, aucune reconnaissance faciale.

## Transfert vers les notes

Conditions : épreuve marquée « peut produire une note », trimestre renseigné, tentative validée retenue par la politique, enseignant affecté à la matière dans la classe, action explicite. La note est créée une seule fois (contrainte d'unicité par épreuve et par élève, et lien unique vers la note). Coefficient de matière, poids d'évaluation et calcul des moyennes restent ceux du module de notes. Après un transfert, la copie ne se corrige plus dans ce module.

**Si la note est supprimée dans le module de notes :** le lien subsiste et aucun nouveau transfert ne la recrée. La restauration passe par le module de notes.

## Compétences

Après validation d'une copie, si le suivi est actif, chaque compétence liée aux questions reçoit une proposition plafonnée sous le niveau le plus haut. Seul l'enseignant valide. Une note ne rend jamais une compétence « Acquis ».

## Résultats

Invisibles pour l'élève avant « Publier les résultats ». Les parents n'y accèdent que si l'académie a ouvert `suivi_familles`.

## Import CSV

Colonnes : `type, enonce, points, difficulte, choix (a|b|c), bonnes (a|b)`. Types : `qcm_unique`, `qcm_multiple`, `vrai_faux`, `courte`, `ouverte`. Tout ou rien. L'export neutralise les cellules interprétables par un tableur.
