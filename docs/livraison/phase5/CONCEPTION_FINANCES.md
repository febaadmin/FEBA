# Phase 5 : conception de la gestion financière

Date : 04/11/2026. Fondé sur l'audit du code (`apps/payments`) et des données de production, lues sans modification.

## 1. Ce qui existe déjà

| Besoin | Existant | Fichier |
|---|---|---|
| Grille tarifaire par académie, année, niveau et nature | `FeeSchedule` (montant en unité mineure, devise de l'académie, obligatoire ou par abonnement, actif). Résolution du plus précis au plus général : niveau, puis année, puis permanent. Contraintes d'unicité. | `fee_models.py` |
| Échéancier | `FeeInstallment` (libellé, date, montant, ordre). Mode « tranches » (somme = tarif, sinon anomalie bloquante) ou « récurrent » (chaque échéance est due). | `schedule_models.py` |
| Tarification individuelle | `StudentFeeArrangement` : abonnement (avec dates), exonération, réduction (montant). Motif, auteur et date conservés. | `schedule_models.py` |
| Dus, payés, restants | `compute_dues(academie, date)` calcule une ligne par élève, tarif et échéance : attendu, réduction, payé, restant, statut (à venir, en retard, réglé), jours de retard, anomalies. Aucune écriture. | `reminders.py` |
| Affectation des paiements | Dans `compute_dues`, de façon déterministe : 1) un paiement qui indique son mois est imputé sur l'échéance de ce mois ; 2) le reste est imputé dans l'ordre des échéances. Remboursements de carte déduits, paiements annulés ou supprimés ignorés, devise contrôlée. | `reminders.py` |
| Paiements | `Payment` (nature, montant, mode, date et heure, mois concerné, confirmé ou annulé, supprimé logique, historique `PaymentHistory`, reçu) | `models.py` |
| Carte | `PaymentTransaction` (statuts, remboursements plafonnés, webhooks idempotents) | `transaction_models.py` |
| Relances | Politique, exécutions et relances par échéance | `schedule_models.py`, `reminders.py` |
| Saisie des tarifs | Écran complet (tarifs, échéances, dispositions par élève)… **caché dans l'onglet « Échéanciers » de « Relances de paiement »** | `PaymentReminders.jsx` |

**Constat principal** : la gestion des tarifs existait, mais personne ne la trouvait. En production, aucun tarif n'est configuré dans les deux académies, d'où « Non calculable » sur le graphique.

## 2. Décisions

1. **Ne pas créer un second système.** Les modèles ci-dessus sont la base. On ajoute ce qui manque, sans dupliquer.
2. **Natures de frais** : `Payment.PAYMENT_TYPES` est partagé par les paiements, les tarifs, les relances et la carte.
   - On ajoute les natures demandées : réinscription, frais de dossier, examen, fournitures, activités. La liste de choix change, le schéma de la base non.
   - Le libellé libre de chaque tarif sert aux distinctions plus fines (par exemple « Frais d'examen BEPC »).
   - Une table de catégories entièrement libre obligerait à migrer la nature des 240 paiements réels vers une clé étrangère. C'est écarté pour cette phase et documenté comme évolution possible.
3. **Historique des tarifs** : nouveau modèle `FeeScheduleChange`, en ajout seul. Il conserve la création, la modification (champs, ancien et nouveau montant), la désactivation et la suppression, avec l'auteur, la date et le motif. Un changement de montant sur un tarif déjà utilisé par des paiements exige un motif.
4. **Années** : les tarifs restent rattachés à une année. `compute_dues` résout le tarif de l'année d'inscription de chaque élève. Un nouveau tarif ne modifie donc jamais les montants d'une année passée.
5. **Affectation des paiements** : elle reste **calculée**, sans table d'affectation. Elle est déterministe, donc reproductible, sans double affectation possible ni désynchronisation entre une table et les paiements. Trop-perçu : un paiement au-delà des échéances n'est imputé à rien et apparaît comme « non affecté » dans la situation de l'élève. Une table d'affectation manuelle ne serait utile que pour des régularisations libres : à décider plus tard, si le besoin est confirmé.
6. **Situation financière** : nouvelles API en lecture seule, calculées par `compute_dues` (une seule règle) :
   - par élève : échéances, payé, restant, paiements, non affecté ;
   - agrégée par classe, par niveau et par académie (attendu, payé, restant, nombre d'élèves en retard, taux de recouvrement).
7. **Accès** :
   - saisie des tarifs et dispositions : administrateur de l'académie et super administrateur (inchangé) ;
   - situation financière : personnel de l'académie ;
   - parent : uniquement ses enfants ;
   - enseignant et élève : aucun accès aux finances.
8. **Production** : aucune valeur de tarif n'est créée par le code ni par une migration. Les écrans permettent à l'administration de les saisir. Des données d'essai n'existent que dans les tests et la base jetable de démonstration.

## 3. Lots

| Lot | Contenu |
|---|---|
| F1 | Écran dédié « Tarifs et échéances » au menu (administrateur et super administrateur), avec grille niveaux × natures ; nouvelles natures ; historique des tarifs |
| F2 | Situation financière : par élève, par classe et niveau, par académie ; vue parent de ses enfants |
| F3 | Graphique des paiements : filtres de structure et financiers, comparaison avec la période précédente, détail d'une période |
| A1 à A3 | Centre d'analyse : couche commune de filtres et d'indicateurs (effectifs, résultats, matières, enseignants avec contexte, présences), présentation FR, EN ou bilingue |
