# Configurer le paiement par carte — guide d'installation

Ce guide s'adresse à la personne qui installe FEBA pour l'établissement.
Il ne demande aucune connaissance de Django.

> **Rien de ce qui suit ne fonctionne sans compte marchand validé.** Le
> projet n'invente aucune clé et ne peut pas en créer. Tant que le
> prestataire n'a pas validé le dossier de l'établissement, aucun paiement
> réel n'est possible — aucune configuration ne peut y suppléer.

---

## 1. Ouvrir le compte marchand

1. Créer un compte sur <https://dashboard.stripe.com/register>.
2. Renseigner les informations légales de l'établissement (raison sociale,
   pays, coordonnées bancaires).
3. Attendre la validation. Elle conditionne les paiements **réels** ; les
   paiements de **test** fonctionnent immédiatement.

Deux mondes coexistent et ne communiquent jamais :

| Mode | Clés | Cartes | Argent |
|---|---|---|---|
| **test** | `sk_test_…` / `pk_test_…` | cartes de test uniquement | aucun |
| **production** | `sk_live_…` / `pk_live_…` | vraies cartes | réel |

Mélanger les deux est l'erreur la plus coûteuse : un paiement créé dans un
mode n'est **jamais** confirmé dans l'autre. La commande de configuration
refuse cette combinaison.

---

## 2. Relever les clés

Tableau de bord Stripe → **Développeurs → Clés API**.

| Clé | Forme | Qui peut la voir |
|---|---|---|
| Clé publique | `pk_test_…` / `pk_live_…` | tout le monde, elle est publique |
| Clé secrète | `sk_test_…` / `sk_live_…` | **le serveur uniquement** |

La clé secrète donne le contrôle du compte marchand. Elle ne doit jamais
être envoyée au navigateur, collée dans un message, ni ajoutée à Git.

---

## 3. Configurer FEBA

```bash
make payments-setup
```

La commande pose quatre questions, vérifie les réponses, et **n'écrit rien
si quelque chose ne va pas** :

```
  ✗ La clé secrète et la clé publique ne sont pas dans le même mode
    (test / production).
CommandError: Configuration refusée. Aucune clé n'a été écrite : une
configuration à moitié juste est pire qu'absente.
```

Elle met à jour `.env` **en place**, sans toucher aux réglages voisins
(base de données, e-mail), et restreint les permissions du fichier à son
seul propriétaire.

Mode non interactif (déploiement automatisé) :

```bash
python manage.py payments_setup --non-interactive \
  --secret-key "sk_test_…" \
  --publishable-key "pk_test_…" \
  --webhook-secret "whsec_…" \
  --public-base-url "https://ecole.exemple.org"
```

Redémarrer le serveur pour recharger l'environnement.

---

## 4. Vérifier les identifiants

```bash
make payments-check
```

Cette commande **appelle réellement** le prestataire, en lecture seule :
rien n'est créé, rien n'est débité. Une clé bien formée mais révoquée est
détectée ici, pas au premier paiement d'un parent.

```
  ✓ Paiement par carte activé
  ✓ STRIPE_SECRET_KEY renseignée
  ✓ Mode « test » cohérent avec la clé
  ✓ Identifiants acceptés par le prestataire
```

Si le compte marchand n'est pas encore validé :

```
  ⚠ Le compte marchand n'est pas encore autorisé à encaisser.
    Les paiements de TEST fonctionneront ; les paiements réels seront
    refusés tant que le prestataire n'a pas validé le dossier.
```

Sans réseau, `--offline` vérifie la configuration locale et **le dit
clairement** : une clé bien formée peut être révoquée.

---

## 5. Déclarer le webhook

C'est l'étape la plus souvent oubliée, et la plus silencieuse quand elle
manque : le parent paie, sa carte est débitée, et l'application n'en sait
rien. Le symptôme — « j'ai payé mais ça n'apparaît pas » — arrive des jours
plus tard, par téléphone.

Tableau de bord Stripe → **Développeurs → Webhooks → Ajouter un point de
terminaison**.

**Adresse :**

```
https://VOTRE-DOMAINE/api/payments/webhook/stripe/
```

**Six événements à cocher :**

- `checkout.session.completed`
- `checkout.session.expired`
- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`
- `charge.refunded`

Stripe affiche alors un **secret de signature** (`whsec_…`) : le reporter
dans `STRIPE_WEBHOOK_SECRET` et redémarrer.

Sans ce secret, **tous** les événements sont refusés, donc aucun paiement
n'est encaissé. C'est voulu : sans signature, n'importe qui connaissant
l'URL pourrait déclarer un paiement réussi.

### En développement, sans domaine public

```bash
stripe login
stripe listen --forward-to localhost:8000/api/payments/webhook/stripe/
```

La commande affiche un `whsec_…` temporaire, à mettre dans `.env`.

---

## 6. Publier les tarifs

Le paiement en ligne **refuse tout montant venu du navigateur**. Il lit la
grille tarifaire de l'académie. Sans tarif publié, un parent voit :

> Aucun tarif n'est publié pour ce type de frais dans cette académie.
> Contactez le secrétariat.

C'est le comportement correct : un montant saisi librement par le payeur
n'est pas encaissable.

```python
from apps.payments.fee_models import FeeSchedule
from apps.schools.models import School

fha = School.objects.get(code="FEBA_FHA")
FeeSchedule.objects.create(
    academy=fha,
    school_year=fha.years.get(is_current=True),
    payment_type="mensualite",
    label="Mensualité",
    amount_minor=12550,        # 125,50 $ — cents, la devise vient de l'académie
)
```

`amount_minor` est en **unité mineure** : cents pour le dollar, franc pour
le franc CFA, qui n'a pas de subdivision. 125,50 $ → `12550` ;
50 000 FCFA → `50000`.

Un tarif défini pour un niveau l'emporte sur un tarif d'année, lui-même
prioritaire sur un tarif permanent : publier un prix unique et ne détailler
que les exceptions.

---

## 7. Essayer

Avec les clés de **test**, cartes fournies par Stripe :

| Carte | Résultat attendu |
|---|---|
| `4242 4242 4242 4242` | paiement accepté |
| `4000 0000 0000 0002` | carte refusée |
| `4000 0025 0000 3155` | authentification bancaire requise (3-D Secure) |

Date d'expiration future, cryptogramme au choix.

Après un paiement accepté, la ligne apparaît dans **Paiements** avec son
reçu, et dans **Transactions carte** avec son statut. Si elle n'apparaît
pas :

```bash
make payments-webhook-check
```

qui indique si des événements arrivent, lesquels ont échoué, et quelles
tentatives sont restées en attente.

---

## 8. Passer en production

1. Basculer le tableau de bord Stripe en mode production.
2. Relever les clés `sk_live_…` / `pk_live_…`.
3. `make payments-setup` avec ces clés — la commande avertit :
   > ⚠ Mode PRODUCTION : les paiements débiteront réellement les cartes.
4. Déclarer un **second** webhook, sur le point de terminaison de
   production (le secret diffère du mode test).
5. `make payments-check` — doit être vert, y compris `charges_enabled`.
6. `PUBLIC_BASE_URL` doit être en **HTTPS** ; la vérification échoue sinon.

---

## Ce que FEBA ne fait jamais

- Stocker un numéro de carte, une date d'expiration ou un cryptogramme.
  Le formulaire est celui du prestataire, sur son domaine ; ces données ne
  touchent pas ce serveur.
- Considérer un retour de navigateur comme une preuve de paiement. L'URL de
  succès est devinable ; seul le webhook signé encaisse.
- Lire un montant envoyé par le navigateur pour un payeur.
- Additionner des dollars et des francs CFA.
- Écrire une clé dans Git. `.env` est ignoré ; `.env.example` ne contient
  que des champs vides.

## En cas de problème

| Symptôme | Commande | Cause fréquente |
|---|---|---|
| Le bouton « Payer par carte » n'apparaît pas | `make payments-check` | `CARD_PAYMENTS_ENABLED=False` ou clés absentes |
| « Aucun tarif n'est publié » | — | grille tarifaire vide pour cette académie |
| Le parent paie, rien n'apparaît | `make payments-webhook-check` | webhook non déclaré ou adresse injoignable |
| « Invalid API Key » | `make payments-check` | clé révoquée, ou mode test/production mélangé |
| Événements refusés | — | `STRIPE_WEBHOOK_SECRET` absent ou issu de l'autre mode |
