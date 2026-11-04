# Phase 5 : glossaire par profil, gestion financière, graphique des paiements, centre d'analyse

Date : 04/11/2026. Dépôt `febaadmin/FEBA`. Production `globalfeba.com`.

Légende des statuts :
- **I** implémenté ;
- **TA** testé automatiquement ;
- **TL** testé localement (navigateur, base jetable) ;
- **D** déployé ;
- **VP** vérifié en production ;
- **HV** en attente de validation humaine ;
- **ND** non fait, avec justification.

FEBA n'est pas « finalisé à 100 % » : les limites sont listées au § F.

## A. Glossaire de l'aide par profil (PR #87, fusionnée `693bcde`)

- **Architecture** : `frontend/src/aide/glossaire.js`.
  - Un terme = une entrée, avec une définition par profil (`*`, superadmin, admin, enseignant, parent, élève).
  - `null` masque le terme pour ce profil.
  - Un terme peut dépendre d'un module.
  - Pas de doublon : une seule entrée par terme.
- **Termes visibles** : super administrateur 37, administrateur 34, enseignant 23, parent 24, élève 20.
- **Exemple** : « Académie » n'apparaît plus pour un élève ou un parent.
- **Tests** : 10 tests unitaires, plus le contrôle E2E « glossaire adapté au profil ».
- **Statut** : I, TA, TL, D, VP (présent dans le frontend déployé).

## B. Gestion financière

Conception et audit : `CONCEPTION_FINANCES.md`. On fait évoluer l'existant, sans second système.

| Fonction | Où | Statut |
|---|---|---|
| Écran « Tarifs et échéances » (grille niveaux × natures, tarifs, historique) | PR #88 (`3dc4e3a`) | I, TA, TL, D, VP (présence ; aucune saisie en production) |
| Nouvelles natures : réinscription, dossier, examen, fournitures, activités | migration `0017` (choix seulement) | I, TA |
| Historique des tarifs : qui, quand, ancien et nouveau montant, champs, motif | `FeeScheduleChange` | I, TA, TL |
| Motif obligatoire pour changer le montant d'un tarif déjà payé ; suppression refusée (409) si le tarif est utilisé | `reminder_views.py` | I, TA |
| Tarifs liés à une année, jamais rétroactifs ; réduction, bourse, exonération ; échéances (montant, date) | existant (`FeeSchedule`, `FeeInstallment`, `StudentFeeArrangement`) | inchangé, TA |
| Exonération exclue de l'attendu (corrige aussi le graphique) | `DueItem.net` | I, TA |
| Situation financière par élève, classe, niveau, académie ; retard ; taux de recouvrement ; paiements hors échéancier | PR #92 (remplace #89), fusionnée | I, TA, TL |
| Vue parent : situation de ses enfants seulement | PR #92 | I, TA, TL |
| Imputation des paiements (partiels, trop-perçus, remboursements, annulations, sans double imputation) | calculée par `compute_dues`, sans table | I (existant), TA |
| Majoration individuelle | — | **ND** : non demandée par une donnée existante ; une réduction négative serait ambiguë. À trancher par l'administration. |
| Catégories de frais entièrement libres (table) | — | **ND** : il faudrait migrer les 240 paiements réels. On utilise à la place les natures étendues et le libellé libre du tarif (voir conception). |

**Données de production** : aucune valeur de tarif n'a été créée, ni par du code ni par une migration. Les tarifs d'essai n'existent que dans les tests et la base E2E jetable, où l'E2E les crée puis les supprime.

## C. Graphique des paiements (PR #93, remplace #90)

- **Filtres combinables**, appliqués de la même façon aux paiements, aux transactions carte et aux échéances :
  - structure : année, cycle, niveau, classe, élève, avec des choix dépendants ;
  - financiers : nature, mode, statut (confirmé, annulé, remboursé), statut d'échéance, solde de l'élève, tranches de montant.
- **Périodes** : 7 jours, 30 jours, 3, 6 et 12 mois, année scolaire, année civile, période personnalisée.
- **Comparaison** avec la période précédente : les mêmes mois un cran plus tôt, ou la même durée juste avant. La variation n'est pas calculée quand la base est nulle.
- **Détail** : un clic sur une barre ouvre la liste de ses paiements ; « Voir les paiements » ouvre celle de toute la période ; export CSV.
- **Affichage des filtres** : puces des filtres actifs, réinitialisation, état vide propre aux filtres, définitions de chaque indicateur.
- **Garanties** :
  - devises jamais mélangées ;
  - « Non calculable » plutôt que 0 quand aucun tarif n'existe ;
  - valeur de filtre inconnue refusée (400) ;
  - filtres de structure exigeant une académie.
- **Tests** :
  - 11 tests backend : totaux filtrés comparés à des requêtes indépendantes, statut d'échéance, solde, comparaison, détail égal à la barre, validation, droits, CSV, isolation entre académies ;
  - 4 tests frontend ;
  - E2E `tableau` 26/26, dont « somme des modes = total encaissé » et « détail filtré = indicateur filtré », avec un clic sur une vraie barre.
- **Statut** : I, TA, TL.

## D. Centre d'analyse (PR #91)

**Couche commune** `apps/analytics` (lecture seule, sans migration) :
- un même contexte de filtres pour tous les indicateurs : académie, année, période, cycle, niveau, classe, matière, enseignant, élève, genre ;
- un même périmètre par profil, appliqué par le serveur.

| Module | Contenu | Statut |
|---|---|---|
| Effectifs | Inscriptions de l'année, genre, statut, remplissage. Contrôle des élèves actifs sans inscription (signalés, pas comptés). | I, TA, TL |
| Résultats | Moyennes selon les règles du bulletin, barème du niveau (« mixte » signalé), médiane, écart-type, répartition, taux de réussite (seuil réglable), niveaux de maîtrise (barème de l'académie), progression par période | I, TA, TL |
| Meilleurs résultats et élèves à accompagner | Formulation neutre. Seulement pour une classe ou un niveau, et seulement pour les élèves ayant au moins N notes (3 par défaut). Les élèves écartés sont comptés. | I, TA |
| Matières | Moyenne, dispersion, réussite, nombre de notes | I, TA, TL |
| Enseignants | Avertissement explicite (« aucune conclusion sur un enseignant »), tri par nom et non par résultat ; un enseignant ne voit que ses lignes | I, TA, TL |
| Présences | Taux par classe et par mois ; élèves à suivre ; jours sans appel non comptés | I, TA, TL |
| Vue personnelle | Parent (ses enfants), élève (lui-même) : moyennes par période et par matière, présences, sans aucune comparaison | I, TA, TL |
| Présentation FR / EN / bilingue | Ne change que les libellés ; aucune nouvelle requête (testé) | I, TA, TL |
| Examens, vie scolaire, ressources | — | **ND** : pas de données fiables exploitables à ce jour. Aucun indicateur fictif. |

**Droits testés** (backend et E2E) :
- élève et parent : 403 sur les analyses d'établissement, 404 sur un autre élève ;
- enseignant : 403 sur la classe d'un autre, sur un autre enseignant et sur les finances ;
- administrateur d'une autre académie : 404 ;
- super administrateur en « Toutes les Académies » : 400 explicite.

**Performance** : agrégation en base. Un test vérifie que le nombre de requêtes reste constant quand le nombre d'élèves augmente.

**Tests** : 10 tests backend, 5 tests frontend, E2E `analyses` 31/31 (5 profils).

## E. GitHub, déploiement et production

| PR | Objet | Statut |
|---|---|---|
| #87 | Glossaire par profil | fusionnée (`693bcde`), déployée avec succès |
| #88 | Tarifs et échéances, natures, historique | fusionnée (`3dc4e3a`), déployée, vérifiée en production (ci-dessous) |
| #89 | Situation financière | fermée automatiquement à la suppression de sa branche de base ; remplacée par #92 |
| #90 | Graphique : filtres | remplacée par #93, même contenu |
| #91 | Centre d'analyse | ouverte, basée sur `main` |
| #92 | Situation financière | fusionnée par commit de fusion (`1bca3eb`) |
| #93 | Graphique : filtres | fusionnée par commit de fusion (`f5b0ef6`) |

**Vérifié en production sur `3dc4e3a`, en lecture seule (04/11)** :
- migration `0017_historique_tarifs_natures` appliquée ;
- conteneurs backend, Celery et planificateur sains, redémarrés par le déploiement ; PostgreSQL et Redis non touchés ;
- **0 tarif** et 0 entrée d'historique : aucune valeur créée ;
- 242 paiements non supprimés, aucun modifié ;
- site 200 ; historique des tarifs refusé sans connexion (401) ;
- le menu « Tarifs et échéances », l'écran Tarifs et le glossaire sont présents dans le frontend déployé.

Déploiements de `1bca3eb`, `f5b0ef6` et #91 : à vérifier de la même façon (§ F).

## F. État final et limites

À compléter après déploiement et vérification en production.

**Limites connues** :
- la classe d'une note ou d'un paiement analysé est celle de l'inscription annuelle, à défaut la classe actuelle de l'élève ;
- le graphique ne prend que la classe actuelle ;
- les tarifs restent à saisir par l'administration : tant qu'ils manquent, l'attendu et le reste à payer restent « Non calculables » ;
- une relecture humaine des écrans et des textes d'aide, profil par profil, reste à faire (HV).
