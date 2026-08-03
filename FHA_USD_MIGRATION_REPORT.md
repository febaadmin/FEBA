# Migration FEBA FHA vers le dollar — rapport

## Ce qui a été migré, et ce que ça a changé

FEBA French Heritage Academy facture en dollars. Avant cette itération, le
modèle `Payment` ne stockait **aucune devise** : onze écrans écrivaient
`FCFA` en dur, et le reçu PDF aussi.

## Migration en trois temps — `payments.0007`

| Étape | Opération | Pourquoi séparée |
|---|---|---|
| 1 | `AddField amount_minor`, `AddField currency` | les colonnes doivent exister avant d'être remplies |
| 2 | `RunPython backfill_currency_and_minor` | la devise vient de l'académie de l'élève ; l'entier est dérivé du décimal avec les décimales de CETTE devise |
| 3 | `AddConstraint amount_minor >= 0` | poser la contrainte avant le remplissage ferait échouer la migration sur une base existante |

La migration `schools.0014` renomme en parallèle `currency` en
`currency_code`, en trois temps également : ajout, copie par `RunPython`,
suppression. Renommer directement perdrait les valeurs sur les bases où
la colonne a divergé.

## Résultat sur la base réelle

```
$ python manage.py audit_payment_currencies

Audit des devises — 281 paiement(s)
Conforme : 281

Totaux par académie et par devise :
  FEBA         8 550 000 FCFA
  FEBA_FHA     $1,001.50

Aucune anomalie de devise.
```

Inspection directe de PostgreSQL, sans passer par l'ORM :

```sql
SELECT s.code, p.currency, COUNT(*), SUM(p.amount_minor), MIN(p.amount_minor), MAX(p.amount_minor)
FROM payments_payment p
JOIN students_student st ON st.id = p.student_id
JOIN schools_school s ON s.id = st.school_id
WHERE p.is_deleted = false GROUP BY s.code, p.currency;
```

| académie | currency | nb | total mineur | min | max |
|---|---|---|---|---|---|
| FEBA | XOF | 270 | 8 550 000 | 25 000 | 35 000 |
| FEBA_FHA | USD | 11 | 100 150 | 7 500 | 12 550 |

**Aucune ligne en devise mixte. Aucune ligne sans devise.**

Le total FEBA en unités mineures — 8 550 000 — est identique à la somme
des décimaux d'avant migration : le franc CFA n'a pas de subdivision,
l'entier vaut le décimal. **Aucune valeur n'a été altérée.**

## Ce qui rend la devise infalsifiable

`School.currency_code` est la seule autorité. Symbole, nom, décimales et
locale en **dérivent** — une colonne séparée pourrait afficher « FCFA » sur
une académie dont le code vaut `USD`.

`Payment.save()` écrase toute devise transmise :

```python
self.currency = self.expected_currency_code   # = celle de l'académie de l'élève
```

Vérifié en direct sur l'API :

```
POST /api/payments/
  {"amount": "80.00", "currency": "XOF", "amount_minor": 999999, …}

→ 201   {"currency": "USD", "amount_display": "$80.00"}
```

La devise transmise est ignorée. L'`amount_minor` transmis est ignoré. Le
serializer les déclare `read_only`, et le modèle les recalcule de toute
façon.

## Classification des anomalies

`audit_payment_currencies` range chaque paiement dans une catégorie :

| Classe | Signification | Traitement par `repair --apply` |
|---|---|---|
| `CONFORME` | devise = celle de l'académie | rien |
| `AFFICHAGE` | code faux, montant juste | corrigé |
| `AMBIGU` | les décimales diffèrent : impossible de savoir si le montant a été saisi en FCFA ou en dollars | **jamais converti** |
| `ORPHELIN` | élève sans académie | signalé, laissé en l'état |

`repair_payment_currencies --apply` **refuse de s'exécuter** s'il reste un
cas ambigu. Convertir silencieusement un historique reviendrait à réécrire
une comptabilité sur une hypothèse ; l'ambiguïté se tranche avec les pièces
en main, pas avec une règle par défaut.

## Chaîne complète en dollars — vérifiée

| Étape | FEBA (XOF) | FEBA FHA (USD) |
|---|---|---|
| Paiement en base | `35000` XOF | `12550` USD |
| API `/payments/` | `35 000 FCFA` | `$125.50` |
| Tableau de bord | `currency: XOF` | `currency: USD`, recettes `$1,001.50` |
| Reçu PDF, chiffres | `35 000 FCFA` | `$125.50` |
| Reçu PDF, lettres | `TRENTE-CINQ MILLE FRANCS CFA` | `ONE HUNDRED AND TWENTY-FIVE DOLLARS AND FIFTY CENTS` |
| « FCFA » dans le PDF FHA | — | **absent** |
| Grille tarifaire | `25 000 / 35 000 FCFA` | `$75.00 / $125.50` |
| Paiement par carte | XOF | USD |
| Remboursement | XOF | USD |

## Un défaut d'impression trouvé et corrigé

Le séparateur de milliers français est l'espace fine insécable **U+202F**.
C'est la bonne typographie, et c'est ce que le formateur produit.

Helvetica — la police des reçus — ne la connaît pas. ReportLab ne signale
rien : il dessine un **rectangle plein**. Le reçu FEBA partait à
l'impression avec :

```
35■000 FCFA
```

Corrigé par une substitution appliquée **au seul PDF** : U+202F → U+00A0.
La propriété qui compte est conservée (le nombre ne se coupe pas en fin de
ligne), et le caractère existe dans la police. À l'écran, l'espace fine
reste en place — la corriger à la source dégraderait tout le reste.

Trois tests verrouillent le comportement.

## Aucune addition entre devises

`Money.__add__` lève une `ValidationError` sur des devises différentes.
Il n'existe **aucun taux de conversion** dans le projet, et il ne doit pas
en exister : un taux inventé transformerait un total en estimation
présentée comme un fait.

En mode « Toutes les Académies », `useMoney()` renvoie `currency: null` et
les écrans affichent :

```
$1,001.50 · 8 550 000 FCFA
```

Deux totaux, séparés. Moins commode, et le seul rendu honnête.
