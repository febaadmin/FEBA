# Phase 6 : validation fonctionnelle

## Résultats des suites

| Suite | Résultat | Environnement |
|---|---|---|
| Backend (Django, PostgreSQL) | **2138 tests OK** (7 ignorés, prévus) | local et CI |
| Frontend (vitest) | **573 tests OK** | local et CI |
| E2E Chrome, toutes les suites, sur `main` (`d3b8b9b`) | **330 contrôles, 0 échec** | local, **CSP de production appliquée à chaque page** |
| CI GitHub Actions | 12/12 contrôles verts sur #95, #96, #97 | CI |

## Matrice des profils (E2E et API)

| Contrôle | Superadmin | Admin | Enseignant | Parent | Élève |
|---|---|---|---|---|---|
| Toutes les pages des menus (pages tirées des menus réels), 1366 et 390 px : aucune erreur JS, 5xx ou violation CSP, aucun débordement, **le document ne défile pas** | ✓ | ✓ | ✓ | ✓ | ✓ |
| Aperçu du bulletin dessiné (pages et texte), actualisation, PDF officiel | ✓ (académie choisie ; en « Toutes », demande explicite) | ✓ | — | — | — |
| Centre d'analyse | ✓ (une académie à la fois, sinon 400 explicite) | ✓ parcours complet | ✓ ses classes ; 403 ailleurs ; aucune finance | 403 ; vue personnelle de ses enfants ; autre élève 404 | 403 ; vue personnelle ; autre élève 404 |
| Situation financière | ✓ | ✓ | 403 | ses enfants ; autre famille 404 | 403 |
| Graphique des paiements (filtres, détail, export, explication des tarifs) | ✓ | 403 | — | — | — |
| Présentation FR / EN / bilingue | ✓ | ✓ | ✓ | ✓ | ✓ |

## Matrice des académies

| Académie | Constats et validations |
|---|---|
| Faith & Excellence Bilingual Academy (XOF, 79 élèves actifs) | Production : colonne « Classe » remplie pour 76 élèves sur 79 (les 3 autres n'ont aucune classe). 0 tarif : explication affichée. Intégrité : aucune incohérence entre académies. |
| FEBA French Heritage Academy (USD, 5 élèves actifs) | Production : classe affichée pour 5 sur 5. 0 tarif : explication affichée. Devises jamais mélangées (tests). |
| Académies de test (tests backend) | Isolation : listes, analyses, situation, détail des paiements (404 ou liste vide). |

## Parcours de bout en bout

| Parcours | Couverture |
|---|---|
| **Élève** : création → inscription avec classe → liste → changement de classe → réinscription | Tests backend (`test_classe_eleves`). E2E : formulaires, navigation. |
| **Financier** : tarif → échéances → paiements partiels → reste à payer → situation → graphique | E2E `tarifs`, `situation`, `tableau` (sommes comparées à l'API). Tests de calcul : partiel, total, remboursement carte, exonération, échéance passée et future. |
| **Bulletin** : notes → moyennes → aperçu PDF → commentaire → actualisation → PDF officiel | E2E `apercu_pdf`. Tests backend des bulletins (121). |
| **Analytique** : année → classe → matière → enseignant → KPI → graphiques → détail | E2E `analyses` : KPI de l'écran égaux à l'API pour la sélection exacte. |

## Vérifications en production (lecture seule)

Sur `e7ff2d4` :
- colonne « Classe » corrigée (76/79, 5/5), calculée avec le sérialiseur déployé ;
- CSP inchangée ;
- aperçu PDF et message des tarifs présents dans le frontend déployé ;
- services sains ;
- 0 erreur 500.

**Sur `d3b8b9b`** : aucune migration en attente ; services sains ; Celery répond ; routes d'analyse déployées (401 sans connexion) ; 0 erreur 500 ; la simulation de rattachement compte 15 notes et 3 paiements, sans rien écrire.

## Non testé, et pourquoi

- **Écrans connectés en production** : aucun compte de test ni mot de passe disponible. Ces écrans sont validés en local et en CI.
- **Restauration de la sauvegarde FEBA** : demande root.
- **Navigateurs** : Chrome seulement. Safari et Firefox ne sont pas installés dans l'environnement de test.
- **Évolution par période et présence sur les données réelles** : impossible, une seule période notée et aucun appel en production. Les écrans l'expliquent.
