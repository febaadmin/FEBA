# Inventaire des bugs et anomalies (02/11/2026)

| N° | Anomalie | Origine | Cause | État |
|---|---|---|---|---|
| 1 | QCM refusé, `test,test` sur une ligne | Vidéo 2 | Format par lignes avec `*`, peu compréhensible | Corrigé (PR #41, #42), navigateur local |
| 2 | Bouton « Supprimer » rouge pour publier ou transférer | Audit | `ConfirmDialog` figé sur la suppression | Corrigé (#42), navigateur local |
| 3 | Le chronomètre démarrait à l'ouverture de la page, sans consignes | Audit | Démarrage automatique | Corrigé (#42), navigateur local |
| 4 | Indicateurs vides sans explication | Vidéo 1 | Données réellement absentes, écran muet | Corrigé (#42), navigateur local |
| 5 | Remise automatique annulée par un refus tardif | Test | Refus dans la même transaction | Corrigé (#39), test automatique |
| 6 | Séance saisie deux fois comptée deux fois | Audit | Aucune unicité dans `Attendance` | Compté une fois dans le suivi (#42). Le module Présences reste sans contrainte |
| 7 | Bulletin affiché à jour après suppression d'une note | Audit | `pdf_outdated` ignorait les notes | Corrigé (#35) |
| 8 | Droit de noter non croisé classe et matière | Audit | Deux listes séparées | Code corrigé (#36). **147 lignes à confirmer par les administrateurs** |
| 9 | Pas de modification d'une question | Audit | Écran absent | Corrigé (#42) |
| 10 | Classement sans déplacement noté sans réponse | Test | Aucune réponse envoyée | Comportement conservé, consigne affichée (#42) |

## Connues, non corrigées

| N° | Anomalie | Raison |
|---|---|---|
| A | Devoirs, présences et classes virtuelles restent sur les listes de droits séparées | Touche les droits actuels : à décider |
| B | Pas de formule mathématique en éditeur | Dépendance à décider |
| C | Import Excel non pris en charge, CSV seulement | Dépendance à décider |
| D | Pas de remise ni de correction des devoirs par l'élève | Module existant sans cette fonction |
| E | Responsable d'un objectif ou d'un plan non choisi à l'écran | L'API le prend en charge, l'écran pas encore |
| F | Le progrès n'a pas de vue collective par classe | À développer |
| G | Pages superadministrateur `emails` et `payment-reminders` : erreur 400 sans académie active | Attendu côté serveur ; message d'écran non vérifié |

## Constats de données (aucune modification faite)

- Toute la production : **0 présence enregistrée**. L'assiduité restera vide tant que les présences ne sont pas saisies.
- Académie 2 : 5 élèves, 0 note ; l'élève 148 n'a pas de classe. Noms d'essai visibles (`eleve-FEBAFHA`, `Matière 1`).
- PDF archivés avec tiret cadratin : 226 reçus, 77 bulletins, 4 rapports. Conservés tels quels.
