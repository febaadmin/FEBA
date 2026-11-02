# Audit de FEBA (02/11/2026)

## Portée réelle

**Ce n'est pas une relecture ligne à ligne de tout le dépôt.**

| Contrôle | Portée | Résultat |
|---|---|---|
| Pages, navigateur local | 247 pages, 5 rôles, bureau et mobile | 0 erreur JS, 0 page vide, 0 débordement. 10 signaux expliqués |
| API en lecture, production | 147 routes, 15 comptes, FR et EN, le 01/11 | 0 réponse 5xx |
| Suite backend | CI PostgreSQL | 2185 réussis, 3 ignorés, 0 échec (PR #40) |
| Suite frontend | Vitest, ESLint, build | 428 réussis, 0 erreur |
| Journal nginx de production | 30 minutes après déploiement | 0 réponse 5xx |
| Présence de contrôle d'académie par ViewSet | Recherche dans `apps/*/views.py` | Présent, sauf incidents (réservé au superadmin) ; `messaging` et `notifications` limités à l'utilisateur |
| Revue approfondie | `suivi`, `evaluations`, droits des notes, incidents | Faite |
| Revue approfondie | Paiements, documents officiels, site public, emplois du temps | **Non refaite dans cette mission.** Audits antérieurs seulement |

## Fonctions par module

| Module | État |
|---|---|
| Authentification, utilisateurs, académies, élèves, parents, enseignants, inscriptions, classes, niveaux, matières | Pages ouvertes, tests automatiques verts ; pas de nouveau parcours réel |
| Notes, moyennes, bulletins | Tests verts ; suppression réelle observée en production |
| Présences | Écrans ouverts, **aucune donnée en production** |
| Devoirs | Sans remise par l'élève |
| Messagerie | Envoi et réception en local ; pas de parcours réel en production |
| Paiements, reçus, relances | Tests verts ; décisions en attente (paiements 45 et 47, grille des frais) |
| Salles virtuelles, plugNmeet | Service répond 200 ; recette réelle en attente |
| Suivi, examens, rapports, alertes | Voir les recettes |

## Services au dernier contrôle

`meet.globalfeba.com` 200 ; certificats valides jusqu'au 07/12/2026 (FEBA) et 27/01/2027 (meet) ; Jitsi et OKX présents et non touchés.
