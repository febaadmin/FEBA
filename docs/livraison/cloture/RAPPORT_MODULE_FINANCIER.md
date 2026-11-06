# Module financier : tarifs, remises, exonérations, exceptions, échéanciers

État : **développé et testé localement** (backend, frontend, navigateur réel). Pour la CI, le déploiement et la production, voir `SUIVI_REPRISE_FINAL.md`.

## 1. Architecture (une seule règle de calcul)

```
FeeSchedule (tarif : académie, année, niveau, nature, montant, obligatoire/abonnement)
 ├─ FeeInstallment (échéances standard)
 ├─ EcheanceEleve (échéancier PERSONNEL d'un élève × tarif × année : remplace le standard pour lui seul)
 └─ StudentFeeArrangement (dispositions historiques : abonnement, exonération totale, réduction fixe)
RegleRemise (remise OU exonération : valeur, périmètre, période, conditions, cumul, justification)
JournalFinancier (historique inaltérable : auteur, date, avant, après, motif)
FeeScheduleChange (historique des tarifs, existant)

reminders.compute_dues  ──►  ajustements.appliquer  ──►  DueItem (prévu, exonéré, remisé, net, payé, reste, statut)
        │
        ├─ Situation financière (KPI, classe, niveau, élève, export)
        ├─ Relances (montant net, échéances standard ou personnelles)
        └─ Tableau de bord des paiements
```

Aucun écran ne recalcule un montant de son côté : tous lisent `compute_dues`. Les montants sont stockés et calculés en **unités mineures** (entiers), dans la devise de l'académie.

## 2. Tarifs (existant, renforcé)

- **Critères de tarif** : académie, année scolaire, niveau, nature de frais, montant, échéances, actif/inactif, obligatoire ou par abonnement.
  - Le tarif le plus précis l'emporte (niveau et année, puis année, puis niveau, puis tarif permanent).
  - Quatre contraintes d'unicité empêchent les doublons.
- **La classe et l'élève** ne portent pas de tarif propre, pour ne pas multiplier les règles concurrentes. Le prix d'une classe ou d'un élève s'ajuste par une **remise ou une exonération** de ce périmètre, ou par un **échéancier personnel**. Le tarif général de la classe ou du niveau n'est donc jamais modifié.
- **Correction** : renvoyer une échéance existante sans son identifiant, ou échanger deux dates, était refusé par la contrainte d'unicité.
  - Les échéances sont désormais rapprochées par identifiant, puis par date, ce qui conserve aussi le lien avec les relances déjà envoyées.
  - L'enregistrement se fait en deux temps.
  - Ce défaut a été découvert par le test E2E ; un test de non-régression a été ajouté.
- **Barème officiel** (`fee_plans/feba_2026_2027.json`, affiche 2026-2027) : la page « Tarifs » propose un aperçu complet avec les points à confirmer, puis un import par l'administration après confirmation explicite.
  - Seuls les tarifs absents sont créés, et chaque création est tracée.
  - **Il n'a pas été importé en production** : c'est une décision de l'administration (jours exacts des tranches, date des frais d'inscription, mois de garderie à confirmer).

## 3. Remises (`RegleRemise`, genre « remise »)

| Élément | Règle |
|---|---|
| Type | pourcentage (0,01 à 100) ou montant fixe |
| Catégories | exceptionnelle, plusieurs enfants d'une même famille, paiement anticipé, paiement intégral, sociale, situation particulière, décision administrative, autre |
| Périmètre | année, nature de frais, niveau, classe (de l'année concernée, d'après l'inscription), élève, famille (responsable commun) ; vide = tous |
| Période | seules les échéances dont la date est dans [début, fin] |
| Fratrie | à partir du N-ième enfant (N ≥ 2), rang par date de naissance, l'aîné en premier ; frères et sœurs = élèves de l'académie partageant un responsable |
| Paiement anticipé | accordée si le net (remise comprise) est entièrement payé au plus tard à la date limite |
| Paiement intégral | accordée si un seul paiement couvre tout le net |
| Traçabilité | nom, description, justification (obligatoire pour une décision individuelle), créée par, autorisée par, date, historique (avant / après / motif) |

**Règles de cumul et de priorité**
1. Une règle n'est comptée qu'**une fois** par élève × tarif × année.
2. Les remises **cumulables** s'additionnent.
3. Une remise **non cumulable** ne se combine avec aucune autre. Le moteur retient la solution **la plus favorable à la famille** entre « la somme des cumulables » et « la meilleure non cumulable » (à égalité : priorité, puis ancienneté).
4. Les remises écartées sont **affichées avec la raison** dans la fiche de l'élève et dans l'impact de la règle. La décision n'est jamais implicite.
5. Une condition non remplie (anticipé, intégral) écarte la remise, avec sa raison, et le calcul est refait sans elle.
6. **Jamais de montant négatif** : chaque réduction est plafonnée au reste dû de l'échéance. La réduction est imputée sur les **dernières** échéances : elle allège le solde sans retarder la première tranche.
7. **Arrondi** : le pourcentage est appliqué au total concerné, puis arrondi à l'unité mineure la plus proche (demi vers le haut).

## 4. Exonérations (`RegleRemise`, genre « exonération »)

- Une exonération est totale (100 %) ou partielle (pourcentage ou montant). Elle peut porter sur une nature de frais, une période (exonération temporaire), un élève, une famille, une classe ou un niveau.
- Elle est **toujours justifiée** (validation côté serveur), et la justification n'est **jamais envoyée aux familles**.
- Elle est **déduite avant les remises** et comptée à part (KPI « Exonérations »). Elle n'est ni une remise commerciale ni un paiement.
- Une échéance entièrement exonérée a le statut « Exonérée ».

## 5. Exceptions individuelles et échéanciers personnalisés

- **Remise ou exonération pour un élève ou une famille** : il suffit de renseigner le périmètre « Élève » ou « Famille ». Les autres élèves ne sont pas touchés, et c'est testé.
- **Échéancier personnel** (`EcheanceEleve`) : il remplace, pour un élève, un tarif et une année, les échéances standard. Il sert pour un délai supplémentaire ou une autre répartition.
  - La somme doit rester égale au montant du tarif : une réduction se définit à part.
  - Le motif est obligatoire.
- **Revenir au standard** désactive l'échéancier personnel sans rien supprimer.
- **Les paiements ne sont jamais modifiés** : ils sont réimputés par le moteur, et c'est testé.
- **Les relances** suivent l'échéancier personnel, avec leur propre clé d'idempotence (`pers<id>`), sans collision avec les échéances standard.

## 6. Historique et traçabilité

- `JournalFinancier` est **inaltérable** : toute modification ou suppression est refusée au niveau du modèle.
- Il trace : création, modification (champs changés avant / après, motif obligatoire), annulation et réactivation des règles, échéanciers personnels et dispositions d'élèves.
  - **Audit** : avant ce travail, la suppression d'une disposition (exonération, réduction, abonnement) ne laissait **aucune trace**.
- Les règles **ne se suppriment pas** (DELETE renvoie 405) : elles s'annulent, avec un motif.
- L'onglet « Historique » affiche les tarifs et les décisions, filtrables. La fiche de l'élève affiche son historique, au personnel uniquement.

## 7. Migrations

- `payments/0018_remises_exonerations_echeanciers` est **additive** : trois tables et un champ nullable `PaymentReminder.student_installment`.
- Aucune donnée existante n'est modifiée. Les dispositions historiques (`StudentFeeArrangement`) continuent d'être appliquées par le même moteur.

## 8. Points connus

- Modifier le montant d'un tarif déjà payé exige un motif (règle existante), mais le nouveau montant s'applique rétroactivement aux échéances de ce tarif.
  - Pour une nouvelle année, il faut créer un nouveau tarif sur la nouvelle année, ce que permet la structure par année.
  - Figer des instantanés par élève serait une évolution à décider.
- Le rang dans la fratrie se calcule sur les élèves **actifs** de l'académie.
