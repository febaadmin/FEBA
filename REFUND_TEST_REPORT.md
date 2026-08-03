# Remboursements — rapport de test

## Statut, en une ligne

**Éprouvé contre un prestataire SIMULÉ.** Aucun remboursement réel n'a été
émis chez Stripe : l'environnement ne dispose d'aucun identifiant de test
valide. Voir `WEBHOOK_TEST_REPORT.md`, section finale.

## La règle qui structure tout

**Un remboursement ne peut pas dépasser ce qui a été encaissé.**

Elle est appliquée à deux endroits, et les deux sont nécessaires :

| Où | Quoi |
|---|---|
| Modèle | `register_refund()` compare au solde remboursable et lève |
| **Base de données** | `CheckConstraint(amount_refunded_minor <= amount_minor)` |

La contrainte de base n'est pas redondante : une erreur applicative ne
protège pas d'une écriture faite par un script d'exploitation ou une
console d'administration.

Deux autres contraintes complètent :

```sql
CHECK (amount_minor > 0)
CHECK (amount_refunded_minor >= 0)
```

## Résultats — 8 tests, tous verts

```
$ pytest tests/test_card_payments.py::RefundTests -v

test_un_remboursement_partiel_laisse_un_solde                      ✓
test_un_remboursement_total_solde_la_transaction                   ✓
test_un_remboursement_ne_peut_pas_depasser_l_encaissement          ✓
test_le_plafond_est_verifie_dans_le_modele_aussi                   ✓
test_un_parent_ne_peut_pas_se_rembourser                           ✓
test_un_administrateur_d_une_autre_academie_ne_peut_pas_rembourser ✓
test_un_paiement_non_encaisse_n_est_pas_remboursable               ✓
test_un_remboursement_par_webhook_n_est_compte_qu_une_fois         ✓
```

## Scénarios détaillés

### Remboursement partiel

Transaction FEBA FHA de **125,50 $**. Remboursement de **25,50 $**.

| | |
|---|---|
| Statut après | `partially_refunded` |
| `amount_refunded_minor` | 2550 |
| Solde restant renvoyé | **`$100.00`** |

Le montant est rendu par le serveur, dans la devise de l'académie. Le
navigateur ne reconstitue aucun symbole.

### Remboursement total

Sans montant précisé, le solde remboursable entier est rendu.

| | |
|---|---|
| Statut après | `refunded` |
| Solde restant | **`$0.00`** |

### Dépassement refusé

Après un premier remboursement de 100,00 $ sur 125,50 $, un second de
100,00 $ est demandé.

```
→ 400 Bad Request
   Remboursement impossible : $100.00 dépasse le solde remboursable de $25.50.
```

`amount_refunded_minor` reste à **10000**. Rien n'a bougé.

### Permissions

| Qui | Résultat |
|---|---|
| Parent (`role_level < 80`) | **403** — un parent ne se rembourse pas lui-même |
| Administration d'une autre académie | **403** |
| Administration de l'académie | autorisé |

Dans les deux cas de refus, `amount_refunded_minor` reste à **0** :
le refus est vérifié par son effet, pas seulement par le code HTTP.

### Transaction non encaissée

Une tentative `pending` n'est pas remboursable :

```
→ 400   Seul un paiement encaissé peut être remboursé.
```

### Webhook `charge.refunded`

Le prestataire transmet le **cumul** remboursé, pas l'incrément. Le delta
est calculé avant enregistrement.

Séquence testée : remboursement de 25,50 $ par l'API, puis réception du
webhook annonçant `amount_refunded: 2550`.

| | |
|---|---|
| Attendu | 2550 |
| Obtenu | **2550** |

Sans ce calcul de delta, le même remboursement serait compté deux fois, et
le solde tomberait à 75,00 $ au lieu de 100,00 $.

## Idempotence côté prestataire

La clé d'idempotence du remboursement inclut le montant déjà remboursé :

```python
idempotency_key=f"refund-{transaction.pk}-{transaction.amount_refunded_minor}"
```

Un rejeu réseau du même remboursement retombe donc sur la même opération
chez le prestataire, au lieu de rendre l'argent deux fois. Un remboursement
*suivant*, lui, a une clé différente — il n'est pas confondu avec le
précédent.

## Ce qui reste non validé

Un remboursement réel chez Stripe suppose un encaissement réel, donc un
compte marchand. Cette validation externe reste ouverte.

Ce qui est acquis : la logique de plafond, de permissions, de cumul et
d'idempotence est éprouvée, et les contraintes de base tiendraient même si
le code applicatif était contourné.
