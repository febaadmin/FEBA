# Phase 6 : audit global et corrections

Date : 05/11/2026. Dépôt `febaadmin/FEBA`. Production `globalfeba.com`.

Légende des statuts :
- **CV** corrigé et vérifié ;
- **CNP** corrigé, non vérifié en production ;
- **BH** bloqué par une intervention humaine ;
- **NR** non reproductible ;
- **NC** non corrigé ;
- **AF** amélioration facultative.

## 1. Périmètre audité

| Domaine | Ce qui a été examiné |
|---|---|
| Frontend | React, Vite, Tailwind, React Query, Recharts, pdf.js. Layouts des 5 profils, composants partagés, i18n (tests de couverture), aperçus PDF, défilement, tableaux, filtres. |
| Backend | Django et DRF : sérialiseurs des élèves, services d'inscription, statistiques de classe, graphique des paiements, centre d'analyse, droits et isolation (tests de balayage). |
| Base de données | Intégrité de production en lecture seule : 24 contrôles (académies, années, inscriptions, notes, paiements, liens parents, comptes, affectations, doublons). |
| Exploitation | Conteneurs, journaux du backend, de Celery et du planificateur (24 h), incidents, minuterie de sauvegarde, CSP nginx. |
| Tests | Backend sur PostgreSQL, frontend vitest, E2E Chrome avec la **CSP de production** appliquée à chaque page. |

## 2. Anomalies

| Réf. | Module | Constat | Cause racine | Gravité | Correction | Preuve | Statut |
|---|---|---|---|---|---|---|---|
| P6-A | Graphique des paiements | « Non calculable » sans explication | Aucun tarif en production (0 en base, vérifié). Rien ne l'expliquait. | Moyenne | Explication et lien vers « Tarifs et échéances » ; données partielles signalées (élèves ou académies sans tarif). Aucun tarif créé. | Tests backend et frontend | voir § E |
| P6-B | Tous les écrans | Espace blanc en bas du tableau de bord | Un élément `sr-only` (absolu) du graphique échappait au conteneur `<main>` : le document défilait de 425 px (mesuré). | Moyenne | `<main>` devient le repère de positionnement dans les 5 layouts | E2E : « le document ne défile pas » sur toutes les pages des 5 profils, 1366 et 390 px | voir § E |
| P6-C | Élèves | Colonne « Classe » vide (76 élèves) | Les inscriptions créées par les notes, paiements, absences et bulletins n'avaient pas de classe ; la liste lisait l'inscription. | Haute | Repli sur la classe de la même année ; synchronisation à la création et au changement de classe ; commande de complétion (simulation). | 8 tests | voir § E ; données : **BH** |
| P6-C2 | Bulletins (rangs, statistiques) | Une classe « mixte » perdait des élèves | Règle « inscrits avec classe, OU SINON classe actuelle » | Haute (latente) | Règle unique `eleves_de_la_classe` | Test de régression | voir § E |
| P6-D | Bulletins, boîte d'envoi | Aperçu « Ce contenu est bloqué » | CSP de production (`frame-src` sans `blob:`), reproduite dans Chrome | Haute | Aperçu dessiné par pdf.js (canvas), **CSP inchangée** | E2E sous CSP réelle : pages dessinées avec du texte, actualisation, PDF officiel | voir § E |
| P6-E | Centre d'analyse | Lecture difficile, tableaux, filtre enseignant peu clair | Conception de la phase 5 | Moyenne | Centre de pilotage visuel (§ 3) | 23 tests backend, 7 frontend, E2E 45 | voir § E |
| P6-F | E2E | Le bug D n'était détecté par aucun test | Le serveur de test n'envoyait aucune CSP ; `routes.json` manuel omettait les écrans de la phase 5 | Haute (qualité) | CSP de production injectée ; pages déduites des menus ; contrôle de défilement | 310 contrôles | CV (local et CI) |
| P6-G | Inscriptions | 15 notes et 3 paiements sans inscription alors que l'inscription existe | « Désinscrire » met les données en `SET_NULL` ; la réinscription ne les rattachait pas | Moyenne | Rattachement automatique à la création d'une inscription ; commande pour l'existant (simulation) | 2 tests | PR #97 ; données : **BH** |
| P6-H | E2E | « classe créée visible » échouait | Liste paginée et base de test qui s'enrichit | Faible | Recherche dans la liste, comme un utilisateur | E2E vert | CV |
| P6-I | Données | 5 paires de notes identiques (même élève, matière, valeur, enseignant ; saisies à 1–190 min d'écart) | Pas un double clic. Peut-être deux évaluations réelles. | — | Aucune suppression | Liste au § 4 | **BH** (vérification humaine) |
| P6-J | Comptes | Profil parent du superadmin 191 (2 liens) ; compte élève 209 sans fiche | Données historiques (décisions déjà ouvertes en phase 2) | — | Aucune modification | — | **BH** |
| P6-K | nginx | Requêtes par l'IP rejetées par Django (trace dans les journaux) | Robots qui sondent l'IP | Faible | Possible : bloc `default_server` qui ferme la connexion | — | AF |

## 3. Centre d'analyse (P6-E)

- **Vue d'ensemble** :
  - KPI : inscrits, notés, moyenne, réussite, objectif atteint / à accompagner, présence ;
  - graphiques de synthèse ;
  - **limites des données** expliquées : une seule période notée, aucun appel, statuts d'inscription tous « normal », élèves actifs sans inscription.
- **Graphiques** : chacun a un titre, la période, la population, l'unité, des infobulles, un état vide motivé et un tableau à la demande.
- **Filtres** :
  - sélection multiple : classes, matières, enseignants, types d'évaluation ;
  - dépendances entre filtres, puces des filtres actifs, réinitialisation ;
  - un seul jeu de filtres pour tous les onglets.
- **Enseignants** :
  - profils descriptifs et comparaison descriptive ;
  - avertissement permanent, tri par nom ;
  - enseignants sans note signalés ;
  - répartition présentée honnêtement : moyennes élève × matière.
- **Non disponible**, et dit comme tel :
  - statut de publication des notes : le champ n'existe pas ;
  - présence : aucun appel en production ;
  - évolution : une seule période notée ;
  - nouvelles inscriptions et réinscriptions : statuts indistincts.

## 4. Notes identiques à vérifier (P6-I)

Paires d'identifiants de notes (production) :
- 292 / 303 ;
- 223 / 225 ;
- 680 / 690 ;
- 927 / 978 ;
- 475 / 476.

Même élève, même matière, même période, même type, même valeur, même enseignant. Une personne de l'établissement doit dire s'il s'agit de deux évaluations ou d'une saisie en double. Rien n'a été supprimé.

## 5. Résultats des tests

Voir `RAPPORT_VALIDATION_FONCTIONNELLE.md`.

## 6. Risques restants

- Données à compléter, **sur autorisation** :
  - classes de 77 inscriptions (`completer_classes_inscriptions`) ;
  - lien d'inscription de 15 notes (`rattacher_donnees_inscriptions`).
  
  L'affichage est déjà correct sans ces opérations : le repli se fait sur la classe de la même année, et les notes comptent par élève et par année.
- Restauration de la sauvegarde FEBA : non éprouvée, faute d'accès root.
- Aucun test avec un compte réel en production : il n'y a ni compte de test ni mot de passe à utiliser.
