# Registre des anomalies et corrections

Statut « Local » : corrigé et vérifié hors production. Statut « PR 50+ » : en attente de fusion à la date de ce document.

| # | Anomalie | Cause | Correction | Test | Statut |
|---|---|---|---|---|---|
| 1 | Deux entrées du menu surlignées | `NavLink` sans `end` sur `/suivi` | `end` et classes communes | Navigateur | Production (PR 49) |
| 2 | Copie affichant `c0` au lieu du choix | Valeur brute affichée | `lire_valeur`, `corrige_lisible` | `AnomaliesVideoTests` | Production (PR 48) |
| 3 | `20.00 / 20.00` | Format brut | `Number()` | Navigateur | Production (PR 48) |
| 4 | « Retenir » toujours proposé | Politique ignorée | Selon `politique=validee` | `AnomaliesVideoTests` | Production (PR 48) |
| 5 | Question impossible à supprimer | Action absente | Suppression si inutilisée | `AnomaliesVideoTests` | Production (PR 48) |
| 6 | Aperçu et PDF de résultats absents | Non développés | `apercu`, `resultats_pdf` | `AnomaliesVideoTests` | Production (PR 48) |
| 7 | Export des compétences absent | Non développé | `competences/exporter` | `ExportCompetencesTests` | Production (PR 48) |
| 8 | Dates d'épreuve hors fuseau de l'académie | Fuseau non transmis | `fuseau` dans la liste | Navigateur | Production (PR 48) |
| 9 | Liste de responsables vide | Mauvais champ | `user_id`, `full_name` | Navigateur | Production (PR 48) |
| 10 | Boutons secondaires pris pour du texte | Pas de style commun | Système de design | Navigateur | Production (PR 49) |
| 11 | Tableaux illisibles sur téléphone | Défilement horizontal | Lignes en cartes | Balayage 390 px | Production (PR 49) |
| 12 | Colonne Académie en double (Utilisateurs) | Colonne page et colonne `DataTable` | Colonne de page retirée | `DataTable.confirmation.test` | Production (PR 49) |
| 13 | Requêtes 400 pour le superadmin sans académie (e-mails, relances) | Appel sans académie | Message clair, pas d'appel | Balayage : 0 × 400 | Production (PR 49) |
| 14 | Confirmations natives du navigateur | `window.confirm` (5 endroits) | `ConfirmDialog` | `DataTable.confirmation.test` | Production (PR 49) |
| 15 | Tri inaccessible au clavier | `onClick` seul sur `th` | `tabIndex`, `aria-sort`, clavier | `DataTable.confirmation.test` | Production (PR 49) |
| 16 | **Fond des fenêtres ne couvrant plus l'écran. Régression que j'ai introduite en PR 49** | Animation d'entrée conservant un `transform` | Fenêtres rendues dans `body`, animation non persistante | `useFormulaire.test` | PR 50 |
| 17 | « Enregistrer » muet si un champ obligatoire est vide (35 fichiers) | Aucun retour de validation | `utils/useFormulaire.js` | `useFormulaire.test`, navigateur | PR 50 |
| 18 | Libellés non reliés aux champs (quasi tous les formulaires) | `label` sans `for` | `useLabelLinker` | `useLabelLinker.test`, sondage | PR 50 |
| 19 | Objectif non modifiable, non archivable, historique invisible | Non développé | Modification, archivage réversible, historique | `ObjectifEditionArchivageTests`, navigateur | PR 50 |
| 20 | Pas d'évolution par compétence | Non développé | `EvolutionCompetence` | Navigateur | PR 51 |
| 21 | Plan d'accompagnement non modifiable | Non développé | Même formulaire en modification | `test_plan_modifiable`, navigateur | PR 51 |

Anomalies de missions précédentes : voir `../INVENTAIRE_BUGS_ANOMALIES.md`.

| 22 | **Flash lumineux à la navigation (vidéo 14.52.33, images 163 à 165)** | framer-motion 11 annule l'animation avant d'écrire la valeur finale : une image à l'opacité initiale | framer-motion 12.43.0 | `sansFlash.test`, mesure : 6 chutes sur 6 ouvertures, puis 0 | Production (PR 52) |
| 23 | Page qui s'efface à l'entrée | Opacité de départ à 0 | Départ à 0,55 | `sansFlash.test` | Production (PR 52) |
| 24 | Attente clignotante | `animate-pulse` | `animate-attente`, amplitude réduite | `sansFlash.test` | Production (PR 52) |
| 25 | Échap exécutait `onClose` des fenêtres fermées | Écouteur toujours actif | Écoute seulement si ouverte | Navigateur | Production (PR 52) |
| 26 | Valeurs des cartes coupées (« 12.48/2 0 ») | `break-words` sur une colonne étroite | Taille et césure revues | Planches de photos | Production (PR 53) |
| 27 | Destinataire affiché « all » | Valeur technique | `libelleCible` | `destinataires.test` | Production (PR 53) |
| 28 | Dates coupées dans les tableaux | Colonne étroite | `whitespace-nowrap` pour les dates brutes | Planches de photos ; dates mises en forme par une colonne personnalisée non couvertes | Production (PR 53) |

## Encore ouvert

| Sujet | Gravité | Note |
|---|---|---|
| **A1. Échec isolé de la campagne d'isolation** | **Haute tant qu'elle n'est pas expliquée** | Run 41466038561, PostgreSQL : `T07Z/admin GET /api/bulletins/ contient l'étiquette de T14Z`. Cause inconnue. Le contrôle jumeau sur le même commit est passé, 6 répétitions locales sous SQLite et les CI suivantes aussi. La vue filtre par `student__school`. Hypothèse du suffixe aléatoire de fichier non démontrée. Le détecteur affiche désormais le texte en cause. **Aucune fuite n'est prouvée, aucune n'est exclue** |
| Coupure d'environ 5 s à chaque déploiement | Moyenne | 4 réponses 502 sur les compteurs de notifications le 02/11 à 16:12 UTC |
| Un libellé non relié dans « Nouveau message » | Faible | Bloc à plusieurs champs |
| Tableaux larges à défilement horizontal sur ordinateur | Faible | Élèves, Paiements, Utilisateurs |
| Dialogue de l'admin « Nouvel utilisateur » resté ouvert après 201 dans mon automate | À vérifier | Le code ferme la fenêtre après succès : probablement un artefact de l'automate, non confirmé à la main |
| Tirets longs dans les PDF déjà stockés | Décision | Non modifiés |
