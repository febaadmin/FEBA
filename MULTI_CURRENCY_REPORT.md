# MULTI_CURRENCY_REPORT.md — P1, juillet-août 2026

## Le bug, précisément

`/superadmin/payments`, académie « Toutes les Académies » sélectionnée :

```
Total encaissé : 2 850 601,5
```

= `2 850 000` (total FEBA, en FCFA) + `601,50` (total FEBA FHA, en USD),
additionnés comme si les deux étaient dans la même unité. Confirmé en
reproduisant exactement les montants des captures d'écran fournies.

## Cause exacte

`backend/apps/payments/views.py`, méthode `summary()` :

```python
total = qs.aggregate(t=Sum("amount"))["t"] or 0
```

`qs` n'est filtré que par académie/permissions, jamais par devise. Un
`Sum("amount")` sur des lignes en FCFA et en USD mélangées produit un
nombre dénué de sens — ni des francs, ni des dollars, ni rien d'autre.

## Ce qui existait déjà et n'a PAS été touché

`apps/core/currency.py` contenait déjà `Money`, `totals_by_currency()` et
`format_totals()` — une philosophie « on n'additionne jamais deux devises
directement, on les restitue séparément ». Cette brique est saine et reste
utilisée telle quelle ailleurs (voir `tests/test_multi_currency.py`,
23 tests, inchangés, toujours verts). Le problème n'était pas dans cette
brique : `PaymentViewSet.summary()` ne l'utilisait tout simplement pas, et
faisait sa propre somme brute à côté.

## Ce qui a été ajouté

Une brique complémentaire, PAS une réécriture de la précédente :
`CurrencyConversionService` (`backend/apps/core/currency_conversion.py`),
qui répond à un besoin différent — un total consolidé RÉEL, en une seule
devise, quand on le demande explicitement (plusieurs académies à la fois).

- `ExchangeRate` (`backend/apps/payments/exchange_rate_models.py`) :
  taux daté, avec origine, source de vérité en base.
- Repli sur `settings.FALLBACK_EXCHANGE_RATES` si aucun taux enregistré —
  mais **toujours marqué `is_fallback: true`** dans la réponse API, jamais
  silencieux.
- Aucune conversion tant qu'une seule devise n'est présente dans le
  résultat — pas de calcul inutile qui pourrait introduire un arrondi là
  où il n'y avait aucune raison d'en avoir.

## Contrat de la nouvelle réponse `/api/payments/summary/`

```json
{
  "reporting_currency": "XOF",
  "is_consolidated": true,
  "consolidated_total": {
    "amount": "1600000.00", "amount_minor": 160000000,
    "currency": "XOF", "formatted": "1 600 000 FCFA"
  },
  "totals_by_currency": [
    {"currency": "XOF", "amount": "1000000.00", "formatted": "1 000 000 FCFA", "count": 1},
    {"currency": "USD", "amount": "1000.00", "formatted": "$1,000.00", "count": 1}
  ],
  "conversions": [
    {"original_currency": "USD", "original_amount": "1000.00",
     "converted_currency": "XOF", "converted_amount": "600000",
     "conversion": {"rate": "600", "rate_date": "2025-01-01", "is_fallback": false,
                     "label": "1 USD = 600 XOF"}}
  ],
  "conversion_errors": [],
  "by_type": {"inscription": {...}, "mensualite": {...}, ...},
  "total": 1600000.0
}
```

`total` (flottant) reste pour compatibilité ascendante — ce n'est plus une
somme brute mélangée, c'est désormais le total consolidé exprimé en
nombre.

## Exemple littéral de la demande, vérifié par test

```
FEBA = 1 000 000 FCFA
FEBA FHA = 1 000 USD
Taux = 600 FCFA pour 1 USD
```

```python
def test_exemple_litteral_de_la_demande(self):
    ...
    self.assertNotEqual(Decimal(resp.data["consolidated_total"]["amount"]), Decimal("1001000"))
    self.assertEqual(Decimal(resp.data["consolidated_total"]["amount"]), Decimal("1600000"))
```

**Vert.**

## Matrice de tests (12 tests, tous verts contre PostgreSQL réel)

| Scénario demandé | Test |
|---|---|
| FEBA uniquement | `test_feba_seule_reste_en_fcfa_sans_conversion` |
| FEBA FHA uniquement | `test_fha_seule_reste_en_dollars_sans_conversion` |
| Les deux académies | `test_exemple_litteral_de_la_demande`, `test_capture_ecran_reproduite_601_50_plus_2_850_000` |
| Plusieurs paiements USD/FCFA | `test_by_type_inscriptions_et_mensualites_consolides` |
| Paiement annulé | `test_paiement_annule_est_exclu_du_total` |
| Paiement supprimé | `test_paiement_supprime_est_exclu_du_total` |
| Taux nul/absent | `test_taux_absent_sans_secours_est_signale_pas_ignore` |
| Montant décimal | `test_conversion_avec_taux_decimal_arrondit_correctement` |
| Taux explicite affiché | `test_taux_utilise_est_explicite` |
| Taux de secours signalé | `test_taux_de_secours_est_marque_explicitement` |
| Détail par devise | `test_detail_par_devise_est_expose` |

**Non testés explicitement dans cette liste** (hors du contrat de l'API,
donc hors périmètre de ce correctif) : export Excel (déjà correct — chaque
ligne exportée porte sa propre devise, aucune somme n'y est faite côté
serveur) et rapport mensuel (mono-académie par construction, jamais de
mélange de devises à ce niveau).

## Frontend

`Payments.jsx` n'additionne et ne convertit plus AUCUN montant — il
affiche `summary.consolidated_total.formatted` et
`summary.by_type.*.formatted` tels que renvoyés par le serveur, et un
panneau de détail (devise par devise, taux utilisé) s'affiche uniquement
quand `is_consolidated` est vrai. Build de production vérifié après
modification (`npm run build`, succès).
