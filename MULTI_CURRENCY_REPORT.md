# Architecture multi-devises — rapport V8 (P0)

## Le défaut corrigé

FEBA French Heritage Academy facture en dollars. Onze écrans écrivaient
`FCFA` en dur à côté du montant, et le modèle `Payment` ne stockait aucune
devise. Un encaissement de 125,50 $ s'affichait donc « 125,50 FCFA » : le
nombre était juste, l'unité fausse, et rien à l'écran ne le signalait.

Le reçu PDF faisait pire. Il écrivait :

```python
f"{payment.amount:,.0f} FCFA"          # → « 126 FCFA »
num2words(int(amount)).upper() + " FRANCS CFA"
```

Un paiement de 125,50 $ ressortait comme **126 FCFA**, en chiffres comme en
lettres. Le montant en toutes lettres fait foi en cas de litige : ce n'était
pas un défaut d'affichage, c'était un faux document.

## L'autorité : l'académie, et rien d'autre

`School.currency_code` est la seule source. Tout le reste en dérive :

| Champ | Origine | Pourquoi pas une colonne |
|---|---|---|
| `currency_code` | **stocké** — l'autorité | — |
| `currency_symbol` | dérivé du code | une colonne pourrait dire « FCFA » alors que le code vaut `USD` |
| `currency_name` | dérivé du code | idem |
| `currency_decimal_places` | dérivé du code | une valeur fausse multiplie ou divise toutes les recettes par cent |
| `currency_locale` | stocké, avec repli sur la devise | seul réglage réellement propre à l'établissement |

La devise n'est **jamais** lue depuis la langue de l'interface, le
navigateur, le pays, un symbole fourni par React, un dernier filtre, un
champ libre, ni aucun paramètre manipulable côté client.

Vérification directe :

```
POST /api/payments/   { "amount": "80.00", "currency": "XOF", "amount_minor": 999999 }
→ 201  { "currency": "USD", "amount_display": "$80.00" }
```

La devise transmise est ignorée, `amount_minor` transmis est ignoré.

## Les montants sont des entiers

`amount_minor` (BigInteger) est la valeur de référence : cents pour USD,
franc pour XOF, qui n'a pas de subdivision. `amount` (Decimal) reste exposé
pour la lisibilité, mais il est **recalculé depuis l'entier** à chaque
enregistrement — deux sources de vérité finissent toujours par diverger.

Aucun `float` n'intervient sur une somme d'argent. L'arrondi est
`ROUND_HALF_UP` : sur une facture, un parent attend 0,005 → 0,01, pas
l'arrondi bancaire au pair de Python.

```python
get_currency("USD").to_minor("125.50")   # 12550
get_currency("XOF").to_minor("50000")    # 50000  — et non 5 000 000
```

Se tromper de facteur sur le franc CFA multiplierait toutes les recettes
par cent.

## Deux devises ne s'additionnent jamais

`Money.__add__` lève une `ValidationError` sur des devises différentes. Il
n'existe aucun taux de conversion dans le projet, et il ne doit pas en
exister : un taux inventé transformerait un total en estimation présentée
comme un fait.

Les totaux consolidés sont **ventilés** :

```
FEBA         8 550 000 FCFA
FEBA_FHA     $681.50
```

En mode « Toutes les Académies », `useMoney()` renvoie `currency: null` et
les écrans affichent `$1,500.00 · 500 000 FCFA` — moins commode, et le seul
rendu honnête.

## Typographie

Le séparateur de milliers français est **U+202F** (espace fine insécable),
pas une espace ordinaire : une espace ordinaire autorise le navigateur à
couper `50 000 FCFA` en fin de ligne, ce qui donne « 50 » puis
« 000 FCFA ». Les tests verrouillent ce caractère.

| Devise | Rendu | Décimales | Symbole |
|---|---|---|---|
| XOF | `50 000 FCFA` | 0 | après |
| USD | `$1,250.00` | 2 | avant |

Une devise inconnue **échoue bruyamment** plutôt que de retomber sur une
valeur par défaut : afficher un montant dans la mauvaise unité ne se voit
pas à l'œil.

## Migration des données existantes

Migration en trois temps (`payments.0007`), sans perte :

1. ajout de `amount_minor` et `currency` ;
2. `RunPython` — pour chaque paiement, la devise vient de l'académie de
   l'élève, et l'entier est dérivé du décimal avec les décimales de CETTE
   devise ;
3. contrainte `amount_minor >= 0`.

Exécutée sur la base réelle : **270 paiements**, tous en `XOF`,
`amount_minor` total `8 550 000` — identique à la somme des décimaux, XOF
n'ayant pas de subdivision. Aucune valeur modifiée.

## Commandes d'audit et de réparation

```bash
python manage.py audit_payment_currencies
python manage.py repair_payment_currencies --dry-run
python manage.py repair_payment_currencies --apply
```

L'audit classe chaque paiement :

| Classe | Signification | Traitement |
|---|---|---|
| `CONFORME` | devise = celle de l'académie | rien |
| `AFFICHAGE` | code faux, montant juste | corrigé par `--apply` |
| `AMBIGU` | les décimales diffèrent : impossible de savoir si le montant a été saisi en FCFA ou en dollars | **jamais converti automatiquement** |
| `ORPHELIN` | élève sans académie | signalé, laissé en l'état |

`repair_payment_currencies --apply` **refuse de s'exécuter** s'il reste des
cas ambigus. Convertir silencieusement un historique reviendrait à réécrire
une comptabilité sur une hypothèse ; l'ambiguïté doit être tranchée par
l'établissement, pièce en main.

Sortie sur la base réelle après seed :

```
Audit des devises — 276 paiement(s)
Conforme : 276
Totaux par académie et par devise :
  FEBA         8 550 000 FCFA
  FEBA_FHA     $601.50
Aucune anomalie de devise.
```

## Ce qui a été corrigé écran par écran

| Emplacement | Avant | Après |
|---|---|---|
| `payments/pdf_generator.py` | `f"{amount:,.0f} FCFA"` | `payment.formatted_amount` |
| idem, montant en lettres | `… FRANCS CFA` toujours | `DOLLARS … AND … CENTS` en USD |
| idem, académie du reçu | `School.objects.first()` | académie **de l'élève** |
| idem, lieu | `Cotonou, le …` | ville de l'académie |
| `payments/views.py` notifications | `{amount} FCFA` | `formatted_amount` |
| `dashboard/views.py` KPI | `float` nu | `amount_minor` + `*_display` + `currency` |
| 11 écrans React | `FCFA` en dur | `useMoney()` / `amount_display` du serveur |

## Tests

20 tests dans `backend/tests/test_multi_currency.py`, 11 dans
`frontend/src/utils/money.test.js`. Ils couvrent le registre, l'autorité de
l'académie, le refus des falsifications, l'interdiction d'additionner deux
devises, les totaux consolidés, le formatage, et la présence de la devise
dans les réponses d'API et le tableau de bord.

## Limite connue

Le tableau de bord affiche `0 FCFA` de recettes pour FEBA sur l'année
civile en cours : les paiements de démonstration sont datés du début de
l'année **scolaire** (septembre), et le KPI filtre sur l'année **civile**.
Comportement antérieur à cette itération, conservé tel quel ; il n'affecte
ni les montants ni les devises, seulement la fenêtre du KPI.
