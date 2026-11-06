# Situation financière : vue globale, par classe, par niveau, par élève

État : **développé et testé localement** (API, interface, navigateur réel à quatre tailles d'écran).

## 1. Sources de vérité et règles de calcul

Tout provient de `compute_dues`, puis est agrégé dans `apps/payments/situation.py`.

| Indicateur | Définition | Inclus / exclus |
|---|---|---|
| Frais théoriques | somme des échéances applicables (standard ou personnelles) avant toute réduction | tarifs actifs avec échéances ; abonnements seulement pour les abonnés |
| Exonérations | part exonérée | règles d'exonération et exonérations historiques |
| Remises | part remisée, après exonération | règles de remise et réductions historiques, selon les règles de cumul |
| Net attendu | théorique − exonérations − remises (≥ 0) | |
| Encaissé | part des paiements imputée sur les échéances | paiements **confirmés**, non supprimés, **nets des remboursements** ; exclus : annulés, supprimés, en attente (carte) |
| Total encaissé | tous les paiements confirmés nets de la sélection | y compris hors échéancier (nature sans tarif, trop-perçu) |
| Reste à payer | net − encaissé, sur toutes les échéances de la sélection | |
| En retard | reste des échéances dont la date est passée (date locale de l'académie) | |
| Taux de recouvrement | encaissé ÷ net attendu × 100 | « Non calculable » si le net est nul |
| Taux sur échéances passées | encaissé sur échéances passées ÷ net de ces échéances × 100 | ancien « taux de recouvrement », conservé sous ce nom |
| Élèves soldés, partiels, sans paiement, exonérés | statut de chaque élève de la sélection | |

**Distinctions affichées**
- **Zéro réel** : 0 FCFA.
- **Donnée non calculable** : aucun tarif avec échéances. Le bandeau explique que ce n'est pas un montant nul.
- **Donnée absente** : un tiret.
- **Erreur** : message d'erreur explicite.
- Sans tarif, le **total encaissé** et le graphique des encaissements restent affichés, car ce sont des chiffres réels. Défaut corrigé : la première version affichait « 0 FCFA » dans ce cas, alors que la production compte 240 paiements confirmés.

## 2. Vues

- **Par classe** : classe, niveau, élèves, à jour, en retard, théorique, remises et exonérations, net, encaissé, reste, retard, recouvrement. Cliquer sur une ligne ouvre la vue « Par élève » filtrée sur la classe.
- **Par niveau** : mêmes indicateurs, et un clic mène aux élèves du niveau.
- **Par élève** (nouvelle) :
  - colonnes : matricule, nom, classe, niveau, théorique, remises, exonérations, net, payé, reste, prochaine échéance, retard en jours, statut ;
  - tri par colonne (accessible : `aria-sort`), pagination côté serveur (50 par page).
- **Fiche financière d'un élève** :
  - tarifs appliqués ;
  - remises et exonérations retenues ou **écartées avec leur raison** ;
  - échéances standard ou personnelles (prévu, exonéré, remise, net, payé, reste, statut, jours de retard) ;
  - paiements, avec reçu disponible et remboursement ;
  - historique des décisions (personnel uniquement) ;
  - phrase de calcul : « Frais théoriques − exonérations − remises = net dû ; payé ; reste (dont en retard) ».
- **Groupement par année** : le regroupement par classe ou par niveau utilise la classe **de l'année de l'échéance** (inscription), plus la classe actuelle. Le même défaut, présent dans le tableau de bord des paiements, y a aussi été corrigé.

## 3. Filtres communs

Les filtres disponibles sont : année scolaire, cycle, niveau, classe, nature de frais, statut (soldé, partiel, aucun, exonéré, en retard, à jour), période des échéances, recherche (nom, prénom, matricule, classe, niveau).
- Ils s'appliquent **ensemble** aux KPI, aux tableaux, aux graphiques et à l'export.
- La somme des classes égale le total de l'académie, et c'est testé.
- Les choix sont dépendants : une classe est proposée selon le niveau choisi.

## 4. Graphiques (recharts, palette FEBA)

- **Répartition du net attendu** (encaissé / à échoir / en retard) : un clic filtre la vue par élève.
- **Statut de paiement des élèves** : un clic filtre par statut.
- **Comparaison par classe ou par niveau** (net, encaissé, reste) : un clic filtre la classe ou le niveau.
- **Taux de recouvrement** par classe ou niveau.
- **Encaissements par mois**, à la date de paiement.
- **Remises et exonérations accordées** par catégorie.

Règles communes : légende au texte neutre, infobulles, état vide expliqué, animations coupées si `prefers-reduced-motion`.

## 5. Explications

Chaque KPI porte un bouton « i » accessible (survol, focus, toucher, Échap) qui dit ce qu'il mesure, comment il est calculé et ce qu'il inclut ou exclut. La date de référence est indiquée sur les graphiques.

## 6. Export et permissions

- **Export CSV** (`/api/payments/situation/export/`) : mêmes filtres que l'écran, une ligne par élève, cellules protégées contre l'injection de formules, BOM UTF-8. Il est réservé au personnel.
- **Permissions** :
  - situation et export : administrateur de l'académie et super administrateur ;
  - fiche d'un élève : personnel de son académie, ou parent de l'élève, **sans historique interne ni justification** ;
  - enseignant et élève : 403 ;
  - autre académie : 404.

## 7. Bilinguisme

Les textes visibles sont en français et en anglais : test de couverture, plus les textes passés par variable, ajoutés explicitement (158 entrées).
